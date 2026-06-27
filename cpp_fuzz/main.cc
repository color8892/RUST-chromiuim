#include <iostream>
#include <vector>
#include <cstdlib>
#include <ctime>
#include <cstring>
#include <iomanip>
#include "cpp/http_header_scanner_adapter.h"
#include "cpp/url_canonicalizer_adapter.h"
#include "cpp/mojo_validator_adapter.h"

const char* SEED_HEADER = 
    "Host: example.test\r\n"
    "User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36\r\n"
    "Accept: text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8\r\n"
    "Cookie: session_id=12345abcde; tracking=consent\r\n"
    "\r\n";

const char* SEED_URL = "https://user:pass@google.com:8080/path/to/file?q=1#hash";

int main(int argc, char** argv) {
    using namespace chromium_rust_perf;

    std::cout << "================================================================" << std::endl;
    std::cout << "  Chromium Rust Local Mutation Fuzzer (Headers, URLs, & Mojo)   " << std::endl;
    std::cout << "================================================================" << std::endl;

    size_t header_seed_len = std::strlen(SEED_HEADER);
    std::vector<uint8_t> header_buf(header_seed_len + 500);

    size_t url_seed_len = std::strlen(SEED_URL);
    std::vector<uint8_t> url_buf(url_seed_len + 500);

    std::vector<uint8_t> mojo_buf(40 + 500);

    MojoFieldConstraint mojo_fields[] = {
        {0, 4, 0},
        {4, 8, 1}
    };
    MojoMethodConstraint mojo_methods[] = {
        {100, 16, mojo_fields, 2}
    };
    MojoSchemaTable mojo_schema = {mojo_methods, 1};

    // Use a fixed seed for reproducible fuzzing runs
    std::srand(12345);

    size_t target_runs = 5000000;
    for (int i = 1; i < argc; ++i) {
        if (std::strcmp(argv[i], "--runs") == 0 && i + 1 < argc) {
            target_runs = static_cast<size_t>(std::strtoull(argv[++i], nullptr, 10));
        }
    }
    size_t print_interval = (target_runs < 500000) ? (target_runs / 5) : 500000;
    if (print_interval == 0) {
        print_interval = 1;
    }

    size_t header_status_counts[10] = {0};
    size_t url_status_counts[10] = {0};
    size_t mojo_status_counts[10] = {0};

    std::cout << "Starting " << target_runs << " iterations of mutation fuzzing..." << std::endl;

    UrlScanner url_scanner;
    MojoMessageValidator mojo_validator;

    for (size_t run = 1; run <= target_runs; ++run) {
        // --- 1. Fuzz HTTP Header Scanner ---
        std::memcpy(header_buf.data(), SEED_HEADER, header_seed_len);
        size_t header_len = header_seed_len;

        int mutations = (std::rand() % 5) + 1;
        for (int m = 0; m < mutations; ++m) {
            int mutation_type = std::rand() % 5;
            switch (mutation_type) {
                case 0: {
                    if (header_len > 0) {
                        size_t idx = std::rand() % header_len;
                        header_buf[idx] = static_cast<uint8_t>(std::rand() % 256);
                    }
                    break;
                }
                case 1: {
                    header_len = std::rand() % (header_len + 1);
                    break;
                }
                case 2: {
                    if (header_len > 0) {
                        size_t idx = std::rand() % header_len;
                        uint8_t special_chars[] = {0, '\r', '\n', ':', ' ', '\t'};
                        header_buf[idx] = special_chars[std::rand() % 6];
                    }
                    break;
                }
                case 3: {
                    size_t append_len = std::rand() % 50;
                    if (header_len + append_len <= header_buf.size()) {
                        for (size_t i = 0; i < append_len; ++i) {
                            header_buf[header_len + i] = static_cast<uint8_t>(std::rand() % 256);
                        }
                        header_len += append_len;
                    }
                    break;
                }
                case 4: {
                    if (header_len > 4) {
                        size_t idx = std::rand() % (header_len - 3);
                        header_buf[idx] = '\r';
                        header_buf[idx+1] = '\n';
                        header_buf[idx+2] = '\r';
                        header_buf[idx+3] = '\n';
                    }
                    break;
                }
            }
        }

        uint32_t max_lines = (std::rand() % 100 == 0) ? 0 : (std::rand() % 200) + 1;
        uint32_t max_line_length = (std::rand() % 100 == 0) ? 0 : (std::rand() % 500) + 1;

        HttpHeaderScanOptions options{max_lines, max_line_length};
        HttpHeaderScanner header_scanner(options);

        HttpHeaderScanResult header_res = header_scanner.Scan(header_buf.data(), header_len);
        uint32_t h_status = static_cast<uint32_t>(header_res.status);
        if (h_status < 10) {
            header_status_counts[h_status]++;
        }

        // --- 2. Fuzz URL Parser ---
        std::memcpy(url_buf.data(), SEED_URL, url_seed_len);
        size_t url_len = url_seed_len;

        mutations = (std::rand() % 5) + 1;
        for (int m = 0; m < mutations; ++m) {
            int mutation_type = std::rand() % 5;
            switch (mutation_type) {
                case 0: {
                    if (url_len > 0) {
                        size_t idx = std::rand() % url_len;
                        url_buf[idx] = static_cast<uint8_t>(std::rand() % 256);
                    }
                    break;
                }
                case 1: {
                    url_len = std::rand() % (url_len + 1);
                    break;
                }
                case 2: {
                    if (url_len > 0) {
                        size_t idx = std::rand() % url_len;
                        uint8_t special_chars[] = {0, '/', '?', '#', ':', '@', ' ', '[', ']'};
                        url_buf[idx] = special_chars[std::rand() % 9];
                    }
                    break;
                }
                case 3: {
                    size_t append_len = std::rand() % 50;
                    if (url_len + append_len <= url_buf.size()) {
                        for (size_t i = 0; i < append_len; ++i) {
                            url_buf[url_len + i] = static_cast<uint8_t>(std::rand() % 256);
                        }
                        url_len += append_len;
                    }
                    break;
                }
                case 4: {
                    if (url_len > 3) {
                        size_t idx = std::rand() % (url_len - 2);
                        url_buf[idx] = ':';
                        url_buf[idx+1] = '/';
                        url_buf[idx+2] = '/';
                    }
                    break;
                }
            }
        }

        UrlScanResult url_res = url_scanner.Scan(url_buf.data(), url_len);
        uint32_t u_status = static_cast<uint32_t>(url_res.status);
        if (u_status < 10) {
            url_status_counts[u_status]++;
        }

        // --- 3. Fuzz Mojo Validator ---
        std::memset(mojo_buf.data(), 0, 40);
        uint32_t header_size = 24;
        std::memcpy(&mojo_buf[0], &header_size, 4);
        uint32_t method_id = 100;
        std::memcpy(&mojo_buf[12], &method_id, 4);
        size_t mojo_len = 40;

        mutations = (std::rand() % 5) + 1;
        for (int m = 0; m < mutations; ++m) {
            int mutation_type = std::rand() % 5;
            switch (mutation_type) {
                case 0: {
                    if (mojo_len > 0) {
                        size_t idx = std::rand() % mojo_len;
                        mojo_buf[idx] = static_cast<uint8_t>(std::rand() % 256);
                    }
                    break;
                }
                case 1: {
                    mojo_len = std::rand() % (mojo_len + 1);
                    break;
                }
                case 2: {
                    uint32_t bad_header_size = (std::rand() % 10 == 0) ? (std::rand() % 64) : 24;
                    std::memcpy(&mojo_buf[0], &bad_header_size, 4);
                    break;
                }
                case 3: {
                    uint32_t bad_method_id = (std::rand() % 10 == 0) ? (std::rand() % 200) : 100;
                    std::memcpy(&mojo_buf[12], &bad_method_id, 4);
                    break;
                }
                case 4: {
                    size_t append_len = std::rand() % 50;
                    if (mojo_len + append_len <= mojo_buf.size()) {
                        for (size_t i = 0; i < append_len; ++i) {
                            mojo_buf[mojo_len + i] = static_cast<uint8_t>(std::rand() % 256);
                        }
                        mojo_len += append_len;
                    }
                    break;
                }
            }
        }

        MojoValidateResult mojo_res = mojo_validator.Validate(mojo_buf.data(), mojo_len, &mojo_schema);
        uint32_t m_status = static_cast<uint32_t>(mojo_res.status);
        if (m_status < 10) {
            mojo_status_counts[m_status]++;
        }

        // Print progress
        if (run % print_interval == 0) {
            std::cout << "  -> Progress: " << std::right << std::setw(9) << run << " runs completed." << std::endl;
        }
    }

    std::cout << "================================================================" << std::endl;
    std::cout << "Fuzzing completed successfully! No crashes or unexpected panics." << std::endl;
    std::cout << "================================================================" << std::endl;
    
    std::cout << "Header Scanner Status Statistics:" << std::endl;
    const char* header_status_names[] = {
        "kOk                 ",
        "kIncomplete         ",
        "kNullInput          ",
        "kLengthOverflow     ",
        "kOutputNull         ",
        "kInvalidByte        ",
        "kMalformedLineEnding",
        "kTooManyLines       ",
        "kLineTooLong        ",
        "kInvalidPolicy      "
    };
    for (int i = 0; i < 10; ++i) {
        std::cout << "  - " << header_status_names[i] << ": " << header_status_counts[i] << std::endl;
    }

    std::cout << "\nURL Scanner Status Statistics:" << std::endl;
    const char* url_status_names[] = {
        "kOk                 ",
        "kNullInput          ",
        "kLengthOverflow     ",
        "kOutputNull         ",
        "kInvalidScheme      ",
        "kInvalidHost        ",
        "kInvalidPort        ",
        "unused7             ",
        "unused8             ",
        "unused9             "
    };
    for (int i = 0; i < 7; ++i) {
        std::cout << "  - " << url_status_names[i] << ": " << url_status_counts[i] << std::endl;
    }

    std::cout << "\nMojo Validator Status Statistics:" << std::endl;
    const char* mojo_status_names[] = {
        "kOk                 ",
        "kNullInput          ",
        "kMessageTooShort    ",
        "kInvalidHeaderSize  ",
        "kUnknownMethod      ",
        "kPayloadTooShort    ",
        "kFieldOutOfBounds   ",
        "kInvalidAlignment   ",
        "unused8             ",
        "unused9             "
    };
    for (int i = 0; i < 8; ++i) {
        std::cout << "  - " << mojo_status_names[i] << ": " << mojo_status_counts[i] << std::endl;
    }
    std::cout << "================================================================" << std::endl;

    return 0;
}
