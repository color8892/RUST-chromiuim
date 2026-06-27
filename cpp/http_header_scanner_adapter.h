#ifndef CHROMIUM_RUST_PERF_HTTP_HEADER_SCANNER_ADAPTER_H_
#define CHROMIUM_RUST_PERF_HTTP_HEADER_SCANNER_ADAPTER_H_

#include <cstddef>
#include <cstdint>

#include "include/chromium_rust_perf/http_header_scanner_ffi.h"

namespace chromium_rust_perf {

enum class HttpHeaderScanStatus : uint32_t {
  kOk = CHROMIUM_RUST_HTTP_SCAN_OK,
  kIncomplete = CHROMIUM_RUST_HTTP_SCAN_INCOMPLETE,
  kNullInput = CHROMIUM_RUST_HTTP_SCAN_NULL_INPUT,
  kLengthOverflow = CHROMIUM_RUST_HTTP_SCAN_LENGTH_OVERFLOW,
  kOutputNull = CHROMIUM_RUST_HTTP_SCAN_OUTPUT_NULL,
  kInvalidByte = CHROMIUM_RUST_HTTP_SCAN_INVALID_BYTE,
  kMalformedLineEnding = CHROMIUM_RUST_HTTP_SCAN_MALFORMED_LINE_ENDING,
  kTooManyLines = CHROMIUM_RUST_HTTP_SCAN_TOO_MANY_LINES,
  kLineTooLong = CHROMIUM_RUST_HTTP_SCAN_LINE_TOO_LONG,
  kInvalidPolicy = CHROMIUM_RUST_HTTP_SCAN_INVALID_POLICY,
};

struct HttpHeaderScanOptions final {
  uint32_t max_lines = 1024;
  uint32_t max_line_length = 8192;

  [[nodiscard]] bool IsValid() const noexcept;
};

struct HttpHeaderScanResult final {
  HttpHeaderScanStatus status = HttpHeaderScanStatus::kIncomplete;
  uint32_t line_count = 0;
  uint32_t max_line_length = 0;
  size_t header_end_offset = 0;

  [[nodiscard]] bool ok() const noexcept {
    return status == HttpHeaderScanStatus::kOk;
  }
};

class HttpHeaderScanner final {
 public:
  explicit HttpHeaderScanner(HttpHeaderScanOptions options) noexcept;

  HttpHeaderScanner(const HttpHeaderScanner&) = delete;
  HttpHeaderScanner& operator=(const HttpHeaderScanner&) = delete;

  [[nodiscard]] HttpHeaderScanResult Scan(const uint8_t* data,
                                          size_t len) const noexcept;

 private:
  HttpHeaderScanOptions options_;
};

}  // namespace chromium_rust_perf

#endif  // CHROMIUM_RUST_PERF_HTTP_HEADER_SCANNER_ADAPTER_H_
