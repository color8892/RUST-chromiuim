#include <iostream>
#include <chrono>
#include <string_view>
#include <iomanip>
#include <cstring>
#include <fstream>
#include <algorithm>
#include <vector>
#include "cpp/http_header_scanner_adapter.h"
#include "cpp/url_canonicalizer_adapter.h"
#include "cpp/url_canonicalizer_baseline.h"
#include "cpp/mojo_validator_adapter.h"
#include "cpp/mojo_validator_baseline.h"
#include "cpp/test_fixtures.h"

// Global checksum to prevent compiler from optimizing away benchmark loops
volatile uint64_t g_checksum = 0;

inline void Keep(uint64_t val) {
    g_checksum += val;
}

#include "cpp/http_header_scanner_baseline.h"

const char* SMALL_PAYLOAD = "Host: example.test\r\nConnection: close\r\n\r\n";

const char* LARGE_PAYLOAD = "Host: example.test\r\n"
"User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36\r\n"
"Accept: text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8\r\n"
"Accept-Encoding: gzip, deflate, br\r\n"
"Cookie: session_id=abc123xyz7890fe456; user_preference=dark_mode; tracking_consent=true; long_dummy_cookie_to_make_this_payload_large_for_benchmarking_purposes=1234567890abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ1234567890\r\n"
"\r\n";

const char* MALFORMED_PAYLOAD = "Host: example.test\nConnection: close\r\n\r\n";

struct BenchmarkResult {
    const char* name;
    double rust_ns;
    double cpp_ns;
    double speedup;
};

double Median(std::vector<double> values) {
    std::sort(values.begin(), values.end());
    return values[values.size() / 2];
}

double Best(const std::vector<double>& values) {
    return *std::min_element(values.begin(), values.end());
}

BenchmarkResult RunBenchmark(const char* name,
                             const uint8_t* data,
                             size_t len,
                             size_t iterations,
                             size_t samples) {
    using namespace chromium_rust_perf;
    
    HttpHeaderScanOptions options{100, 1000};
    HttpHeaderScanner rust_scanner(options);
    CppBaselineScanner cpp_scanner(100, 1000);

    // Warm up
    for (int i = 0; i < 1000; ++i) {
        auto r1 = rust_scanner.Scan(data, len);
        auto r2 = cpp_scanner.Scan(data, len);
        Keep(r1.header_end_offset + r2.header_end_offset);
    }

    std::vector<double> rust_samples;
    std::vector<double> cpp_samples;
    rust_samples.reserve(samples);
    cpp_samples.reserve(samples);

    for (size_t sample = 0; sample < samples; ++sample) {
        auto start_rust = std::chrono::high_resolution_clock::now();
        for (size_t i = 0; i < iterations; ++i) {
            auto r = rust_scanner.Scan(data, len);
            Keep(r.header_end_offset);
        }
        auto end_rust = std::chrono::high_resolution_clock::now();
        std::chrono::duration<double, std::nano> elapsed_rust = end_rust - start_rust;
        rust_samples.push_back(elapsed_rust.count() / iterations);

        auto start_cpp = std::chrono::high_resolution_clock::now();
        for (size_t i = 0; i < iterations; ++i) {
            auto r = cpp_scanner.Scan(data, len);
            Keep(r.header_end_offset);
        }
        auto end_cpp = std::chrono::high_resolution_clock::now();
        std::chrono::duration<double, std::nano> elapsed_cpp = end_cpp - start_cpp;
        cpp_samples.push_back(elapsed_cpp.count() / iterations);
    }

    const double avg_rust = Best(rust_samples);
    const double avg_cpp = Best(cpp_samples);
    const double ratio = avg_cpp / avg_rust;

    std::cout << "| " << std::left << std::setw(20) << name
              << " | " << std::right << std::setw(12) << std::fixed << std::setprecision(2) << avg_rust << " ns"
              << " | " << std::right << std::setw(12) << std::fixed << std::setprecision(2) << avg_cpp << " ns"
              << " | " << std::right << std::setw(10) << std::fixed << std::setprecision(2) << ratio << "x |" << std::endl;

    return BenchmarkResult{name, avg_rust, avg_cpp, ratio};
}

BenchmarkResult RunUrlBenchmark(const char* name,
                                 const uint8_t* data,
                                 size_t len,
                                 size_t iterations,
                                 size_t samples) {
    using namespace chromium_rust_perf;
    
    UrlScanner rust_scanner;

    // Warm up
    for (int i = 0; i < 1000; ++i) {
        auto r1 = rust_scanner.Scan(data, len);
        auto r2 = CppBaselineUrlScanner::Scan(data, len);
        Keep(r1.status == UrlScanStatus::kOk || r2.status == UrlScanStatus::kOk);
    }

    std::vector<double> rust_samples;
    std::vector<double> cpp_samples;
    rust_samples.reserve(samples);
    cpp_samples.reserve(samples);

    for (size_t sample = 0; sample < samples; ++sample) {
        auto start_rust = std::chrono::high_resolution_clock::now();
        for (size_t i = 0; i < iterations; ++i) {
            auto r = rust_scanner.Scan(data, len);
            Keep(r.status == UrlScanStatus::kOk);
        }
        auto end_rust = std::chrono::high_resolution_clock::now();
        std::chrono::duration<double, std::nano> elapsed_rust = end_rust - start_rust;
        rust_samples.push_back(elapsed_rust.count() / iterations);

        auto start_cpp = std::chrono::high_resolution_clock::now();
        for (size_t i = 0; i < iterations; ++i) {
            auto r = CppBaselineUrlScanner::Scan(data, len);
            Keep(r.status == UrlScanStatus::kOk);
        }
        auto end_cpp = std::chrono::high_resolution_clock::now();
        std::chrono::duration<double, std::nano> elapsed_cpp = end_cpp - start_cpp;
        cpp_samples.push_back(elapsed_cpp.count() / iterations);
    }

    const double avg_rust = Best(rust_samples);
    const double avg_cpp = Best(cpp_samples);
    const double ratio = avg_cpp / avg_rust;

    std::cout << "| " << std::left << std::setw(20) << name
              << " | " << std::right << std::setw(12) << std::fixed << std::setprecision(2) << avg_rust << " ns"
              << " | " << std::right << std::setw(12) << std::fixed << std::setprecision(2) << avg_cpp << " ns"
              << " | " << std::right << std::setw(10) << std::fixed << std::setprecision(2) << ratio << "x |" << std::endl;

    return BenchmarkResult{name, avg_rust, avg_cpp, ratio};
}

BenchmarkResult RunMojoBenchmark(const char* name,
                                  const uint8_t* data,
                                  size_t len,
                                  const chromium_rust_perf::MojoSchemaTable* schema,
                                  size_t iterations,
                                  size_t samples) {
    using namespace chromium_rust_perf;
    
    MojoMessageValidator rust_validator;

    // Warm up
    for (int i = 0; i < 1000; ++i) {
        auto r1 = rust_validator.Validate(data, len, schema);
        auto r2 = CppBaselineMojoValidator::Validate(data, len, schema);
        Keep(r1.ok() || r2.ok());
    }

    std::vector<double> rust_samples;
    std::vector<double> cpp_samples;
    rust_samples.reserve(samples);
    cpp_samples.reserve(samples);

    for (size_t sample = 0; sample < samples; ++sample) {
        auto start_rust = std::chrono::high_resolution_clock::now();
        for (size_t i = 0; i < iterations; ++i) {
            auto r = rust_validator.Validate(data, len, schema);
            Keep(r.ok());
        }
        auto end_rust = std::chrono::high_resolution_clock::now();
        std::chrono::duration<double, std::nano> elapsed_rust = end_rust - start_rust;
        rust_samples.push_back(elapsed_rust.count() / iterations);

        auto start_cpp = std::chrono::high_resolution_clock::now();
        for (size_t i = 0; i < iterations; ++i) {
            auto r = CppBaselineMojoValidator::Validate(data, len, schema);
            Keep(r.ok());
        }
        auto end_cpp = std::chrono::high_resolution_clock::now();
        std::chrono::duration<double, std::nano> elapsed_cpp = end_cpp - start_cpp;
        cpp_samples.push_back(elapsed_cpp.count() / iterations);
    }

    const double avg_rust = Best(rust_samples);
    const double avg_cpp = Best(cpp_samples);
    const double ratio = avg_cpp / avg_rust;

    std::cout << "| " << std::left << std::setw(20) << name
              << " | " << std::right << std::setw(12) << std::fixed << std::setprecision(2) << avg_rust << " ns"
              << " | " << std::right << std::setw(12) << std::fixed << std::setprecision(2) << avg_cpp << " ns"
              << " | " << std::right << std::setw(10) << std::fixed << std::setprecision(2) << ratio << "x |" << std::endl;

    return BenchmarkResult{name, avg_rust, avg_cpp, ratio};
}

void WriteJsonString(std::ofstream& out, const char* value) {
    out << '"';
    for (const char* cursor = value; *cursor != '\0'; ++cursor) {
        switch (*cursor) {
            case '\\':
                out << "\\\\";
                break;
            case '"':
                out << "\\\"";
                break;
            default:
                out << *cursor;
                break;
        }
    }
    out << '"';
}

bool WriteJsonReport(const char* path,
                     const std::vector<BenchmarkResult>& results,
                     size_t iterations) {
    std::ofstream out(path, std::ios::out | std::ios::trunc);
    if (!out) {
        return false;
    }

    out << "{\n";
    out << "  \"iterations\": " << iterations << ",\n";
    out << "  \"benchmarks\": [\n";
    out << std::fixed << std::setprecision(4);
    for (size_t i = 0; i < results.size(); ++i) {
        const BenchmarkResult& result = results[i];
        out << "    {\"name\": ";
        WriteJsonString(out, result.name);
        out << ", \"rust_ns\": " << result.rust_ns
            << ", \"cpp_ns\": " << result.cpp_ns
            << ", \"speedup\": " << result.speedup << "}";
        if (i + 1 < results.size()) {
            out << ",";
        }
        out << "\n";
    }
    out << "  ]\n";
    out << "}\n";
    return true;
}

int main(int argc, char** argv) {
    const char* json_output = nullptr;
    size_t samples = 7;
    const char* mode = "header";

    for (int i = 1; i < argc; ++i) {
        if (std::strcmp(argv[i], "--json") == 0 && i + 1 < argc) {
            json_output = argv[++i];
        } else if (std::strcmp(argv[i], "--samples") == 0 && i + 1 < argc) {
            samples = static_cast<size_t>(std::strtoull(argv[++i], nullptr, 10));
            if (samples == 0) {
                std::cerr << "--samples must be greater than zero" << std::endl;
                return 2;
            }
        } else if (std::strcmp(argv[i], "--mode") == 0 && i + 1 < argc) {
            mode = argv[++i];
        } else {
            std::cerr << "Usage: " << argv[0] << " [--json output.json] [--samples N] [--mode header|url|mojo]" << std::endl;
            return 2;
        }
    }

    std::cout << "================================================================" << std::endl;
    std::cout << "               Chromium Rust FFI Microbenchmark                 " << std::endl;
    std::cout << "================================================================" << std::endl;
    std::cout << "| " << std::left << std::setw(20) << "Payload"
              << " | " << std::right << std::setw(15) << "Rust (FFI)"
              << " | " << std::right << std::setw(15) << "C++ Baseline"
              << " | " << std::right << std::setw(12) << "Speedup" << " |" << std::endl;
    std::cout << "|----------------------|-----------------|-----------------|--------------|" << std::endl;

    size_t iterations = 1000000;
    std::vector<BenchmarkResult> results;

    if (std::strcmp(mode, "header") == 0) {
        results.push_back(RunBenchmark("Small Header", reinterpret_cast<const uint8_t*>(SMALL_PAYLOAD), std::strlen(SMALL_PAYLOAD), iterations, samples));
        results.push_back(RunBenchmark("Large Header", reinterpret_cast<const uint8_t*>(LARGE_PAYLOAD), std::strlen(LARGE_PAYLOAD), iterations, samples));
        results.push_back(RunBenchmark("Malformed Header", reinterpret_cast<const uint8_t*>(MALFORMED_PAYLOAD), std::strlen(MALFORMED_PAYLOAD), iterations, samples));
    } else if (std::strcmp(mode, "url") == 0) {
        const char* SMALL_URL = "https://google.com/";
        const char* LARGE_URL = "https://user:pass@google.com:8080/path/to/file?q=1#hash";
        const char* MALFORMED_URL = "https://invalid_host:99999/";
        results.push_back(RunUrlBenchmark("Small URL", reinterpret_cast<const uint8_t*>(SMALL_URL), std::strlen(SMALL_URL), iterations, samples));
        results.push_back(RunUrlBenchmark("Large URL", reinterpret_cast<const uint8_t*>(LARGE_URL), std::strlen(LARGE_URL), iterations, samples));
        results.push_back(RunUrlBenchmark("Malformed URL", reinterpret_cast<const uint8_t*>(MALFORMED_URL), std::strlen(MALFORMED_URL), iterations, samples));
    } else if (std::strcmp(mode, "mojo") == 0) {
        using namespace chromium_rust_perf;
        std::vector<uint8_t> valid_mojo(40, 0);
        uint32_t header_size = 24;
        std::memcpy(&valid_mojo[0], &header_size, 4);
        uint32_t method_id = 100;
        std::memcpy(&valid_mojo[12], &method_id, 4);

        std::vector<uint8_t> malformed_mojo(20, 0);
        std::memcpy(&malformed_mojo[0], &header_size, 4);

        MojoFieldConstraint mojo_fields[] = {
            {0, 4, 0},
            {4, 8, 1}
        };
        MojoMethodConstraint mojo_methods[] = {
            {100, 16, mojo_fields, 2}
        };
        MojoSchemaTable mojo_schema = {mojo_methods, 1};

        results.push_back(RunMojoBenchmark("Valid Mojo", valid_mojo.data(), valid_mojo.size(), &mojo_schema, iterations, samples));
        results.push_back(RunMojoBenchmark("Malformed Mojo", malformed_mojo.data(), malformed_mojo.size(), &mojo_schema, iterations, samples));
    } else {
        std::cerr << "Unknown mode: " << mode << std::endl;
        return 2;
    }

    std::cout << "================================================================" << std::endl;
    if (json_output != nullptr) {
        if (!WriteJsonReport(json_output, results, iterations)) {
            std::cerr << "Failed to write JSON benchmark report: " << json_output << std::endl;
            return 1;
        }
        std::cout << "JSON report written to: " << json_output << std::endl;
    }

    (void)g_checksum;

    return 0;
}
