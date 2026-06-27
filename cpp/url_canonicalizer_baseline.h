#ifndef CHROMIUM_RUST_PERF_URL_CANONICALIZER_BASELINE_H_
#define CHROMIUM_RUST_PERF_URL_CANONICALIZER_BASELINE_H_

#include <string_view>
#include <cstdint>
#include <cstddef>
#include "cpp/url_canonicalizer_adapter.h"

namespace chromium_rust_perf {

class CppBaselineUrlScanner {
public:
    static UrlScanResult Scan(const uint8_t* data, size_t len) noexcept {
        UrlScanResult result;
        if (len > 9223372036854775807ULL) {
            result.status = UrlScanStatus::kLengthOverflow;
            return result;
        }
        if (len == 0) {
            result.status = UrlScanStatus::kOk;
            return result;
        }
        if (!data) {
            result.status = UrlScanStatus::kNullInput;
            return result;
        }

        std::string_view url(reinterpret_cast<const char*>(data), len);
        size_t cursor = 0;

        // 1. Scheme
        size_t colon_idx = std::string_view::npos;
        for (size_t i = 0; i < len; ++i) {
            char c = url[i];
            if (c == ':') {
                colon_idx = i;
                break;
            }
            if (c == '/' || c == '?' || c == '#') {
                break;
            }
        }

        bool authority_start = false;
        if (colon_idx != std::string_view::npos) {
            bool valid = colon_idx > 0;
            if (valid) {
                char first = url[0];
                if (!((first >= 'a' && first <= 'z') || (first >= 'A' && first <= 'Z'))) {
                    valid = false;
                }
                for (size_t i = 1; i < colon_idx; ++i) {
                    char c = url[i];
                    if (!((c >= 'a' && c <= 'z') || (c >= 'A' && c <= 'Z') || (c >= '0' && c <= '9') || c == '+' || c == '-' || c == '.')) {
                        valid = false;
                        break;
                    }
                }
            }
            if (!valid) {
                result.status = UrlScanStatus::kInvalidScheme;
                return result;
            }
            result.scheme = url.substr(0, colon_idx);
            cursor = colon_idx + 1;

            if (cursor + 1 < len && url[cursor] == '/' && url[cursor + 1] == '/') {
                cursor += 2;
                authority_start = true;
            }
        } else {
            if (len >= 2 && url[0] == '/' && url[1] == '/') {
                cursor = 2;
                authority_start = true;
            }
        }

        // 2. Authority
        if (authority_start) {
            size_t auth_end = len;
            for (size_t i = cursor; i < len; ++i) {
                char c = url[i];
                if (c == '/' || c == '?' || c == '#') {
                    auth_end = i;
                    break;
                }
            }

            std::string_view auth = url.substr(cursor, auth_end - cursor);
            if (!auth.empty()) {
                size_t at_idx = auth.find('@');
                std::string_view hp = auth;
                size_t hp_offset = cursor;

                if (at_idx != std::string_view::npos) {
                    std::string_view userinfo = auth.substr(0, at_idx);
                    size_t user_colon = userinfo.find(':');
                    if (user_colon != std::string_view::npos) {
                        result.username = url.substr(cursor, user_colon);
                        result.password = url.substr(cursor + user_colon + 1, userinfo.length() - user_colon - 1);
                    } else {
                        result.username = url.substr(cursor, userinfo.length());
                    }
                    hp = auth.substr(at_idx + 1);
                    hp_offset = cursor + at_idx + 1;
                }

                if (!hp.empty()) {
                    size_t last_colon = std::string_view::npos;
                    for (size_t j = hp.length(); j > 0; --j) {
                        size_t idx = j - 1;
                        if (hp[idx] == ':') {
                            bool inside_brackets = false;
                            bool has_bracket_end = false;
                            for (size_t k = idx; k < hp.length(); ++k) {
                                if (hp[k] == ']') {
                                    has_bracket_end = true;
                                    break;
                                }
                            }
                            for (size_t k = 0; k < idx; ++k) {
                                if (hp[k] == '[') {
                                    if (has_bracket_end) {
                                        inside_brackets = true;
                                    }
                                    break;
                                }
                            }
                            if (!inside_brackets) {
                                last_colon = idx;
                                break;
                            }
                        }
                    }

                    std::string_view host_str = hp;
                    if (last_colon != std::string_view::npos) {
                        std::string_view port_str = hp.substr(last_colon + 1);
                        if (!port_str.empty()) {
                            uint32_t val = 0;
                            bool valid_port = true;
                            for (char c : port_str) {
                                if (c >= '0' && c <= '9') {
                                    val = val * 10 + (c - '0');
                                    if (val > 65535) {
                                        valid_port = false;
                                    }
                                } else {
                                    valid_port = false;
                                    break;
                                }
                            }
                            if (valid_port) {
                                result.port = static_cast<int32_t>(val);
                            } else {
                                UrlScanResult err_res;
                                err_res.status = UrlScanStatus::kInvalidPort;
                                return err_res;
                            }
                        }
                        host_str = hp.substr(0, last_colon);
                    }

                    for (char c : host_str) {
                        unsigned char uc = static_cast<unsigned char>(c);
                        if (uc <= 32 || uc >= 127 || uc == '/' || uc == '?' || uc == '#') {
                            UrlScanResult err_res;
                            err_res.status = UrlScanStatus::kInvalidHost;
                            return err_res;
                        }
                    }
                    result.host = url.substr(hp_offset, host_str.length());
                }
            }
            cursor = auth_end;
        }

        // 3. Path, Query, Fragment
        if (cursor < len && url[cursor] == '/') {
            size_t path_end = len;
            for (size_t i = cursor; i < len; ++i) {
                char c = url[i];
                if (c == '?' || c == '#') {
                    path_end = i;
                    break;
                }
            }
            result.path = url.substr(cursor, path_end - cursor);
            cursor = path_end;
        } else if (cursor < len && url[cursor] != '?' && url[cursor] != '#') {
            size_t path_end = len;
            for (size_t i = cursor; i < len; ++i) {
                char c = url[i];
                if (c == '?' || c == '#') {
                    path_end = i;
                    break;
                }
            }
            result.path = url.substr(cursor, path_end - cursor);
            cursor = path_end;
        }

        if (cursor < len && url[cursor] == '?') {
            size_t query_end = len;
            for (size_t i = cursor + 1; i < len; ++i) {
                if (url[i] == '#') {
                    query_end = i;
                    break;
                }
            }
            result.query = url.substr(cursor + 1, query_end - cursor - 1);
            cursor = query_end;
        }

        if (cursor < len && url[cursor] == '#') {
            result.fragment = url.substr(cursor + 1, len - cursor - 1);
        }

        result.status = UrlScanStatus::kOk;
        return result;
    }

    static ptrdiff_t CanonicalizeHost(const uint8_t* host_data, size_t host_len, uint8_t* out_data, size_t out_max_len) noexcept {
        if (host_len > out_max_len) {
            return -1;
        }
        for (size_t i = 0; i < host_len; ++i) {
            uint8_t b = host_data[i];
            if (b <= 32 || b >= 127 || b == '/' || b == '?' || b == '#') {
                return -1;
            }
            if (b >= 'A' && b <= 'Z') {
                out_data[i] = b - 'A' + 'a';
            } else {
                out_data[i] = b;
            }
        }
        return static_cast<ptrdiff_t>(host_len);
    }

    static ptrdiff_t PercentDecodeSafe(const uint8_t* in_data, size_t in_len, uint8_t* out_data, size_t out_max_len) noexcept {
        size_t in_idx = 0;
        size_t out_idx = 0;

        auto hex_val = [](uint8_t c) -> int {
            if (c >= '0' && c <= '9') return c - '0';
            if (c >= 'a' && c <= 'f') return c - 'a' + 10;
            if (c >= 'A' && c <= 'F') return c - 'A' + 10;
            return -1;
        };

        while (in_idx < in_len) {
            uint8_t b = in_data[in_idx];
            if (b == '%') {
                if (in_idx + 2 < in_len) {
                    int d1 = hex_val(in_data[in_idx + 1]);
                    int d2 = hex_val(in_data[in_idx + 2]);
                    if (d1 >= 0 && d2 >= 0) {
                        uint8_t decoded = static_cast<uint8_t>((d1 << 4) | d2);
                        bool is_alnum = (decoded >= '0' && decoded <= '9') ||
                                        (decoded >= 'a' && decoded <= 'z') ||
                                        (decoded >= 'A' && decoded <= 'Z') ||
                                        decoded == '-' || decoded == '.' ||
                                        decoded == '_' || decoded == '~';
                        if (is_alnum) {
                            if (out_idx < out_max_len) {
                                out_data[out_idx++] = decoded;
                            } else {
                                return -1;
                            }
                        } else {
                            if (out_idx + 2 < out_max_len) {
                                out_data[out_idx++] = '%';
                                out_data[out_idx++] = in_data[in_idx + 1];
                                out_data[out_idx++] = in_data[in_idx + 2];
                            } else {
                                return -1;
                            }
                        }
                        in_idx += 3;
                        continue;
                    }
                }
                return -1;
            } else {
                if (out_idx < out_max_len) {
                    out_data[out_idx++] = b;
                } else {
                    return -1;
                }
                in_idx += 1;
            }
        }
        return static_cast<ptrdiff_t>(out_idx);
    }
};

} // namespace chromium_rust_perf

#endif // CHROMIUM_RUST_PERF_URL_CANONICALIZER_BASELINE_H_
