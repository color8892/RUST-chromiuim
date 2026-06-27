// Copyright 2026 The Chromium Authors
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

#[cxx::bridge(namespace = "chromium_rust_perf")]
pub mod ffi {
    struct MojoValidateResultCxx {
        status: u32,
        error_offset: u32,
    }

    struct HttpHeaderScanResultCxx {
        status: u32,
        line_count: u32,
        max_line_length: u32,
        header_end_offset: usize,
    }

    struct UrlParseResultCxx {
        status: u32,
        scheme_start: i32,
        scheme_len: i32,
        host_start: i32,
        host_len: i32,
        port_start: i32,
        port_len: i32,
    }

    extern "Rust" {
        fn validate_mojo_cxx(data: &[u8], method_id: u32) -> MojoValidateResultCxx;

        fn scan_http_headers_cxx(
            data: &[u8],
            max_lines: u32,
            max_line_len: u32,
        ) -> HttpHeaderScanResultCxx;

        fn parse_url_cxx(url: &str) -> UrlParseResultCxx;
        fn canonicalize_host_cxx(host: &str, out: &mut [u8]) -> isize;
        fn percent_decode_cxx(input: &[u8], out: &mut [u8]) -> isize;
    }
}

pub fn validate_mojo_cxx(data: &[u8], method_id: u32) -> ffi::MojoValidateResultCxx {
    let fields = [
        chromium_rust_mojo_validator::MojoFieldConstraint { offset: 0, expected_size: 4, is_nullable: 0 },
    ];
    let methods = [
        chromium_rust_mojo_validator::MojoMethodConstraint {
            method_id,
            expected_payload_size: 8,
            field_constraints: fields.as_ptr(),
            field_count: fields.len() as u32,
        },
    ];
    let schema = chromium_rust_mojo_validator::MojoSchemaTable {
        methods: methods.as_ptr(),
        method_count: methods.len() as u32,
    };

    let res = unsafe {
        chromium_rust_mojo_validator::validate_mojo_message(
            data.as_ptr(),
            data.len(),
            &schema as *const _,
        )
    };

    ffi::MojoValidateResultCxx {
        status: res.status,
        error_offset: res.error_offset,
    }
}

pub fn scan_http_headers_cxx(
    data: &[u8],
    max_lines: u32,
    max_line_len: u32,
) -> ffi::HttpHeaderScanResultCxx {
    let mut out = chromium_rust_http_header_scanner::ChromiumRustHttpHeaderScanResult {
        status: 0,
        line_count: 0,
        max_line_length: 0,
        header_end_offset: 0,
    };
    
    unsafe {
        chromium_rust_http_header_scanner::chromium_rust_http_scan_headers_v1_internal(
            data.as_ptr(),
            data.len(),
            max_lines,
            max_line_len,
            &mut out as *mut _,
        );
    }
    
    ffi::HttpHeaderScanResultCxx {
        status: out.status,
        line_count: out.line_count,
        max_line_length: out.max_line_length,
        header_end_offset: out.header_end_offset,
    }
}

pub fn parse_url_cxx(url: &str) -> ffi::UrlParseResultCxx {
    let mut out = chromium_rust_url_canonicalizer::ChromiumRustUrlParseResult {
        status: 0,
        scheme: chromium_rust_url_canonicalizer::ChromiumRustUrlComponent { begin: -1, len: -1 },
        username: chromium_rust_url_canonicalizer::ChromiumRustUrlComponent { begin: -1, len: -1 },
        password: chromium_rust_url_canonicalizer::ChromiumRustUrlComponent { begin: -1, len: -1 },
        host: chromium_rust_url_canonicalizer::ChromiumRustUrlComponent { begin: -1, len: -1 },
        port: -1,
        port_component: chromium_rust_url_canonicalizer::ChromiumRustUrlComponent { begin: -1, len: -1 },
        path: chromium_rust_url_canonicalizer::ChromiumRustUrlComponent { begin: -1, len: -1 },
        query: chromium_rust_url_canonicalizer::ChromiumRustUrlComponent { begin: -1, len: -1 },
        fragment: chromium_rust_url_canonicalizer::ChromiumRustUrlComponent { begin: -1, len: -1 },
    };
    
    unsafe {
        chromium_rust_url_canonicalizer::chromium_rust_url_parse_v1_internal(
            url.as_ptr(),
            url.len(),
            &mut out as *mut _,
        );
    }
    
    ffi::UrlParseResultCxx {
        status: out.status,
        scheme_start: out.scheme.begin,
        scheme_len: out.scheme.len,
        host_start: out.host.begin,
        host_len: out.host.len,
        port_start: out.port_component.begin,
        port_len: out.port_component.len,
    }
}

pub fn canonicalize_host_cxx(host: &str, out: &mut [u8]) -> isize {
    match chromium_rust_url_canonicalizer::canonicalize_host(host.as_bytes(), out) {
        Some(written) => written as isize,
        None => -1,
    }
}

pub fn percent_decode_cxx(input: &[u8], out: &mut [u8]) -> isize {
    match chromium_rust_url_canonicalizer::percent_decode_safe(input, out) {
        Some(written) => written as isize,
        None => -1,
    }
}
