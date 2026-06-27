#include <iostream>
#include <string>
#include <string_view>
#include <vector>
#include <cstring>
#include <iomanip>
#include "cpp/http_header_scanner_adapter.h"
#include "cpp/http_header_scanner_baseline.h"
#include "cpp/url_canonicalizer_adapter.h"
#include "cpp/url_canonicalizer_baseline.h"

int g_test_count = 0;
int g_fail_count = 0;

#define EXPECT_EQ(actual, expected, context) \
    do { \
        g_test_count++; \
        if ((actual) != (expected)) { \
            std::cerr << "FAIL: " << (context) << " -> Line " << __LINE__ \
                      << " | Actual: " << (actual) << " | Expected: " << (expected) << std::endl; \
            g_fail_count++; \
        } \
    } while(0)

#define EXPECT_TRUE(cond, context) \
    do { \
        g_test_count++; \
        if (!(cond)) { \
            std::cerr << "FAIL: " << (context) << " -> Line " << __LINE__ \
                      << " | Expected condition to be true" << std::endl; \
            g_fail_count++; \
        } \
    } while(0)

// Helper to check if Rust and C++ baseline results are identical
void AssertIdentical(const char* test_name, const uint8_t* data, size_t len, uint32_t max_lines, uint32_t max_line_length) {
    using namespace chromium_rust_perf;

    HttpHeaderScanOptions options{max_lines, max_line_length};
    HttpHeaderScanner rust_scanner(options);
    CppBaselineScanner cpp_scanner(max_lines, max_line_length);

    HttpHeaderScanResult rust_res = rust_scanner.Scan(data, len);
    CppScanResult cpp_res = cpp_scanner.Scan(data, len);

    std::string context = std::string(test_name) + " (len=" + std::to_string(len) + ")";

    EXPECT_EQ(static_cast<uint32_t>(rust_res.status), static_cast<uint32_t>(cpp_res.status), context.c_str());
    EXPECT_EQ(rust_res.line_count, cpp_res.line_count, context.c_str());
    EXPECT_EQ(rust_res.max_line_length, cpp_res.max_line_length, context.c_str());
    EXPECT_EQ(rust_res.header_end_offset, cpp_res.header_end_offset, context.c_str());
    EXPECT_EQ(rust_res.ok(), (cpp_res.status == HttpHeaderScanStatus::kOk), context.c_str());
}

// 1. Core Unit Tests for specific API contracts
void RunUnitTests() {
    using namespace chromium_rust_perf;
    std::cout << "[Unit Tests] Running API contract checks..." << std::endl;

    // Test Ok Path
    {
        const char* p = "Host: example.test\r\nConnection: close\r\n\r\n";
        AssertIdentical("OkPath", reinterpret_cast<const uint8_t*>(p), std::strlen(p), 10, 100);
    }

    // Test Incomplete
    {
        const char* p = "Host: example.test\r\nConnection: close\r\n";
        AssertIdentical("IncompleteNoEnd", reinterpret_cast<const uint8_t*>(p), std::strlen(p), 10, 100);

        AssertIdentical("EmptyBuffer", nullptr, 0, 10, 100);
    }

    // Test Null Input
    {
        HttpHeaderScanOptions options{10, 100};
        HttpHeaderScanner rust_scanner(options);
        auto res = rust_scanner.Scan(nullptr, 10);
        EXPECT_EQ(static_cast<uint32_t>(res.status), static_cast<uint32_t>(HttpHeaderScanStatus::kNullInput), "NullInputTest");
    }

    // Test Length Overflow
    {
        HttpHeaderScanOptions options{10, 100};
        HttpHeaderScanner rust_scanner(options);
        // Pass negative value cast to size_t to exceed isize::MAX
        size_t overflow_len = static_cast<size_t>(-1);
        auto res = rust_scanner.Scan(nullptr, overflow_len);
        EXPECT_EQ(static_cast<uint32_t>(res.status), static_cast<uint32_t>(HttpHeaderScanStatus::kLengthOverflow), "LengthOverflowTest");
    }

    // Test Invalid Byte
    {
        const char* p = "Host: ex\0mple\r\n\r\n";
        AssertIdentical("NulByte", reinterpret_cast<const uint8_t*>(p), 14, 10, 100);
    }

    // Test Malformed Line Ending (Bare LF)
    {
        const char* p = "Host: ex\nConnection: close\r\n\r\n";
        AssertIdentical("BareLF", reinterpret_cast<const uint8_t*>(p), std::strlen(p), 10, 100);
    }

    // Test Malformed Line Ending (Bare CR)
    {
        const char* p = "Host: ex\rConnection: close\r\n\r\n";
        AssertIdentical("BareCR", reinterpret_cast<const uint8_t*>(p), std::strlen(p), 10, 100);
    }

    // Test Too Many Lines
    {
        const char* p = "A: 1\r\nB: 2\r\nC: 3\r\n\r\n";
        AssertIdentical("TooManyLinesLimit", reinterpret_cast<const uint8_t*>(p), std::strlen(p), 2, 100);
    }

    // Test Line Too Long
    {
        const char* p = "LongHeaderName: 123456\r\n\r\n";
        AssertIdentical("LineTooLongLimit", reinterpret_cast<const uint8_t*>(p), std::strlen(p), 10, 10);
    }

    // Test Invalid Policy
    {
        HttpHeaderScanOptions options{0, 100};
        HttpHeaderScanner rust_scanner(options);
        auto res = rust_scanner.Scan(reinterpret_cast<const uint8_t*>("A\r\n\r\n"), 5);
        EXPECT_EQ(static_cast<uint32_t>(res.status), static_cast<uint32_t>(HttpHeaderScanStatus::kInvalidPolicy), "InvalidPolicyLinesTest");

        HttpHeaderScanOptions options2{10, 0};
        HttpHeaderScanner rust_scanner2(options2);
        auto res2 = rust_scanner2.Scan(reinterpret_cast<const uint8_t*>("A\r\n\r\n"), 5);
        EXPECT_EQ(static_cast<uint32_t>(res2.status), static_cast<uint32_t>(HttpHeaderScanStatus::kInvalidPolicy), "InvalidPolicyLenTest");
    }
}

// 2. Differential Tests exploring prefix truncations and errors
void RunDifferentialTests() {
    std::cout << "[Differential Tests] Running prefix and mutation scans..." << std::endl;

    const char* base_headers = 
        "Host: example.test\r\n"
        "User-Agent: TestAgent/1.0\r\n"
        "Accept: */*\r\n"
        "Cookie: name=value; other=12345\r\n"
        "\r\n";
    
    size_t total_len = std::strlen(base_headers);
    const uint8_t* base_data = reinterpret_cast<const uint8_t*>(base_headers);

    // Scan every prefix of a valid header block
    for (size_t len = 0; len <= total_len; ++len) {
        AssertIdentical("TruncatedHeaderPrefix", base_data, len, 100, 1000);
    }

    // Mutate every single byte of the valid header block to invalid values (NUL, bare LF, bare CR)
    std::vector<uint8_t> mutated(base_data, base_data + total_len);
    for (size_t i = 0; i < total_len; ++i) {
        uint8_t original = mutated[i];

        // Mutation: NUL byte
        mutated[i] = 0;
        AssertIdentical("MutatedNul", mutated.data(), total_len, 100, 1000);

        // Mutation: Bare LF (unless original was CR/LF in which case it is tested as-is or elsewhere)
        if (original != '\r' && original != '\n') {
            mutated[i] = '\n';
            AssertIdentical("MutatedBareLF", mutated.data(), total_len, 100, 1000);

            mutated[i] = '\r';
            AssertIdentical("MutatedBareCR", mutated.data(), total_len, 100, 1000);
        }

        // Restore original
        mutated[i] = original;
    }
}

void TestRollbackMechanism() {
    using namespace chromium_rust_perf;
    std::cout << "[Rollback Tests] Running feature flag & fallback checks..." << std::endl;

    // Default should be false
    EXPECT_TRUE(!HttpHeaderScanner::IsRollbackEnabled(), "DefaultRollbackFalse");

    const char* p = "Host: example.test\r\nConnection: close\r\n\r\n";
    size_t len = std::strlen(p);
    HttpHeaderScanOptions options{10, 100};
    HttpHeaderScanner scanner(options);

    // 1. Rollback false (calls Rust FFI)
    auto res1 = scanner.Scan(reinterpret_cast<const uint8_t*>(p), len);
    EXPECT_EQ(static_cast<uint32_t>(res1.status), static_cast<uint32_t>(HttpHeaderScanStatus::kOk), "RollbackFalseOk");

    // 2. Enable Rollback (calls C++ Baseline)
    HttpHeaderScanner::SetRollbackEnabled(true);
    EXPECT_TRUE(HttpHeaderScanner::IsRollbackEnabled(), "RollbackTrueSet");
    auto res2 = scanner.Scan(reinterpret_cast<const uint8_t*>(p), len);
    EXPECT_EQ(static_cast<uint32_t>(res2.status), static_cast<uint32_t>(HttpHeaderScanStatus::kOk), "RollbackTrueOk");

    // 3. Disable Rollback (returns to Rust FFI)
    HttpHeaderScanner::SetRollbackEnabled(false);
    EXPECT_TRUE(!HttpHeaderScanner::IsRollbackEnabled(), "RollbackFalseReset");
    auto res3 = scanner.Scan(reinterpret_cast<const uint8_t*>(p), len);
    EXPECT_EQ(static_cast<uint32_t>(res3.status), static_cast<uint32_t>(HttpHeaderScanStatus::kOk), "RollbackFalseRestore");
}

void AssertUrlIdentical(const char* test_name, const uint8_t* data, size_t len) {
    using namespace chromium_rust_perf;
    UrlScanner rust_scanner;
    
    UrlScanResult rust_res = rust_scanner.Scan(data, len);
    UrlScanResult cpp_res = CppBaselineUrlScanner::Scan(data, len);

    std::string context = std::string(test_name) + " (len=" + std::to_string(len) + ")";

    EXPECT_EQ(static_cast<uint32_t>(rust_res.status), static_cast<uint32_t>(cpp_res.status), context.c_str());
    EXPECT_EQ(rust_res.scheme, cpp_res.scheme, context.c_str());
    EXPECT_EQ(rust_res.username, cpp_res.username, context.c_str());
    EXPECT_EQ(rust_res.password, cpp_res.password, context.c_str());
    EXPECT_EQ(rust_res.host, cpp_res.host, context.c_str());
    EXPECT_EQ(rust_res.port, cpp_res.port, context.c_str());
    EXPECT_EQ(rust_res.path, cpp_res.path, context.c_str());
    EXPECT_EQ(rust_res.query, cpp_res.query, context.c_str());
    EXPECT_EQ(rust_res.fragment, cpp_res.fragment, context.c_str());
    EXPECT_EQ(rust_res.ok(), cpp_res.ok(), context.c_str());
}

void RunUrlUnitTests() {
    using namespace chromium_rust_perf;
    std::cout << "[URL Unit Tests] Running basic API checks..." << std::endl;

    UrlScanner scanner;
    
    // 1. Valid URLs
    {
        auto res = scanner.Scan("http://example.com/path?q=1#hash");
        EXPECT_EQ(static_cast<uint32_t>(res.status), static_cast<uint32_t>(UrlScanStatus::kOk), "UrlValidStatus");
        EXPECT_EQ(res.scheme, "http", "UrlScheme");
        EXPECT_EQ(res.host, "example.com", "UrlHost");
        EXPECT_EQ(res.port, -1, "UrlPortMissing");
        EXPECT_EQ(res.path, "/path", "UrlPath");
        EXPECT_EQ(res.query, "q=1", "UrlQuery");
        EXPECT_EQ(res.fragment, "hash", "UrlFragment");
    }

    {
        auto res = scanner.Scan("https://user:pass@google.com:8080/foo");
        EXPECT_EQ(static_cast<uint32_t>(res.status), static_cast<uint32_t>(UrlScanStatus::kOk), "UrlUserInfoStatus");
        EXPECT_EQ(res.username, "user", "UrlUsername");
        EXPECT_EQ(res.password, "pass", "UrlPassword");
        EXPECT_EQ(res.host, "google.com", "UrlHostWithPort");
        EXPECT_EQ(res.port, 8080, "UrlPortParsed");
        EXPECT_EQ(res.path, "/foo", "UrlPathWithPort");
    }

    {
        auto res = scanner.Scan("http://[::1]:80/");
        EXPECT_EQ(static_cast<uint32_t>(res.status), static_cast<uint32_t>(UrlScanStatus::kOk), "UrlIPv6Status");
        EXPECT_EQ(res.host, "[::1]", "UrlIPv6Host");
        EXPECT_EQ(res.port, 80, "UrlIPv6Port");
    }

    // 2. Invalid URLs
    {
        auto res = scanner.Scan("http://example.com:99999/");
        EXPECT_EQ(static_cast<uint32_t>(res.status), static_cast<uint32_t>(UrlScanStatus::kInvalidPort), "UrlInvalidPortRange");
    }
    {
        auto res = scanner.Scan("http://example.com:80a/");
        EXPECT_EQ(static_cast<uint32_t>(res.status), static_cast<uint32_t>(UrlScanStatus::kInvalidPort), "UrlInvalidPortChars");
    }
    {
        auto res = scanner.Scan("http://ex ample.com/");
        EXPECT_EQ(static_cast<uint32_t>(res.status), static_cast<uint32_t>(UrlScanStatus::kInvalidHost), "UrlInvalidHostSpace");
    }
}

void RunUrlDifferentialTests() {
    using namespace chromium_rust_perf;
    std::cout << "[URL Differential Tests] Running prefix and mutation scans..." << std::endl;

    std::vector<std::string> seeds = {
        "http://example.com/path?q=1#hash",
        "https://user:pass@google.com:8080/foo/bar?key=val",
        "ftp://[2001:db8::1]:21/file.txt",
        "file:///C:/path/to/file",
        "mailto:user@example.com",
        "//schemeless-auth.test/path?query",
        "just-path/no-auth/file",
        "http://localhost:80/",
        "http://example.com:65535/"
    };

    for (const auto& seed : seeds) {
        size_t total_len = seed.length();
        const uint8_t* seed_bytes = reinterpret_cast<const uint8_t*>(seed.data());

        // Test all prefixes
        for (size_t len = 0; len <= total_len; ++len) {
            AssertUrlIdentical("PrefixTest", seed_bytes, len);
        }

        // Mutation: Single-byte corruptions
        std::vector<uint8_t> mutated(seed_bytes, seed_bytes + total_len);
        for (size_t i = 0; i < total_len; ++i) {
            uint8_t original = mutated[i];

            // Mutation: NUL byte
            mutated[i] = '\0';
            AssertUrlIdentical("MutatedNul", mutated.data(), total_len);

            // Mutation: Random invalid characters
            mutated[i] = ' ';
            AssertUrlIdentical("MutatedSpace", mutated.data(), total_len);

            mutated[i] = '/';
            AssertUrlIdentical("MutatedSlash", mutated.data(), total_len);

            mutated[i] = ':';
            AssertUrlIdentical("MutatedColon", mutated.data(), total_len);

            // Restore original
            mutated[i] = original;
        }
    }
}

void TestUrlRollbackMechanism() {
    using namespace chromium_rust_perf;
    std::cout << "[URL Rollback Tests] Running feature flag & fallback checks..." << std::endl;

    EXPECT_TRUE(!UrlScanner::IsRollbackEnabled(), "DefaultUrlRollbackFalse");

    const char* url = "http://example.com/path?q=1#hash";
    size_t len = std::strlen(url);
    UrlScanner scanner;

    // 1. Rollback false (calls Rust FFI)
    auto res1 = scanner.Scan(reinterpret_cast<const uint8_t*>(url), len);
    EXPECT_EQ(static_cast<uint32_t>(res1.status), static_cast<uint32_t>(UrlScanStatus::kOk), "UrlRollbackFalseOk");

    // 2. Enable Rollback (calls C++ Baseline)
    UrlScanner::SetRollbackEnabled(true);
    EXPECT_TRUE(UrlScanner::IsRollbackEnabled(), "UrlRollbackTrueSet");
    auto res2 = scanner.Scan(reinterpret_cast<const uint8_t*>(url), len);
    EXPECT_EQ(static_cast<uint32_t>(res2.status), static_cast<uint32_t>(UrlScanStatus::kOk), "UrlRollbackTrueOk");

    // 3. Disable Rollback (returns to Rust FFI)
    UrlScanner::SetRollbackEnabled(false);
    EXPECT_TRUE(!UrlScanner::IsRollbackEnabled(), "UrlRollbackFalseReset");
    auto res3 = scanner.Scan(reinterpret_cast<const uint8_t*>(url), len);
    EXPECT_EQ(static_cast<uint32_t>(res3.status), static_cast<uint32_t>(UrlScanStatus::kOk), "UrlRollbackFalseRestore");
}

int main() {
    std::cout << "================================================================" << std::endl;
    std::cout << "         Chromium Rust C++ & FFI Differential Tests             " << std::endl;
    std::cout << "================================================================" << std::endl;

    RunUnitTests();
    RunDifferentialTests();
    TestRollbackMechanism();

    RunUrlUnitTests();
    RunUrlDifferentialTests();
    TestUrlRollbackMechanism();

    std::cout << "================================================================" << std::endl;
    std::cout << "Tests Run: " << g_test_count << " | Failures: " << g_fail_count << std::endl;
    std::cout << "================================================================" << std::endl;

    return (g_fail_count == 0) ? 0 : 1;
}
