#include "cpp/url_canonicalizer_adapter.h"

#include <atomic>

#include "cpp/url_canonicalizer_baseline.h"

namespace chromium_rust_perf {

namespace {
std::atomic_bool g_url_rollback_enabled{false};

std::string_view MapComponent(const uint8_t* base_data,
                              ChromiumRustUrlComponent comp) noexcept {
  if (comp.begin < 0 || comp.len < 0) {
    return std::string_view();
  }
  return std::string_view(
      reinterpret_cast<const char*>(base_data + static_cast<size_t>(comp.begin)),
      static_cast<size_t>(comp.len));
}
}  // namespace

void UrlScanner::SetRollbackEnabled(bool enabled) noexcept {
  g_url_rollback_enabled.store(enabled, std::memory_order_relaxed);
}

bool UrlScanner::IsRollbackEnabled() noexcept {
  return g_url_rollback_enabled.load(std::memory_order_relaxed);
}

UrlScanResult UrlScanner::Scan(const uint8_t* data, size_t len) const noexcept {
  UrlScanResult result;
  if (g_url_rollback_enabled.load(std::memory_order_relaxed)) {
    return CppBaselineUrlScanner::Scan(data, len);
  }

  ChromiumRustUrlParseResult ffi_res = {};
  uint32_t status = chromium_rust_url_parse_v1(data, len, &ffi_res);
  result.status = static_cast<UrlScanStatus>(status);
  
  if (result.status != UrlScanStatus::kOk) {
    return result;
  }

  result.scheme = MapComponent(data, ffi_res.scheme);
  result.username = MapComponent(data, ffi_res.username);
  result.password = MapComponent(data, ffi_res.password);
  result.host = MapComponent(data, ffi_res.host);
  result.port = ffi_res.port;
  result.path = MapComponent(data, ffi_res.path);
  result.query = MapComponent(data, ffi_res.query);
  result.fragment = MapComponent(data, ffi_res.fragment);

  return result;
}

ptrdiff_t UrlScanner::CanonicalizeHost(const uint8_t* host_data, size_t host_len, uint8_t* out_data, size_t out_max_len) const noexcept {
  if (g_url_rollback_enabled.load(std::memory_order_relaxed)) {
    return CppBaselineUrlScanner::CanonicalizeHost(host_data, host_len, out_data, out_max_len);
  }
  return chromium_rust_url_canonicalize_host_v1(host_data, host_len, out_data, out_max_len);
}

ptrdiff_t UrlScanner::PercentDecodeSafe(const uint8_t* in_data, size_t in_len, uint8_t* out_data, size_t out_max_len) const noexcept {
  if (g_url_rollback_enabled.load(std::memory_order_relaxed)) {
    return CppBaselineUrlScanner::PercentDecodeSafe(in_data, in_len, out_data, out_max_len);
  }
  return chromium_rust_url_percent_decode_safe_v1(in_data, in_len, out_data, out_max_len);
}

}  // namespace chromium_rust_perf
