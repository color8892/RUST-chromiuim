#include "cpp/cookie_canonicalizer_adapter.h"

#include <atomic>

#include "cpp/cookie_canonicalizer_baseline.h"

namespace chromium_rust_perf {

namespace {

std::atomic_bool g_rollback_enabled{false};

std::string_view MapComponent(const uint8_t* base_data,
                              ChromiumRustCookieComponent comp) noexcept {
  if (comp.begin < 0 || comp.len < 0) {
    return std::string_view();
  }
  return std::string_view(
      reinterpret_cast<const char*>(base_data + static_cast<size_t>(comp.begin)),
      static_cast<size_t>(comp.len));
}

CookieCanonicalizeResult FromFfi(const uint8_t* data,
                                 const ChromiumRustCookieCanonicalizeResult& result) noexcept {
  return CookieCanonicalizeResult{
      static_cast<CookieCanonicalizeStatus>(result.status),
      MapComponent(data, result.name),
      MapComponent(data, result.value),
      result.attribute_count,
      result.max_attr_name_length,
      result.max_attr_value_length,
      result.has_secure != 0,
      result.has_httponly != 0,
      static_cast<CookieSameSite>(result.same_site),
      result.bytes_consumed,
  };
}

}  // namespace

CookieCanonicalizer::CookieCanonicalizer(CookieCanonicalizeOptions options) noexcept
    : options_(options), options_valid_(options.IsValid()) {}

void CookieCanonicalizer::SetRollbackEnabled(bool enabled) noexcept {
  g_rollback_enabled.store(enabled, std::memory_order_relaxed);
}

bool CookieCanonicalizer::IsRollbackEnabled() noexcept {
  return g_rollback_enabled.load(std::memory_order_relaxed);
}

CookieCanonicalizeResult CookieCanonicalizer::Canonicalize(const uint8_t* data,
                                                           size_t len) const noexcept {
  if (!options_valid_) {
    return CookieCanonicalizeResult{CookieCanonicalizeStatus::kInvalidPolicy};
  }

  if (g_rollback_enabled.load(std::memory_order_relaxed)) {
    CppBaselineCookieCanonicalizer baseline(options_);
    return baseline.Canonicalize(data, len);
  }

  ChromiumRustCookieCanonicalizeResult ffi_result = {};
  chromium_rust_cookie_canonicalize_v1(
      data,
      len,
      options_.max_attributes,
      options_.max_attr_name_length,
      options_.max_attr_value_length,
      &ffi_result);
  return FromFfi(data, ffi_result);
}

}  // namespace chromium_rust_perf