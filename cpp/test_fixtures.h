#ifndef CHROMIUM_RUST_PERF_TEST_FIXTURES_H_
#define CHROMIUM_RUST_PERF_TEST_FIXTURES_H_

#include <vector>
#include <string>
#include <cstdint>

struct HeaderFixture {
    std::string name;
    std::vector<uint8_t> data;
    uint32_t max_lines;
    uint32_t max_line_length;
};

struct UrlFixture {
    std::string name;
    std::vector<uint8_t> data;
};

inline std::vector<HeaderFixture> GetHeaderFixtures() {
    auto to_vec = [](const std::string& str) {
        return std::vector<uint8_t>(str.begin(), str.end());
    };
    return {
        {
            "Standard Request",
            to_vec("GET / HTTP/1.1\r\nHost: example.com\r\nUser-Agent: Chromium\r\n\r\n"),
            10, 100
        },
        {
            "Response with Cookies",
            to_vec("HTTP/1.1 200 OK\r\nContent-Type: text/html\r\nSet-Cookie: a=1; Path=/\r\nSet-Cookie: b=2; Secure\r\n\r\n"),
            20, 200
        },
        {
            "Folded Header Line",
            to_vec("Host: example.com\r\nX-Folded: value\r\n continued\r\n\r\n"),
            10, 100
        },
        {
            "Malformed Header (Bare LF)",
            to_vec("Host: example.com\n\r\n"),
            5, 50
        },
        {
            "Header line too long",
            to_vec("Host: abcdefghijklmnopqrstuvwxyz\r\n\r\n"),
            5, 10
        }
    };
}

inline std::vector<UrlFixture> GetUrlFixtures() {
    auto to_vec = [](const std::string& str) {
        return std::vector<uint8_t>(str.begin(), str.end());
    };
    return {
        {
            "Simple HTTP URL",
            to_vec("http://example.com/")
        },
        {
            "URL with username and password",
            to_vec("https://user:pass@host.com:8080/")
        },
        {
            "IPv6 URL",
            to_vec("http://[2001:db8::1]:80/")
        },
        {
            "URL with Percent Encoding",
            to_vec("http://example.com/foo%20bar%2f%41")
        },
        {
            "URL with control chars",
            to_vec("http://example.com/\x01\t\n/")
        },
        {
            "URL with invalid UTF-8",
            std::vector<uint8_t>{'h','t','t','p',':','/','/','e','x','a','m','p','l','e','.','c','o','m','/', 0xff, 0xfe}
        }
    };
}

#endif // CHROMIUM_RUST_PERF_TEST_FIXTURES_H_
