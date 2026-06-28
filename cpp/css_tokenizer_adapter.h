#ifndef CHROMIUM_RUST_PERF_CSS_TOKENIZER_ADAPTER_H_
#define CHROMIUM_RUST_PERF_CSS_TOKENIZER_ADAPTER_H_

#include <cstddef>
#include <cstdint>
#include "include/chromium_rust_perf/css_tokenizer_ffi.h"

namespace chromium_rust_perf {

enum class CssTokenizeStatus : uint32_t {
  kOk = CHROMIUM_RUST_CSS_TOKENIZE_OK,
  kIncomplete = CHROMIUM_RUST_CSS_TOKENIZE_INCOMPLETE,
  kNullInput = CHROMIUM_RUST_CSS_TOKENIZE_NULL_INPUT,
  kLengthOverflow = CHROMIUM_RUST_CSS_TOKENIZE_LENGTH_OVERFLOW,
  kOutputNull = CHROMIUM_RUST_CSS_TOKENIZE_OUTPUT_NULL,
  kInvalidByte = CHROMIUM_RUST_CSS_TOKENIZE_INVALID_BYTE,
  kBadEscape = CHROMIUM_RUST_CSS_TOKENIZE_BAD_ESCAPE,
  kUnclosedComment = CHROMIUM_RUST_CSS_TOKENIZE_UNCLOSED_COMMENT,
  kUnclosedString = CHROMIUM_RUST_CSS_TOKENIZE_UNCLOSED_STRING,
  kTooManyTokens = CHROMIUM_RUST_CSS_TOKENIZE_TOO_MANY_TOKENS,
  kTokenTooLong = CHROMIUM_RUST_CSS_TOKENIZE_TOKEN_TOO_LONG,
  kInvalidPolicy = CHROMIUM_RUST_CSS_TOKENIZE_INVALID_POLICY,
};

struct CssTokenizeOptions final {
  uint32_t max_tokens = 0;
  uint32_t max_token_length = 0;

  [[nodiscard]] bool IsValid() const noexcept {
    return max_tokens > 0 && max_token_length > 0;
  }
};

struct CssTokenizeResult final {
  CssTokenizeStatus status = CssTokenizeStatus::kNullInput;
  uint32_t token_count = 0;
  uint32_t max_token_length = 0;
  size_t bytes_consumed = 0;

  [[nodiscard]] bool ok() const noexcept {
    return status == CssTokenizeStatus::kOk;
  }
};

class CssTokenizer final {
 public:
  explicit CssTokenizer(CssTokenizeOptions options) noexcept;

  CssTokenizer(const CssTokenizer&) = delete;
  CssTokenizer& operator=(const CssTokenizer&) = delete;

  [[nodiscard]] CssTokenizeResult Tokenize(const uint8_t* data, size_t len) const noexcept;

  static void SetRollbackEnabled(bool enabled) noexcept;
  static bool IsRollbackEnabled() noexcept;

 private:
  CssTokenizeOptions options_;
  bool options_valid_;
};

}  // namespace chromium_rust_perf

#endif  // CHROMIUM_RUST_PERF_CSS_TOKENIZER_ADAPTER_H_