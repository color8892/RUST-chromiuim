#ifndef CHROMIUM_RUST_PERF_HTTP_HEADER_SCANNER_FFI_H_
#define CHROMIUM_RUST_PERF_HTTP_HEADER_SCANNER_FFI_H_

#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

enum {
  CHROMIUM_RUST_HTTP_SCAN_OK = 0u,
  CHROMIUM_RUST_HTTP_SCAN_INCOMPLETE = 1u,
  CHROMIUM_RUST_HTTP_SCAN_NULL_INPUT = 2u,
  CHROMIUM_RUST_HTTP_SCAN_LENGTH_OVERFLOW = 3u,
  CHROMIUM_RUST_HTTP_SCAN_OUTPUT_NULL = 4u,
  CHROMIUM_RUST_HTTP_SCAN_INVALID_BYTE = 5u,
  CHROMIUM_RUST_HTTP_SCAN_MALFORMED_LINE_ENDING = 6u,
  CHROMIUM_RUST_HTTP_SCAN_TOO_MANY_LINES = 7u,
  CHROMIUM_RUST_HTTP_SCAN_LINE_TOO_LONG = 8u,
  CHROMIUM_RUST_HTTP_SCAN_INVALID_POLICY = 9u
};

typedef struct ChromiumRustHttpHeaderScanResult {
  uint32_t status;
  uint32_t line_count;
  uint32_t max_line_length;
  size_t header_end_offset;
} ChromiumRustHttpHeaderScanResult;

uint32_t chromium_rust_http_scan_headers_v1(
    const uint8_t* data,
    size_t len,
    uint32_t max_lines,
    uint32_t max_line_length,
    ChromiumRustHttpHeaderScanResult* out);

#ifdef __cplusplus
}
#endif

#endif  // CHROMIUM_RUST_PERF_HTTP_HEADER_SCANNER_FFI_H_
