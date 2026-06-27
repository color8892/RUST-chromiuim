// Copyright 2026 The Chromium Authors
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

#ifndef INCLUDE_CHROMIUM_RUST_PERF_MOJO_VALIDATOR_FFI_H_
#define INCLUDE_CHROMIUM_RUST_PERF_MOJO_VALIDATOR_FFI_H_

#include <cstdint>
#include <cstddef>

namespace chromium_rust_perf {

struct MojoFieldConstraint {
    uint32_t offset;
    uint32_t expected_size;
    uint32_t is_nullable;
};

struct MojoMethodConstraint {
    uint32_t method_id;
    uint32_t expected_payload_size;
    const MojoFieldConstraint* field_constraints;
    uint32_t field_count;
};

struct MojoSchemaTable {
    const MojoMethodConstraint* methods;
    uint32_t method_count;
};

enum class MojoValidateStatus : uint32_t {
    kOk = 0,
    kNullInput = 1,
    kMessageTooShort = 2,
    kInvalidHeaderSize = 3,
    kUnknownMethod = 4,
    kPayloadTooShort = 5,
    kFieldOutOfBounds = 6,
    kInvalidAlignment = 7,
};

struct MojoValidateResult {
    uint32_t status;
    uint32_t error_offset;

    bool ok() const noexcept {
        return status == static_cast<uint32_t>(MojoValidateStatus::kOk);
    }
};

} // namespace chromium_rust_perf

extern "C" {

uint32_t chromium_rust_mojo_validate_v1(
    const uint8_t* data,
    size_t len,
    const chromium_rust_perf::MojoSchemaTable* schema,
    chromium_rust_perf::MojoValidateResult* out
);

// FFI callback types for Task Runner Executor
typedef void (*ChromiumCallback)(void* user_data);
typedef uint32_t (*PostTaskFn)(void* runner, ChromiumCallback callback, void* user_data);

void chromium_rust_async_executor_init(
    void* runner,
    PostTaskFn post_fn
);

uint32_t chromium_rust_async_executor_test_run(
    size_t yield_count
);

ptrdiff_t chromium_rust_mojo_writer_test(
    uint8_t* buf,
    size_t buf_len,
    uint32_t method_id,
    size_t field_offset,
    uint32_t field_val
);

int64_t chromium_rust_mojo_reader_test(
    const uint8_t* data,
    size_t len,
    size_t field_offset
);

ptrdiff_t chromium_rust_mojo_writer_string_test(
    uint8_t* buf,
    size_t buf_len,
    uint32_t method_id,
    size_t field_offset,
    const uint8_t* str_ptr,
    size_t str_len
);

ptrdiff_t chromium_rust_mojo_reader_string_test(
    const uint8_t* data,
    size_t len,
    size_t field_offset,
    uint8_t* out_buf,
    size_t out_len
);

ptrdiff_t chromium_rust_mojo_writer_array_u32_test(
    uint8_t* buf,
    size_t buf_len,
    uint32_t method_id,
    size_t field_offset,
    const uint32_t* array_ptr,
    size_t array_len
);

ptrdiff_t chromium_rust_mojo_reader_array_u32_test(
    const uint8_t* data,
    size_t len,
    size_t field_offset,
    uint32_t* out_array,
    size_t out_len
);

}

#endif // INCLUDE_CHROMIUM_RUST_PERF_MOJO_VALIDATOR_FFI_H_
