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

/// # Safety
///
/// `host_data` must point to `host_len` readable bytes.
/// `out_data` must point to `out_max_len` writable bytes.
#[no_mangle]
pub unsafe extern "C" fn chromium_rust_url_canonicalize_host_v1(
    host_data: *const u8,
    host_len: usize,
    out_data: *mut u8,
    out_max_len: usize,
) -> isize {
    if host_data.is_null() || out_data.is_null() {
        return -1;
    }
    let host = unsafe { core::slice::from_raw_parts(host_data, host_len) };
    let out = unsafe { core::slice::from_raw_parts_mut(out_data, out_max_len) };
    match chromium_rust_url_canonicalizer::canonicalize_host(host, out) {
        Some(written) => written as isize,
        None => -1,
    }
}

/// # Safety
///
/// `in_data` must point to `in_len` readable bytes.
/// `out_data` must point to `out_max_len` writable bytes.
#[no_mangle]
pub unsafe extern "C" fn chromium_rust_url_percent_decode_safe_v1(
    in_data: *const u8,
    in_len: usize,
    out_data: *mut u8,
    out_max_len: usize,
) -> isize {
    if in_data.is_null() || out_data.is_null() {
        return -1;
    }
    let input = unsafe { core::slice::from_raw_parts(in_data, in_len) };
    let out = unsafe { core::slice::from_raw_parts_mut(out_data, out_max_len) };
    match chromium_rust_url_canonicalizer::percent_decode_safe(input, out) {
        Some(written) => written as isize,
        None => -1,
    }
}

/// # Safety
///
/// `out` must point to a writable `MojoValidateResult` for the duration of this call.
/// If `len` is non-zero, `data` must point to `len` readable bytes for the duration of this call.
/// `schema` must point to a valid, readable `MojoSchemaTable` for the duration of this call.
#[no_mangle]
pub unsafe extern "C" fn chromium_rust_mojo_validate_v1(
    data: *const u8,
    len: usize,
    schema: *const chromium_rust_mojo_validator::MojoSchemaTable,
    out: *mut chromium_rust_mojo_validator::MojoValidateResult,
) -> u32 {
    // SAFETY: caller guarantees pointer validity contracts.
    unsafe { chromium_rust_mojo_validator::chromium_rust_mojo_validate_v1_internal(data, len, schema, out) }
}


extern "C" {
    fn abort() -> !;
}

#[cfg(not(test))]
#[panic_handler]
fn panic(_info: &PanicInfo<'_>) -> ! {
    // SAFETY: abort terminates the process without formatting or unwinding.
    unsafe { abort() }
}
