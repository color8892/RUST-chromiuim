#![no_main]

use libfuzzer_sys::fuzz_target;
use chromium_rust_http_header_scanner::{HeaderScanner, ScanPolicy};

fuzz_target!(|data: &[u8]| {
    if data.len() < 8 {
        return;
    }

    // Extract policy limits from the first 8 bytes
    let max_lines = u32::from_ne_bytes([data[0], data[1], data[2], data[3]]);
    let max_line_length = u32::from_ne_bytes([data[4], data[5], data[6], data[7]]);

    let payload = &data[8..];

    // Initialize scanner with extracted policy and execute scan
    if let Some(policy) = ScanPolicy::new(max_lines, max_line_length) {
        let scanner = HeaderScanner::new(policy);
        let _ = scanner.scan(payload);
    }
});
