#ifndef CHROMIUM_RUST_PERF_URL_CANONICALIZER_ADAPTER_H_
#define CHROMIUM_RUST_PERF_URL_CANONICALIZER_ADAPTER_H_

#include <string_view>
#include "include/chromium_rust_perf/url_canonicalizer_ffi.h"

namespace chromium_rust_perf {

enum class UrlScanStatus : uint32_t {
  kOk = CHROMIUM_RUST_URL_PARSE_OK,
  kNullInput = CHROMIUM_RUST_URL_PARSE_NULL_INPUT,
  kLengthOverflow = CHROMIUM_RUST_URL_PARSE_LENGTH_OVERFLOW,
  kOutputNull = CHROMIUM_RUST_URL_PARSE_OUTPUT_NULL,
  kInvalidScheme = CHROMIUM_RUST_URL_PARSE_INVALID_SCHEME,
  kInvalidHost = CHROMIUM_RUST_URL_PARSE_INVALID_HOST,
  kInvalidPort = CHROMIUM_RUST_URL_PARSE_INVALID_PORT,
};

struct UrlScanResult final {
  UrlScanStatus status = UrlScanStatus::kNullInput;
  std::string_view scheme;
  std::string_view username;
  std::string_view password;
  std::string_view host;
  int32_t port = -1;
  std::string_view path;
  std::string_view query;
  std::string_view fragment;

  [[nodiscard]] bool ok() const noexcept {
    return status == UrlScanStatus::kOk;
  }
};

class UrlScanner final {
 public:
  UrlScanner() noexcept = default;
  
  UrlScanner(const UrlScanner&) = delete;
  UrlScanner& operator=(const UrlScanner&) = delete;

  [[nodiscard]] UrlScanResult Scan(const uint8_t* data, size_t len) const noexcept;
  
  [[nodiscard]] UrlScanResult Scan(std::string_view url) const noexcept {
    return Scan(reinterpret_cast<const uint8_t*>(url.data()), url.length());
  }

  [[nodiscard]] ptrdiff_t CanonicalizeHost(const uint8_t* host_data, size_t host_len, uint8_t* out_data, size_t out_max_len) const noexcept;
  [[nodiscard]] ptrdiff_t PercentDecodeSafe(const uint8_t* in_data, size_t in_len, uint8_t* out_data, size_t out_max_len) const noexcept;

  static void SetRollbackEnabled(bool enabled) noexcept;
  static bool IsRollbackEnabled() noexcept;
};

}  // namespace chromium_rust_perf

#endif  // CHROMIUM_RUST_PERF_URL_CANONICALIZER_ADAPTER_H_
