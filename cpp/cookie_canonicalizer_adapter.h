#ifndef CHROMIUM_RUST_PERF_COOKIE_CANONICALIZER_ADAPTER_H_
#define CHROMIUM_RUST_PERF_COOKIE_CANONICALIZER_ADAPTER_H_

#include <string_view>
#include "include/chromium_rust_perf/cookie_canonicalizer_ffi.h"

namespace chromium_rust_perf {

enum class CookieCanonicalizeStatus : uint32_t {
  kOk = CHROMIUM_RUST_COOKIE_CANONICALIZE_OK,
  kIncomplete = CHROMIUM_RUST_COOKIE_CANONICALIZE_INCOMPLETE,
  kNullInput = CHROMIUM_RUST_COOKIE_CANONICALIZE_NULL_INPUT,
  kLengthOverflow = CHROMIUM_RUST_COOKIE_CANONICALIZE_LENGTH_OVERFLOW,
  kOutputNull = CHROMIUM_RUST_COOKIE_CANONICALIZE_OUTPUT_NULL,
  kInvalidByte = CHROMIUM_RUST_COOKIE_CANONICALIZE_INVALID_BYTE,
  kEmptyName = CHROMIUM_RUST_COOKIE_CANONICALIZE_EMPTY_NAME,
  kInvalidName = CHROMIUM_RUST_COOKIE_CANONICALIZE_INVALID_NAME,
  kUnclosedQuote = CHROMIUM_RUST_COOKIE_CANONICALIZE_UNCLOSED_QUOTE,
  kTooManyAttributes = CHROMIUM_RUST_COOKIE_CANONICALIZE_TOO_MANY_ATTRIBUTES,
  kAttrNameTooLong = CHROMIUM_RUST_COOKIE_CANONICALIZE_ATTR_NAME_TOO_LONG,
  kAttrValueTooLong = CHROMIUM_RUST_COOKIE_CANONICALIZE_ATTR_VALUE_TOO_LONG,
  kInvalidPolicy = CHROMIUM_RUST_COOKIE_CANONICALIZE_INVALID_POLICY,
  kInvalidSameSite = CHROMIUM_RUST_COOKIE_CANONICALIZE_INVALID_SAMESITE,
};

enum class CookieSameSite : uint32_t {
  kNone = CHROMIUM_RUST_COOKIE_SAMESITE_NONE,
  kStrict = CHROMIUM_RUST_COOKIE_SAMESITE_STRICT,
  kLax = CHROMIUM_RUST_COOKIE_SAMESITE_LAX,
  kNoneValue = CHROMIUM_RUST_COOKIE_SAMESITE_NONE_VALUE,
};

struct CookieCanonicalizeOptions final {
  uint32_t max_attributes = 0;
  uint32_t max_attr_name_length = 0;
  uint32_t max_attr_value_length = 0;

  [[nodiscard]] bool IsValid() const noexcept {
    return max_attributes > 0 && max_attr_name_length > 0 && max_attr_value_length > 0;
  }
};

struct CookieCanonicalizeResult final {
  CookieCanonicalizeStatus status = CookieCanonicalizeStatus::kNullInput;
  std::string_view name;
  std::string_view value;
  uint32_t attribute_count = 0;
  uint32_t max_attr_name_length = 0;
  uint32_t max_attr_value_length = 0;
  bool has_secure = false;
  bool has_httponly = false;
  CookieSameSite same_site = CookieSameSite::kNone;
  size_t bytes_consumed = 0;

  [[nodiscard]] bool ok() const noexcept {
    return status == CookieCanonicalizeStatus::kOk;
  }
};

class CookieCanonicalizer final {
 public:
  explicit CookieCanonicalizer(CookieCanonicalizeOptions options) noexcept;

  CookieCanonicalizer(const CookieCanonicalizer&) = delete;
  CookieCanonicalizer& operator=(const CookieCanonicalizer&) = delete;

  [[nodiscard]] CookieCanonicalizeResult Canonicalize(const uint8_t* data,
                                                      size_t len) const noexcept;

  static void SetRollbackEnabled(bool enabled) noexcept;
  static bool IsRollbackEnabled() noexcept;

 private:
  CookieCanonicalizeOptions options_;
  bool options_valid_;
};

}  // namespace chromium_rust_perf

#endif  // CHROMIUM_RUST_PERF_COOKIE_CANONICALIZER_ADAPTER_H_