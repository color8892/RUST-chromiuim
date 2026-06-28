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

struct CssFixture {
    std::string name;
    std::vector<uint8_t> data;
    uint32_t max_tokens;
    uint32_t max_token_length;
};

struct CookieFixture {
    std::string name;
    std::vector<uint8_t> data;
    uint32_t max_attributes;
    uint32_t max_attr_name_length;
    uint32_t max_attr_value_length;
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

inline std::vector<CssFixture> GetCssFixtures() {
    auto to_vec = [](const std::string& str) {
        return std::vector<uint8_t>(str.begin(), str.end());
    };
    return {
        {
            "Simple rule",
            to_vec(".box { color: red; }"),
            64,
            128
        },
        {
            "Comment and string",
            to_vec("/* note */ .title { content: \"hi\"; }"),
            64,
            128
        },
        {
            "Hash selector",
            to_vec("#main { display: block; }"),
            64,
            128
        },
        {
            "Unclosed string",
            to_vec(".bad { content: \"oops"),
            64,
            128
        },
        {
            "Token limit",
            to_vec("a b c d e f g h"),
            3,
            32
        }
    };
}

inline std::vector<CookieFixture> GetCookieFixtures() {
    auto to_vec = [](const std::string& str) {
        return std::vector<uint8_t>(str.begin(), str.end());
    };
    return {
        {
            "Session cookie",
            to_vec("session_id=abc123; Path=/; Secure; HttpOnly; SameSite=Strict"),
            16,
            64,
            256
        },
        {
            "Quoted value",
            to_vec("token=\"quoted value\"; Path=/"),
            16,
            64,
            256
        },
        {
            "Name only",
            to_vec("flag"),
            16,
            64,
            256
        },
        {
            "Unclosed quote",
            to_vec("name=\"oops"),
            16,
            64,
            256
        },
        {
            "Attribute limit",
            to_vec("a=1; b=2; c=3; d=4"),
            2,
            64,
            256
        }
    };
}

#endif // CHROMIUM_RUST_PERF_TEST_FIXTURES_H_
