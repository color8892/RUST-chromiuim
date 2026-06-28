#ifndef CHROMIUM_RUST_PERF_COOKIE_CANONICALIZER_FFI_H_
#define CHROMIUM_RUST_PERF_COOKIE_CANONICALIZER_FFI_H_

#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

enum {
  CHROMIUM_RUST_COOKIE_CANONICALIZE_OK = 0u,
  CHROMIUM_RUST_COOKIE_CANONICALIZE_INCOMPLETE = 1u,
  CHROMIUM_RUST_COOKIE_CANONICALIZE_NULL_INPUT = 2u,
  CHROMIUM_RUST_COOKIE_CANONICALIZE_LENGTH_OVERFLOW = 3u,
  CHROMIUM_RUST_COOKIE_CANONICALIZE_OUTPUT_NULL = 4u,
  CHROMIUM_RUST_COOKIE_CANONICALIZE_INVALID_BYTE = 5u,
  CHROMIUM_RUST_COOKIE_CANONICALIZE_EMPTY_NAME = 6u,
  CHROMIUM_RUST_COOKIE_CANONICALIZE_INVALID_NAME = 7u,
  CHROMIUM_RUST_COOKIE_CANONICALIZE_UNCLOSED_QUOTE = 8u,
  CHROMIUM_RUST_COOKIE_CANONICALIZE_TOO_MANY_ATTRIBUTES = 9u,
  CHROMIUM_RUST_COOKIE_CANONICALIZE_ATTR_NAME_TOO_LONG = 10u,
  CHROMIUM_RUST_COOKIE_CANONICALIZE_ATTR_VALUE_TOO_LONG = 11u,
  CHROMIUM_RUST_COOKIE_CANONICALIZE_INVALID_POLICY = 12u,
  CHROMIUM_RUST_COOKIE_CANONICALIZE_INVALID_SAMESITE = 13u
};

enum {
  CHROMIUM_RUST_COOKIE_SAMESITE_NONE = 0u,
  CHROMIUM_RUST_COOKIE_SAMESITE_STRICT = 1u,
  CHROMIUM_RUST_COOKIE_SAMESITE_LAX = 2u,
  CHROMIUM_RUST_COOKIE_SAMESITE_NONE_VALUE = 3u
};

typedef struct ChromiumRustCookieComponent {
  int32_t begin;
  int32_t len;
} ChromiumRustCookieComponent;

typedef struct ChromiumRustCookieCanonicalizeResult {
  uint32_t status;
  ChromiumRustCookieComponent name;
  ChromiumRustCookieComponent value;
  uint32_t attribute_count;
  uint32_t max_attr_name_length;
  uint32_t max_attr_value_length;
  uint8_t has_secure;
  uint8_t has_httponly;
  uint32_t same_site;
  size_t bytes_consumed;
} ChromiumRustCookieCanonicalizeResult;

uint32_t chromium_rust_cookie_canonicalize_v1(
    const uint8_t* data,
    size_t len,
    uint32_t max_attributes,
    uint32_t max_attr_name_length,
    uint32_t max_attr_value_length,
    ChromiumRustCookieCanonicalizeResult* out);

#ifdef __cplusplus
}
#endif

#endif  // CHROMIUM_RUST_PERF_COOKIE_CANONICALIZER_FFI_H_