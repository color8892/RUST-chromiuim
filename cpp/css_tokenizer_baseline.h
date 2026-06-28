#ifndef CHROMIUM_RUST_PERF_CSS_TOKENIZER_BASELINE_H_
#define CHROMIUM_RUST_PERF_CSS_TOKENIZER_BASELINE_H_

#include <cstddef>
#include <cstdint>
#include "cpp/css_tokenizer_adapter.h"

namespace chromium_rust_perf {

class CppBaselineCssTokenizer {
 public:
  explicit CppBaselineCssTokenizer(CssTokenizeOptions options) noexcept
      : options_(options), options_valid_(options.IsValid()) {}

  [[nodiscard]] CssTokenizeResult Tokenize(const uint8_t* data, size_t len) const noexcept {
    CssTokenizeResult result;
    if (!options_valid_) {
      result.status = CssTokenizeStatus::kInvalidPolicy;
      return result;
    }
    if (len > static_cast<size_t>(9223372036854775807LL)) {
      result.status = CssTokenizeStatus::kLengthOverflow;
      return result;
    }
    if (len == 0) {
      result.status = CssTokenizeStatus::kOk;
      return result;
    }
    if (!data) {
      result.status = CssTokenizeStatus::kNullInput;
      return result;
    }

    uint32_t token_count = 0;
    uint32_t observed_max_token_length = 0;
    size_t cursor = 0;

    auto record_token = [&](uint32_t token_len, size_t next_cursor) -> bool {
      if (token_len > options_.max_token_length) {
        result.status = CssTokenizeStatus::kTokenTooLong;
        result.token_count = token_count;
        result.max_token_length = observed_max_token_length;
        result.bytes_consumed = next_cursor;
        return false;
      }
      if (token_count >= options_.max_tokens) {
        result.status = CssTokenizeStatus::kTooManyTokens;
        result.token_count = token_count;
        result.max_token_length = observed_max_token_length;
        result.bytes_consumed = next_cursor;
        return false;
      }
      token_count += 1;
      if (token_len > observed_max_token_length) {
        observed_max_token_length = token_len;
      }
      cursor = next_cursor;
      return true;
    };

    auto fail = [&](CssTokenizeStatus status, size_t at) {
      result.status = status;
      result.token_count = token_count;
      result.max_token_length = observed_max_token_length;
      result.bytes_consumed = at;
    };

    auto is_whitespace = [](uint8_t b) {
      return b == '\t' || b == '\n' || b == '\r' || b == '\f' || b == ' ';
    };
    auto is_ident = [](uint8_t b) {
      return (b >= 'a' && b <= 'z') || (b >= 'A' && b <= 'Z') || (b >= '0' && b <= '9') ||
             b == '_' || b == '-';
    };
    auto is_ident_start = [](uint8_t b) {
      return (b >= 'a' && b <= 'z') || (b >= 'A' && b <= 'Z') || b == '_' || b == '-';
    };

    while (cursor < len) {
      uint8_t b = data[cursor];
      if (b == 0) {
        fail(CssTokenizeStatus::kInvalidByte, cursor);
        return result;
      }

      if (is_whitespace(b)) {
        size_t start = cursor;
        cursor += 1;
        while (cursor < len && is_whitespace(data[cursor])) {
          cursor += 1;
        }
        if (!record_token(static_cast<uint32_t>(cursor - start), cursor)) {
          return result;
        }
        continue;
      }

      if (b == '/' && cursor + 1 < len && data[cursor + 1] == '*') {
        size_t start = cursor;
        cursor += 2;
        bool closed = false;
        while (cursor + 1 < len) {
          if (data[cursor] == '*' && data[cursor + 1] == '/') {
            cursor += 2;
            closed = true;
            break;
          }
          cursor += 1;
        }
        if (!closed) {
          fail(CssTokenizeStatus::kUnclosedComment, start);
          return result;
        }
        if (!record_token(static_cast<uint32_t>(cursor - start), cursor)) {
          return result;
        }
        continue;
      }

      if (b == '\'' || b == '"') {
        uint8_t quote = b;
        size_t start = cursor;
        cursor += 1;
        bool closed = false;
        while (cursor < len) {
          uint8_t ch = data[cursor];
          if (ch == quote) {
            cursor += 1;
            closed = true;
            break;
          }
          if (ch == '\\') {
            if (cursor + 1 >= len) {
              fail(CssTokenizeStatus::kBadEscape, cursor);
              return result;
            }
            uint8_t next = data[cursor + 1];
            if (next == '\n' || next == '\r' || next == '\f') {
              cursor += 2;
              if (cursor < len && next == '\r' && data[cursor] == '\n') {
                cursor += 1;
              }
              continue;
            }
            cursor += 2;
            continue;
          }
          if (ch == 0) {
            fail(CssTokenizeStatus::kInvalidByte, cursor);
            return result;
          }
          cursor += 1;
        }
        if (!closed) {
          fail(CssTokenizeStatus::kUnclosedString, start);
          return result;
        }
        if (!record_token(static_cast<uint32_t>(cursor - start), cursor)) {
          return result;
        }
        continue;
      }

      if (b == '#') {
        size_t start = cursor;
        cursor += 1;
        while (cursor < len && is_ident(data[cursor])) {
          cursor += 1;
        }
        if (!record_token(static_cast<uint32_t>(cursor - start), cursor)) {
          return result;
        }
        continue;
      }

      if (is_ident_start(b)) {
        if (b == '-') {
          if (cursor + 1 >= len || !is_ident(data[cursor + 1])) {
            if (!record_token(1, cursor + 1)) {
              return result;
            }
            continue;
          }
        }
        size_t start = cursor;
        cursor += 1;
        while (cursor < len && is_ident(data[cursor])) {
          cursor += 1;
        }
        if (!record_token(static_cast<uint32_t>(cursor - start), cursor)) {
          return result;
        }
        continue;
      }

      if (!record_token(1, cursor + 1)) {
        return result;
      }
    }

    result.status = CssTokenizeStatus::kOk;
    result.token_count = token_count;
    result.max_token_length = observed_max_token_length;
    result.bytes_consumed = len;
    return result;
  }

 private:
  CssTokenizeOptions options_;
  bool options_valid_;
};

}  // namespace chromium_rust_perf

#endif  // CHROMIUM_RUST_PERF_CSS_TOKENIZER_BASELINE_H_