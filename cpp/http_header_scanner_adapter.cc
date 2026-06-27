#include "cpp/http_header_scanner_adapter.h"

namespace chromium_rust_perf {

namespace {

HttpHeaderScanResult FromFfi(
    const ChromiumRustHttpHeaderScanResult& result) noexcept {
  return HttpHeaderScanResult{
      static_cast<HttpHeaderScanStatus>(result.status),
      result.line_count,
      result.max_line_length,
      result.header_end_offset,
  };
}

}  // namespace

bool HttpHeaderScanOptions::IsValid() const noexcept {
  return max_lines > 0 && max_line_length > 0;
}

HttpHeaderScanner::HttpHeaderScanner(HttpHeaderScanOptions options) noexcept
    : options_(options) {}

HttpHeaderScanResult HttpHeaderScanner::Scan(const uint8_t* data,
                                             size_t len) const noexcept {
  if (!options_.IsValid()) {
    return HttpHeaderScanResult{HttpHeaderScanStatus::kInvalidPolicy, 0, 0, 0};
  }

  ChromiumRustHttpHeaderScanResult ffi_result = {};
  const uint32_t status = chromium_rust_http_scan_headers_v1(
      data, len, options_.max_lines, options_.max_line_length, &ffi_result);
  if (status != ffi_result.status) {
    return HttpHeaderScanResult{HttpHeaderScanStatus::kInvalidPolicy, 0, 0, 0};
  }
  return FromFfi(ffi_result);
}

}  // namespace chromium_rust_perf
