#include <iostream>
#include <chrono>
#include <string_view>
#include <iomanip>
#include <cstring>
#include "cpp/http_header_scanner_adapter.h"

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

void RunBenchmark(const char* name, const uint8_t* data, size_t len, size_t iterations) {
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

    // Rust Benchmark
    auto start_rust = std::chrono::high_resolution_clock::now();
    for (size_t i = 0; i < iterations; ++i) {
        auto r = rust_scanner.Scan(data, len);
        Keep(r.header_end_offset);
    }
    auto end_rust = std::chrono::high_resolution_clock::now();
    std::chrono::duration<double, std::nano> elapsed_rust = end_rust - start_rust;
    double avg_rust = elapsed_rust.count() / iterations;

    // C++ Baseline Benchmark
    auto start_cpp = std::chrono::high_resolution_clock::now();
    for (size_t i = 0; i < iterations; ++i) {
        auto r = cpp_scanner.Scan(data, len);
        Keep(r.header_end_offset);
    }
    auto end_cpp = std::chrono::high_resolution_clock::now();
    std::chrono::duration<double, std::nano> elapsed_cpp = end_cpp - start_cpp;
    double avg_cpp = elapsed_cpp.count() / iterations;

    double ratio = avg_cpp / avg_rust;

    std::cout << "| " << std::left << std::setw(20) << name
              << " | " << std::right << std::setw(12) << std::fixed << std::setprecision(2) << avg_rust << " ns"
              << " | " << std::right << std::setw(12) << std::fixed << std::setprecision(2) << avg_cpp << " ns"
              << " | " << std::right << std::setw(10) << std::fixed << std::setprecision(2) << ratio << "x |" << std::endl;
}

int main() {
    std::cout << "================================================================" << std::endl;
    std::cout << "               Chromium Rust FFI Microbenchmark                 " << std::endl;
    std::cout << "================================================================" << std::endl;
    std::cout << "| " << std::left << std::setw(20) << "Payload"
              << " | " << std::right << std::setw(15) << "Rust (FFI)"
              << " | " << std::right << std::setw(15) << "C++ Baseline"
              << " | " << std::right << std::setw(12) << "Speedup" << " |" << std::endl;
    std::cout << "|----------------------|-----------------|-----------------|--------------|" << std::endl;

    size_t iterations = 1000000;
    
    RunBenchmark("Small Header", reinterpret_cast<const uint8_t*>(SMALL_PAYLOAD), std::strlen(SMALL_PAYLOAD), iterations);
    RunBenchmark("Large Header", reinterpret_cast<const uint8_t*>(LARGE_PAYLOAD), std::strlen(LARGE_PAYLOAD), iterations);
    RunBenchmark("Malformed Header", reinterpret_cast<const uint8_t*>(MALFORMED_PAYLOAD), std::strlen(MALFORMED_PAYLOAD), iterations);

    std::cout << "================================================================" << std::endl;
    // Print checksum to prevent compiler dead code elimination
    // (cast to void to suppress compiler warnings if any)
    (void)g_checksum;

    return 0;
}
