#ifndef CHROMIUM_RUST_PERF_URL_CANONICALIZER_FFI_H_
#define CHROMIUM_RUST_PERF_URL_CANONICALIZER_FFI_H_

#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

enum {
  CHROMIUM_RUST_URL_PARSE_OK = 0u,
  CHROMIUM_RUST_URL_PARSE_NULL_INPUT = 1u,
  CHROMIUM_RUST_URL_PARSE_LENGTH_OVERFLOW = 2u,
  CHROMIUM_RUST_URL_PARSE_OUTPUT_NULL = 3u,
  CHROMIUM_RUST_URL_PARSE_INVALID_SCHEME = 4u,
  CHROMIUM_RUST_URL_PARSE_INVALID_HOST = 5u,
  CHROMIUM_RUST_URL_PARSE_INVALID_PORT = 6u
};

typedef struct ChromiumRustUrlComponent {
  int32_t begin;
  int32_t len;
} ChromiumRustUrlComponent;

typedef struct ChromiumRustUrlParseResult {
  uint32_t status;
  ChromiumRustUrlComponent scheme;
  ChromiumRustUrlComponent username;
  ChromiumRustUrlComponent password;
  ChromiumRustUrlComponent host;
  int32_t port;
  ChromiumRustUrlComponent port_component;
  ChromiumRustUrlComponent path;
  ChromiumRustUrlComponent query;
  ChromiumRustUrlComponent fragment;
} ChromiumRustUrlParseResult;

uint32_t chromium_rust_url_parse_v1(
    const uint8_t* data,
    size_t len,
    ChromiumRustUrlParseResult* out);

#ifdef __cplusplus
}
#endif

#endif  // CHROMIUM_RUST_PERF_URL_CANONICALIZER_FFI_H_
