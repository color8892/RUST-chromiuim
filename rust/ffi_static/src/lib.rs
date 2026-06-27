#![cfg_attr(
    all(
        not(test),
        not(feature = "prototype"),
        not(feature = "async-prototype"),
        not(feature = "cxx-bridge")
    ),
    no_std
)]
#![deny(unsafe_op_in_unsafe_fn)]
#![deny(clippy::expect_used)]
#![deny(clippy::panic)]
#![deny(clippy::print_stdout)]
#![deny(clippy::print_stderr)]
#![deny(clippy::todo)]
#![deny(clippy::unwrap_used)]

#[cfg(feature = "async-prototype")]
pub mod task_runner_bridge;
#[cfg(feature = "cxx-bridge")]
pub mod cxx_bridge;

pub use chromium_rust_http_header_scanner::ChromiumRustHttpHeaderScanResult;
pub use chromium_rust_url_canonicalizer::ChromiumRustUrlParseResult;

#[cfg(all(
    not(test),
    not(feature = "prototype"),
    not(feature = "async-prototype"),
    not(feature = "cxx-bridge")
))]
#[panic_handler]
fn panic_handler(_: &core::panic::PanicInfo<'_>) -> ! {
    unsafe extern "C" {
        fn abort() -> !;
    }

    unsafe { abort() }
}

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
    if out.is_null() {
        return 1; // MojoValidateStatus::NullInput
    }
    if len < 24 {
        let status = if data.is_null() || schema.is_null() { 1 } else { 2 };
        let res = chromium_rust_mojo_validator::MojoValidateResult {
            status,
            error_offset: if status == 2 { len as u32 } else { 0 },
        };
        unsafe { out.write(res) };
        return status;
    }
    // SAFETY: caller guarantees pointer validity contracts.
    let res = unsafe { chromium_rust_mojo_validator::validate_mojo_message(data, len, schema) };
    unsafe { out.write(res) };
    res.status
}

#[cfg(feature = "async-prototype")]
#[no_mangle]
pub unsafe extern "C" fn chromium_rust_mojo_writer_test(
    buf: *mut u8,
    buf_len: usize,
    method_id: u32,
    field_offset: usize,
    field_val: u32,
) -> isize {
    if buf.is_null() {
        return -1;
    }
    let slice = unsafe { core::slice::from_raw_parts_mut(buf, buf_len) };
    let mut builder = chromium_rust_mojo_validator::MojoMessageBuilder::new(slice, field_offset + 4);
    if builder.write_header(24, method_id).is_err() {
        return -1;
    }
    if builder.write_field_u32(24, field_offset, field_val).is_err() {
        return -1;
    }
    builder.next_offset() as isize
}

#[cfg(feature = "async-prototype")]
#[no_mangle]
pub unsafe extern "C" fn chromium_rust_mojo_reader_test(
    data: *const u8,
    len: usize,
    field_offset: usize,
) -> i64 {
    if data.is_null() {
        return -1;
    }
    let slice = unsafe { core::slice::from_raw_parts(data, len) };
    if let Some(reader) = chromium_rust_mojo_validator::MojoMessageReader::new(slice) {
        if let Some(val) = reader.get_field_u32(field_offset) {
            return val as i64;
        }
    }
    -1
}

#[cfg(feature = "async-prototype")]
#[no_mangle]
pub unsafe extern "C" fn chromium_rust_mojo_writer_string_test(
    buf: *mut u8,
    buf_len: usize,
    method_id: u32,
    field_offset: usize,
    str_ptr: *const u8,
    str_len: usize,
) -> isize {
    if buf.is_null() || str_ptr.is_null() {
        return -1;
    }
    let slice = unsafe { core::slice::from_raw_parts_mut(buf, buf_len) };
    let str_bytes = unsafe { core::slice::from_raw_parts(str_ptr, str_len) };
    let str_val = match core::str::from_utf8(str_bytes) {
        Ok(s) => s,
        Err(_) => return -1,
    };
    let mut builder = chromium_rust_mojo_validator::MojoMessageBuilder::new(slice, field_offset + 8);
    if builder.write_header(24, method_id).is_err() {
        return -1;
    }
    if builder.write_field_string(24, field_offset, str_val).is_err() {
        return -1;
    }
    builder.next_offset() as isize
}

#[cfg(feature = "async-prototype")]
#[no_mangle]
pub unsafe extern "C" fn chromium_rust_mojo_reader_string_test(
    data: *const u8,
    len: usize,
    field_offset: usize,
    out_buf: *mut u8,
    out_len: usize,
) -> isize {
    if data.is_null() || out_buf.is_null() {
        return -1;
    }
    let slice = unsafe { core::slice::from_raw_parts(data, len) };
    if let Some(reader) = chromium_rust_mojo_validator::MojoMessageReader::new(slice) {
        if let Some(val) = reader.get_field_string(field_offset) {
            let val_bytes = val.as_bytes();
            if val_bytes.len() > out_len {
                return -1;
            }
            unsafe {
                core::ptr::copy_nonoverlapping(val_bytes.as_ptr(), out_buf, val_bytes.len());
            }
            return val_bytes.len() as isize;
        }
    }
    -1
}

#[cfg(feature = "async-prototype")]
#[no_mangle]
pub unsafe extern "C" fn chromium_rust_mojo_writer_array_u32_test(
    buf: *mut u8,
    buf_len: usize,
    method_id: u32,
    field_offset: usize,
    array_ptr: *const u32,
    array_len: usize,
) -> isize {
    if buf.is_null() || array_ptr.is_null() {
        return -1;
    }
    let slice = unsafe { core::slice::from_raw_parts_mut(buf, buf_len) };
    let array_val = unsafe { core::slice::from_raw_parts(array_ptr, array_len) };
    let mut builder = chromium_rust_mojo_validator::MojoMessageBuilder::new(slice, field_offset + 8);
    if builder.write_header(24, method_id).is_err() {
        return -1;
    }
    if builder.write_field_array_u32(24, field_offset, array_val).is_err() {
        return -1;
    }
    builder.next_offset() as isize
}

#[cfg(feature = "async-prototype")]
#[no_mangle]
pub unsafe extern "C" fn chromium_rust_mojo_reader_array_u32_test(
    data: *const u8,
    len: usize,
    field_offset: usize,
    out_array: *mut u32,
    out_len: usize,
) -> isize {
    if data.is_null() || out_array.is_null() {
        return -1;
    }
    let slice = unsafe { core::slice::from_raw_parts(data, len) };
    if let Some(reader) = chromium_rust_mojo_validator::MojoMessageReader::new(slice) {
        let out_slice = unsafe { core::slice::from_raw_parts_mut(out_array, out_len) };
        if let Some(written) = reader.get_field_array_u32(field_offset, out_slice) {
            return written as isize;
        }
    }
    -1
}
