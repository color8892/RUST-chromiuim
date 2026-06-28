#ifndef CHROMIUM_RUST_PERF_COOKIE_CANONICALIZER_BASELINE_H_
#define CHROMIUM_RUST_PERF_COOKIE_CANONICALIZER_BASELINE_H_

#include <cstddef>
#include <cstdint>
#include <cstring>
#include "cpp/cookie_canonicalizer_adapter.h"

namespace chromium_rust_perf {

class CppBaselineCookieCanonicalizer {
 public:
  explicit CppBaselineCookieCanonicalizer(CookieCanonicalizeOptions options) noexcept
      : options_(options), options_valid_(options.IsValid()) {}

  [[nodiscard]] CookieCanonicalizeResult Canonicalize(const uint8_t* data,
                                                      size_t len) const noexcept {
    CookieCanonicalizeResult result;
    if (!options_valid_) {
      result.status = CookieCanonicalizeStatus::kInvalidPolicy;
      return result;
    }
    if (len > static_cast<size_t>(9223372036854775807LL)) {
      result.status = CookieCanonicalizeStatus::kLengthOverflow;
      return result;
    }
    if (len == 0) {
      result.status = CookieCanonicalizeStatus::kEmptyName;
      return result;
    }
    if (!data) {
      result.status = CookieCanonicalizeStatus::kNullInput;
      return result;
    }

    size_t cursor = 0;
    uint32_t attribute_count = 0;
    uint32_t observed_max_attr_name_length = 0;
    uint32_t observed_max_attr_value_length = 0;
    bool has_secure = false;
    bool has_httponly = false;
    CookieSameSite same_site = CookieSameSite::kNone;

    auto fail = [&](CookieCanonicalizeStatus status, size_t at) {
      result.status = status;
      result.attribute_count = attribute_count;
      result.max_attr_name_length = observed_max_attr_name_length;
      result.max_attr_value_length = observed_max_attr_value_length;
      result.has_secure = has_secure;
      result.has_httponly = has_httponly;
      result.same_site = same_site;
      result.bytes_consumed = at;
    };

    while (cursor < len && IsOws(data[cursor])) {
      cursor += 1;
    }
    if (cursor >= len) {
      fail(CookieCanonicalizeStatus::kEmptyName, cursor);
      return result;
    }

    size_t name_start = cursor;
    while (cursor < len) {
      uint8_t b = data[cursor];
      if (b == 0) {
        fail(CookieCanonicalizeStatus::kInvalidByte, cursor);
        return result;
      }
      if (!IsTokenChar(b)) {
        break;
      }
      cursor += 1;
    }
    if (cursor == name_start) {
      fail(CookieCanonicalizeStatus::kEmptyName, cursor);
      return result;
    }

    result.name = std::string_view(reinterpret_cast<const char*>(data + name_start),
                                   cursor - name_start);
    result.value = std::string_view();

    if (cursor < len && data[cursor] == '=') {
      cursor += 1;
      if (cursor >= len) {
        result.status = CookieCanonicalizeStatus::kOk;
        result.bytes_consumed = cursor;
        return result;
      }

      size_t value_start = cursor;
      if (data[cursor] == '"') {
        cursor += 1;
        bool closed = false;
        while (cursor < len) {
          uint8_t b = data[cursor];
          if (b == 0) {
            fail(CookieCanonicalizeStatus::kInvalidByte, cursor);
            return result;
          }
          if (b == '"') {
            cursor += 1;
            closed = true;
            break;
          }
          cursor += 1;
        }
        if (!closed) {
          result.value = std::string_view(reinterpret_cast<const char*>(data + value_start),
                                          cursor - value_start);
          fail(CookieCanonicalizeStatus::kUnclosedQuote, value_start);
          return result;
        }
        result.value = std::string_view(reinterpret_cast<const char*>(data + value_start + 1),
                                        cursor - value_start - 2);
      } else {
        while (cursor < len) {
          uint8_t b = data[cursor];
          if (b == 0) {
            fail(CookieCanonicalizeStatus::kInvalidByte, cursor);
            return result;
          }
          if (b == ';') {
            break;
          }
          cursor += 1;
        }
        result.value = std::string_view(reinterpret_cast<const char*>(data + value_start),
                                        cursor - value_start);
      }
    }

    result.bytes_consumed = cursor;

    while (cursor < len) {
      if (data[cursor] != ';') {
        fail(CookieCanonicalizeStatus::kInvalidName, cursor);
        return result;
      }
      cursor += 1;

      while (cursor < len && IsOws(data[cursor])) {
        cursor += 1;
      }
      if (cursor >= len) {
        fail(CookieCanonicalizeStatus::kIncomplete, cursor);
        return result;
      }

      size_t attr_start = cursor;
      while (cursor < len) {
        uint8_t b = data[cursor];
        if (b == 0) {
          fail(CookieCanonicalizeStatus::kInvalidByte, cursor);
          return result;
        }
        if (!IsTokenChar(b)) {
          break;
        }
        cursor += 1;
      }
      if (cursor == attr_start) {
        fail(CookieCanonicalizeStatus::kIncomplete, cursor);
        return result;
      }

      uint32_t attr_name_len = static_cast<uint32_t>(cursor - attr_start);
      if (attr_name_len > options_.max_attr_name_length) {
        fail(CookieCanonicalizeStatus::kAttrNameTooLong, attr_start);
        return result;
      }
      if (attr_name_len > observed_max_attr_name_length) {
        observed_max_attr_name_length = attr_name_len;
      }

      if (cursor < len && data[cursor] == '=') {
        cursor += 1;
        if (cursor >= len) {
          fail(CookieCanonicalizeStatus::kIncomplete, cursor);
          return result;
        }
        size_t value_start = cursor;
        while (cursor < len) {
          uint8_t b = data[cursor];
          if (b == 0) {
            fail(CookieCanonicalizeStatus::kInvalidByte, cursor);
            return result;
          }
          if (b == ';') {
            break;
          }
          cursor += 1;
        }
        uint32_t attr_value_len = static_cast<uint32_t>(cursor - value_start);
        if (attr_value_len > options_.max_attr_value_length) {
          fail(CookieCanonicalizeStatus::kAttrValueTooLong, value_start);
          return result;
        }
        if (attr_value_len > observed_max_attr_value_length) {
          observed_max_attr_value_length = attr_value_len;
        }

        if (AsciiEqIgnoreCase(data + attr_start, attr_name_len, "SameSite", 8)) {
          if (AsciiEqIgnoreCase(data + value_start, attr_value_len, "Strict", 6)) {
            same_site = CookieSameSite::kStrict;
          } else if (AsciiEqIgnoreCase(data + value_start, attr_value_len, "Lax", 3)) {
            same_site = CookieSameSite::kLax;
          } else if (AsciiEqIgnoreCase(data + value_start, attr_value_len, "None", 4)) {
            same_site = CookieSameSite::kNoneValue;
          } else {
            fail(CookieCanonicalizeStatus::kInvalidSameSite, value_start);
            return result;
          }
        }
      } else {
        if (AsciiEqIgnoreCase(data + attr_start, attr_name_len, "Secure", 6)) {
          has_secure = true;
        } else if (AsciiEqIgnoreCase(data + attr_start, attr_name_len, "HttpOnly", 8)) {
          has_httponly = true;
        }
      }

      if (attribute_count >= options_.max_attributes) {
        fail(CookieCanonicalizeStatus::kTooManyAttributes, attr_start);
        return result;
      }
      attribute_count += 1;
      result.bytes_consumed = cursor;
    }

    result.status = CookieCanonicalizeStatus::kOk;
    result.attribute_count = attribute_count;
    result.max_attr_name_length = observed_max_attr_name_length;
    result.max_attr_value_length = observed_max_attr_value_length;
    result.has_secure = has_secure;
    result.has_httponly = has_httponly;
    result.same_site = same_site;
    return result;
  }

 private:
  CookieCanonicalizeOptions options_;
  bool options_valid_;

  static bool IsCtl(uint8_t b) {
    return b < 0x20 || b == 0x7F;
  }

  static bool IsSeparator(uint8_t b) {
    switch (b) {
      case '(':
      case ')':
      case '<':
      case '>':
      case '@':
      case ',':
      case ';':
      case ':':
      case '\\':
      case '"':
      case '/':
      case '[':
      case ']':
      case '?':
      case '=':
      case '{':
      case '}':
      case ' ':
      case '\t':
        return true;
      default:
        return false;
    }
  }

  static bool IsTokenChar(uint8_t b) {
    return !IsCtl(b) && !IsSeparator(b);
  }

  static bool IsOws(uint8_t b) {
    return b == ' ' || b == '\t';
  }

  static bool AsciiEqIgnoreCase(const uint8_t* left,
                                size_t left_len,
                                const char* right,
                                size_t right_len) {
    if (left_len != right_len) {
      return false;
    }
    for (size_t i = 0; i < left_len; ++i) {
      uint8_t a = left[i];
      uint8_t b = static_cast<uint8_t>(right[i]);
      if (a >= 'A' && a <= 'Z') {
        a = static_cast<uint8_t>(a + 32);
      }
      if (b >= 'A' && b <= 'Z') {
        b = static_cast<uint8_t>(b + 32);
      }
      if (a != b) {
        return false;
      }
    }
    return true;
  }
};

}  // namespace chromium_rust_perf

#endif  // CHROMIUM_RUST_PERF_COOKIE_CANONICALIZER_BASELINE_H_