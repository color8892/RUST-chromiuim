#![no_std]
#![deny(unsafe_op_in_unsafe_fn)]
#![deny(clippy::expect_used)]
#![deny(clippy::panic)]
#![deny(clippy::print_stdout)]
#![deny(clippy::print_stderr)]
#![deny(clippy::todo)]
#![deny(clippy::unwrap_used)]

use core::panic::PanicInfo;

pub use chromium_rust_http_header_scanner::ChromiumRustHttpHeaderScanResult;
pub use chromium_rust_url_canonicalizer::ChromiumRustUrlParseResult;

/// # Safety
///
/// `out` must point to a writable `ChromiumRustHttpHeaderScanResult` for the
/// duration of this call. If `len` is non-zero, `data` must point to `len`
/// readable bytes for the duration of this call. Rust never stores either
/// pointer after returning.
#[no_mangle]
pub unsafe extern "C" fn chromium_rust_http_scan_headers_v1(
    data: *const u8,
    len: usize,
    max_lines: u32,
    max_line_length: u32,
    out: *mut ChromiumRustHttpHeaderScanResult,
) -> u32 {
    // SAFETY: caller guarantees the same pointer validity contract.
    unsafe {
        chromium_rust_http_header_scanner::chromium_rust_http_scan_headers_v1_internal(
            data,
            len,
            max_lines,
            max_line_length,
            out,
        )
    }
}

/// # Safety
///
/// `out` must point to a writable `ChromiumRustUrlParseResult` for the duration
/// of this call. If `len` is non-zero, `data` must point to `len` readable bytes
/// for the duration of this call. Rust never stores either pointer after
/// returning.
#[no_mangle]
pub unsafe extern "C" fn chromium_rust_url_parse_v1(
    data: *const u8,
    len: usize,
    out: *mut ChromiumRustUrlParseResult,
) -> u32 {
    // SAFETY: caller guarantees the same pointer validity contract.
    unsafe { chromium_rust_url_canonicalizer::chromium_rust_url_parse_v1(data, len, out) }
}

extern "C" {
    fn abort() -> !;
}

#[panic_handler]
fn panic(_info: &PanicInfo<'_>) -> ! {
    // SAFETY: abort terminates the process without formatting or unwinding.
    unsafe { abort() }
}
