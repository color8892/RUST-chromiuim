#include "cpp/url_canonicalizer_adapter.h"

#include <atomic>

#include "cpp/url_canonicalizer_baseline.h"

namespace chromium_rust_perf {

namespace {
std::atomic_bool g_url_rollback_enabled{false};

std::string_view MapComponent(const uint8_t* base_data,
                              size_t data_len,
                              ChromiumRustUrlComponent comp) noexcept {
  if (comp.begin < 0 || comp.len < 0) {
    return std::string_view();
  }
  const size_t begin = static_cast<size_t>(comp.begin);
  const size_t len = static_cast<size_t>(comp.len);
  if (base_data == nullptr || begin > data_len || len > data_len - begin) {
    return std::string_view();
  }
  return std::string_view(reinterpret_cast<const char*>(base_data + begin), len);
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

  result.scheme = MapComponent(data, len, ffi_res.scheme);
  result.username = MapComponent(data, len, ffi_res.username);
  result.password = MapComponent(data, len, ffi_res.password);
  result.host = MapComponent(data, len, ffi_res.host);
  result.port = ffi_res.port;
  result.path = MapComponent(data, len, ffi_res.path);
  result.query = MapComponent(data, len, ffi_res.query);
  result.fragment = MapComponent(data, len, ffi_res.fragment);

  return result;
}

}  // namespace chromium_rust_perf
