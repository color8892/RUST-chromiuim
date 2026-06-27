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

}

#endif // INCLUDE_CHROMIUM_RUST_PERF_MOJO_VALIDATOR_FFI_H_
