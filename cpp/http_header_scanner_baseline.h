#ifndef CHROMIUM_RUST_PERF_HTTP_HEADER_SCANNER_BASELINE_H_
#define CHROMIUM_RUST_PERF_HTTP_HEADER_SCANNER_BASELINE_H_

#include <cstdint>
#include <cstddef>
#include "cpp/http_header_scanner_adapter.h"

struct CppScanResult {
    chromium_rust_perf::HttpHeaderScanStatus status = chromium_rust_perf::HttpHeaderScanStatus::kIncomplete;
    uint32_t line_count = 0;
    uint32_t max_line_length = 0;
    size_t header_end_offset = 0;
};

class CppBaselineScanner {
public:
    CppBaselineScanner(uint32_t max_lines, uint32_t max_line_length)
        : max_lines_(max_lines), max_line_length_(max_line_length) {}

    CppScanResult Scan(const uint8_t* data, size_t len) const noexcept {
        using namespace chromium_rust_perf;

        // isize::MAX check
        if (len > 9223372036854775807ULL) {
            return CppScanResult{HttpHeaderScanStatus::kLengthOverflow, 0, 0, 0};
        }
        if (len == 0) {
            return CppScanResult{HttpHeaderScanStatus::kIncomplete, 0, 0, 0};
        }
        if (!data) {
            return CppScanResult{HttpHeaderScanStatus::kNullInput, 0, 0, 0};
        }

        size_t line_start = 0;
        size_t cursor = 0;
        uint32_t line_count = 0;
        uint32_t observed_max_line_length = 0;

        while (cursor < len) {
            uint8_t byte = data[cursor];
            if (byte == 0) {
                return CppScanResult{HttpHeaderScanStatus::kInvalidByte, 0, 0, 0};
            }
            if (byte == '\n') {
                return CppScanResult{HttpHeaderScanStatus::kMalformedLineEnding, 0, 0, 0};
            }
            if (byte != '\r') {
                cursor++;
                continue;
            }

            if (cursor + 1 >= len) {
                return CppScanResult{HttpHeaderScanStatus::kIncomplete, 0, 0, 0};
            }
            if (data[cursor + 1] != '\n') {
                return CppScanResult{HttpHeaderScanStatus::kMalformedLineEnding, 0, 0, 0};
            }

            size_t line_len = cursor - line_start;
            if (line_len > max_line_length_) {
                return CppScanResult{HttpHeaderScanStatus::kLineTooLong, 0, 0, 0};
            }

            if (line_len == 0) {
                return CppScanResult{
                    HttpHeaderScanStatus::kOk,
                    line_count,
                    observed_max_line_length,
                    cursor + 2
                };
            }

            if (line_count == max_lines_) {
                return CppScanResult{HttpHeaderScanStatus::kTooManyLines, 0, 0, 0};
            }

            line_count++;
            uint32_t line_len_u32 = (line_len > 0xFFFFFFFF) ? 0xFFFFFFFF : static_cast<uint32_t>(line_len);
            if (line_len_u32 > observed_max_line_length) {
                observed_max_line_length = line_len_u32;
            }

            cursor += 2;
            line_start = cursor;
        }

        return CppScanResult{HttpHeaderScanStatus::kIncomplete, 0, 0, 0};
    }

private:
    uint32_t max_lines_;
    uint32_t max_line_length_;
};

#endif // CHROMIUM_RUST_PERF_HTTP_HEADER_SCANNER_BASELINE_H_
