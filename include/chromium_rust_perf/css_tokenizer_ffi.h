#ifndef CHROMIUM_RUST_PERF_CSS_TOKENIZER_FFI_H_
#define CHROMIUM_RUST_PERF_CSS_TOKENIZER_FFI_H_

#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

enum {
  CHROMIUM_RUST_CSS_TOKENIZE_OK = 0u,
  CHROMIUM_RUST_CSS_TOKENIZE_INCOMPLETE = 1u,
  CHROMIUM_RUST_CSS_TOKENIZE_NULL_INPUT = 2u,
  CHROMIUM_RUST_CSS_TOKENIZE_LENGTH_OVERFLOW = 3u,
  CHROMIUM_RUST_CSS_TOKENIZE_OUTPUT_NULL = 4u,
  CHROMIUM_RUST_CSS_TOKENIZE_INVALID_BYTE = 5u,
  CHROMIUM_RUST_CSS_TOKENIZE_BAD_ESCAPE = 6u,
  CHROMIUM_RUST_CSS_TOKENIZE_UNCLOSED_COMMENT = 7u,
  CHROMIUM_RUST_CSS_TOKENIZE_UNCLOSED_STRING = 8u,
  CHROMIUM_RUST_CSS_TOKENIZE_TOO_MANY_TOKENS = 9u,
  CHROMIUM_RUST_CSS_TOKENIZE_TOKEN_TOO_LONG = 10u,
  CHROMIUM_RUST_CSS_TOKENIZE_INVALID_POLICY = 11u
};

typedef struct ChromiumRustCssTokenizeResult {
  uint32_t status;
  uint32_t token_count;
  uint32_t max_token_length;
  size_t bytes_consumed;
} ChromiumRustCssTokenizeResult;

uint32_t chromium_rust_css_tokenize_v1(
    const uint8_t* data,
    size_t len,
    uint32_t max_tokens,
    uint32_t max_token_length,
    ChromiumRustCssTokenizeResult* out);

#ifdef __cplusplus
}
#endif

#endif  // CHROMIUM_RUST_PERF_CSS_TOKENIZER_FFI_H_