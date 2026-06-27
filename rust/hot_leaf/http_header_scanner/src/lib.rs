#![cfg_attr(not(test), no_std)]
#![deny(unsafe_op_in_unsafe_fn)]
#![deny(clippy::expect_used)]
#![deny(clippy::panic)]
#![deny(clippy::print_stdout)]
#![deny(clippy::print_stderr)]
#![deny(clippy::todo)]
#![deny(clippy::unwrap_used)]

const DEFAULT_STATUS_OFFSET: usize = 0;

#[repr(u32)]
#[derive(Clone, Copy, Eq, PartialEq)]
#[cfg_attr(test, derive(Debug))]
pub enum ScanStatus {
    Ok = 0,
    Incomplete = 1,
    NullInput = 2,
    LengthOverflow = 3,
    OutputNull = 4,
    InvalidByte = 5,
    MalformedLineEnding = 6,
    TooManyLines = 7,
    LineTooLong = 8,
    InvalidPolicy = 9,
}

impl ScanStatus {
    #[inline(always)]
    const fn code(self) -> u32 {
        self as u32
    }
}

#[repr(C)]
#[derive(Clone, Copy, Eq, PartialEq)]
#[cfg_attr(test, derive(Debug))]
pub struct ChromiumRustHttpHeaderScanResult {
    pub status: u32,
    pub line_count: u32,
    pub max_line_length: u32,
    pub header_end_offset: usize,
}

impl ChromiumRustHttpHeaderScanResult {
    #[inline(always)]
    const fn new(status: ScanStatus) -> Self {
        Self {
            status: status.code(),
            line_count: 0,
            max_line_length: 0,
            header_end_offset: DEFAULT_STATUS_OFFSET,
        }
    }
}

#[derive(Clone, Copy, Eq, PartialEq)]
#[cfg_attr(test, derive(Debug))]
pub struct ScanPolicy {
    max_lines: u32,
    max_line_length: u32,
}

impl ScanPolicy {
    #[inline(always)]
    pub const fn new(max_lines: u32, max_line_length: u32) -> Option<Self> {
        if max_lines == 0 || max_line_length == 0 {
            None
        } else {
            Some(Self {
                max_lines,
                max_line_length,
            })
        }
    }
}

pub struct HeaderScanner {
    policy: ScanPolicy,
}

impl HeaderScanner {
    #[inline(always)]
    pub const fn new(policy: ScanPolicy) -> Self {
        Self { policy }
    }

    pub fn scan(&self, input: &[u8]) -> ChromiumRustHttpHeaderScanResult {
        scan_header_block(input, self.policy)
    }
}

/// # Safety
///
/// `out` must point to a writable `ChromiumRustHttpHeaderScanResult` for the
/// duration of this call. If `len` is non-zero, `data` must point to `len`
/// readable bytes for the duration of this call. Rust never stores either
/// pointer after returning.
pub unsafe extern "C" fn chromium_rust_http_scan_headers_v1_internal(
    data: *const u8,
    len: usize,
    max_lines: u32,
    max_line_length: u32,
    out: *mut ChromiumRustHttpHeaderScanResult,
) -> u32 {
    if out.is_null() {
        return ScanStatus::OutputNull.code();
    }

    let result = match ScanPolicy::new(max_lines, max_line_length) {
        Some(policy) => scan_from_raw_parts(data, len, policy),
        None => ChromiumRustHttpHeaderScanResult::new(ScanStatus::InvalidPolicy),
    };

    // SAFETY: `out` was checked for null above. The C ABI contract requires the
    // caller to pass a writable result object for the duration of this call.
    unsafe {
        out.write(result);
    }
    result.status
}

#[inline(always)]
fn scan_from_raw_parts(
    data: *const u8,
    len: usize,
    policy: ScanPolicy,
) -> ChromiumRustHttpHeaderScanResult {
    if len > isize::MAX as usize {
        return ChromiumRustHttpHeaderScanResult::new(ScanStatus::LengthOverflow);
    }
    if len == 0 {
        return scan_header_block(&[], policy);
    }
    if data.is_null() {
        return ChromiumRustHttpHeaderScanResult::new(ScanStatus::NullInput);
    }

    // SAFETY: `data` is non-null, `len` is not greater than `isize::MAX`, and
    // the C ABI contract states that the input memory is readable for this call.
    let input = unsafe { core::slice::from_raw_parts(data, len) };
    scan_header_block(input, policy)
}

#[inline(always)]
fn scan_header_block(input: &[u8], policy: ScanPolicy) -> ChromiumRustHttpHeaderScanResult {
    let mut line_start = 0usize;
    let mut cursor = 0usize;
    let mut line_count = 0u32;
    let mut observed_max_line_length = 0u32;
    let len = input.len();
    let base = input.as_ptr();

    while cursor < len {
        // SAFETY: `cursor < len` is guaranteed by the loop condition.
        let byte = unsafe { *base.add(cursor) };

        if byte == 0 {
            return ChromiumRustHttpHeaderScanResult::new(ScanStatus::InvalidByte);
        }

        if byte == b'\n' {
            return ChromiumRustHttpHeaderScanResult::new(ScanStatus::MalformedLineEnding);
        }

        if byte != b'\r' {
            cursor += 1;
            continue;
        }

        if cursor + 1 >= len {
            return ChromiumRustHttpHeaderScanResult::new(ScanStatus::Incomplete);
        }
        // SAFETY: `cursor + 1 < len` is guaranteed by the check above.
        let next = unsafe { *base.add(cursor + 1) };
        if next != b'\n' {
            return ChromiumRustHttpHeaderScanResult::new(ScanStatus::MalformedLineEnding);
        }

        let line_len = cursor - line_start;
        if line_len > policy.max_line_length as usize {
            return ChromiumRustHttpHeaderScanResult::new(ScanStatus::LineTooLong);
        }

        if line_len == 0 {
            return ChromiumRustHttpHeaderScanResult {
                status: ScanStatus::Ok.code(),
                line_count,
                max_line_length: observed_max_line_length,
                header_end_offset: cursor + 2,
            };
        }

        if line_count == policy.max_lines {
            return ChromiumRustHttpHeaderScanResult::new(ScanStatus::TooManyLines);
        }

        line_count += 1;
        let line_len_u32 = if line_len > u32::MAX as usize {
            u32::MAX
        } else {
            line_len as u32
        };
        if line_len_u32 > observed_max_line_length {
            observed_max_line_length = line_len_u32;
        }

        cursor += 2;
        line_start = cursor;
    }

    ChromiumRustHttpHeaderScanResult::new(ScanStatus::Incomplete)
}

#[cfg(test)]
mod tests {
    use super::*;

    const POLICY: ScanPolicy = ScanPolicy {
        max_lines: 4,
        max_line_length: 32,
    };

    fn scan(input: &[u8]) -> ChromiumRustHttpHeaderScanResult {
        HeaderScanner::new(POLICY).scan(input)
    }

    #[test]
    fn scans_complete_header_block_without_copying_input() {
        let input = b"Host: example.test\r\nConnection: close\r\n\r\nbody";

        let result = scan(input);

        assert_eq!(result.status, ScanStatus::Ok.code());
        assert_eq!(result.line_count, 2);
        assert_eq!(result.max_line_length, 18);
        assert_eq!(result.header_end_offset, 41);
    }

    #[test]
    fn returns_incomplete_for_empty_or_partial_input() {
        assert_eq!(scan(b"").status, ScanStatus::Incomplete.code());
        assert_eq!(scan(b"Host: x\r").status, ScanStatus::Incomplete.code());
        assert_eq!(scan(b"Host: x\r\n").status, ScanStatus::Incomplete.code());
    }

    #[test]
    fn rejects_nul_bytes() {
        assert_eq!(
            scan(b"Host: \0\r\n\r\n").status,
            ScanStatus::InvalidByte.code()
        );
    }

    #[test]
    fn rejects_bare_lf_and_bare_cr() {
        assert_eq!(
            scan(b"Host: x\n\r\n").status,
            ScanStatus::MalformedLineEnding.code()
        );
        assert_eq!(
            scan(b"Host: x\rX\r\n").status,
            ScanStatus::MalformedLineEnding.code()
        );
    }

    #[test]
    fn enforces_line_count_limit() {
        let input = b"A: 1\r\nB: 2\r\nC: 3\r\nD: 4\r\nE: 5\r\n\r\n";

        assert_eq!(scan(input).status, ScanStatus::TooManyLines.code());
    }

    #[test]
    fn enforces_line_length_limit() {
        let input = b"012345678901234567890123456789012\r\n\r\n";

        assert_eq!(scan(input).status, ScanStatus::LineTooLong.code());
    }

    #[test]
    fn rejects_invalid_policy() {
        let mut out = ChromiumRustHttpHeaderScanResult::new(ScanStatus::Ok);

        let status = unsafe {
            chromium_rust_http_scan_headers_v1_internal(b"\r\n".as_ptr(), 2, 0, 32, &mut out)
        };

        assert_eq!(status, ScanStatus::InvalidPolicy.code());
        assert_eq!(out.status, ScanStatus::InvalidPolicy.code());
    }

    #[test]
    fn rejects_null_output_without_touching_input() {
        let status = unsafe {
            chromium_rust_http_scan_headers_v1_internal(
                core::ptr::null(),
                16,
                4,
                32,
                core::ptr::null_mut(),
            )
        };

        assert_eq!(status, ScanStatus::OutputNull.code());
    }

    #[test]
    fn rejects_null_input_when_length_is_non_zero() {
        let mut out = ChromiumRustHttpHeaderScanResult::new(ScanStatus::Ok);

        let status = unsafe {
            chromium_rust_http_scan_headers_v1_internal(core::ptr::null(), 16, 4, 32, &mut out)
        };

        assert_eq!(status, ScanStatus::NullInput.code());
        assert_eq!(out.status, ScanStatus::NullInput.code());
    }

    #[test]
    fn allows_null_input_for_empty_buffer() {
        let mut out = ChromiumRustHttpHeaderScanResult::new(ScanStatus::Ok);

        let status = unsafe {
            chromium_rust_http_scan_headers_v1_internal(core::ptr::null(), 0, 4, 32, &mut out)
        };

        assert_eq!(status, ScanStatus::Incomplete.code());
        assert_eq!(out.status, ScanStatus::Incomplete.code());
    }
}
