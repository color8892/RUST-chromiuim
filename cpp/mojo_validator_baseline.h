// Copyright 2026 The Chromium Authors
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

#ifndef CPP_MOJO_VALIDATOR_BASELINE_H_
#define CPP_MOJO_VALIDATOR_BASELINE_H_

#include "include/chromium_rust_perf/mojo_validator_ffi.h"

namespace chromium_rust_perf {

class CppBaselineMojoValidator {
 public:
  static MojoValidateResult Validate(
      const uint8_t* data,
      size_t len,
      const MojoSchemaTable* schema) noexcept {
    
    if (!data || !schema) {
      MojoValidateResult res = {static_cast<uint32_t>(MojoValidateStatus::kNullInput), 0};
      return res;
    }

    if (len < 24) {
      MojoValidateResult res = {static_cast<uint32_t>(MojoValidateStatus::kMessageTooShort), static_cast<uint32_t>(len)};
      return res;
    }

    // Little endian read of header size (first 4 bytes)
    uint32_t header_num_bytes = data[0] | (data[1] << 8) | (data[2] << 16) | (data[3] << 24);

    if (header_num_bytes != 24 && header_num_bytes != 32) {
      MojoValidateResult res = {static_cast<uint32_t>(MojoValidateStatus::kInvalidHeaderSize), 0};
      return res;
    }
    if ((header_num_bytes % 8) != 0) {
      MojoValidateResult res = {static_cast<uint32_t>(MojoValidateStatus::kInvalidAlignment), 0};
      return res;
    }
    if (len < header_num_bytes) {
      MojoValidateResult res = {static_cast<uint32_t>(MojoValidateStatus::kMessageTooShort), header_num_bytes};
      return res;
    }

    // Little-endian read of method_name (offset 12..16)
    uint32_t method_name = data[12] | (data[13] << 8) | (data[14] << 16) | (data[15] << 24);

    if (!schema->methods && schema->method_count > 0) {
      MojoValidateResult res = {static_cast<uint32_t>(MojoValidateStatus::kNullInput), 0};
      return res;
    }

    const MojoMethodConstraint* found_method = nullptr;
    for (uint32_t i = 0; i < schema->method_count; ++i) {
      if (schema->methods[i].method_id == method_name) {
        found_method = &schema->methods[i];
        break;
      }
    }

    if (!found_method) {
      MojoValidateResult res = {static_cast<uint32_t>(MojoValidateStatus::kUnknownMethod), 12};
      return res;
    }

    size_t payload_offset = header_num_bytes;
    size_t payload_len = len - payload_offset;

    if (payload_len < found_method->expected_payload_size) {
      MojoValidateResult res = {static_cast<uint32_t>(MojoValidateStatus::kPayloadTooShort), static_cast<uint32_t>(payload_offset)};
      return res;
    }

    if (!found_method->field_constraints && found_method->field_count > 0) {
      MojoValidateResult res = {static_cast<uint32_t>(MojoValidateStatus::kNullInput), 0};
      return res;
    }

    for (uint32_t i = 0; i < found_method->field_count; ++i) {
      const MojoFieldConstraint& field = found_method->field_constraints[i];
      size_t f_offset = payload_offset + field.offset;
      if (field.is_nullable == 0) {
        size_t f_end = f_offset + field.expected_size;
        if (f_end > len) {
          MojoValidateResult res = {
              static_cast<uint32_t>(MojoValidateStatus::kFieldOutOfBounds),
              static_cast<uint32_t>(payload_offset + field.offset)};
          return res;
        }
      } else if (field.expected_size > 0) {
        size_t f_end = f_offset + field.expected_size;
        if (f_end > len) {
          MojoValidateResult res = {
              static_cast<uint32_t>(MojoValidateStatus::kFieldOutOfBounds),
              static_cast<uint32_t>(payload_offset + field.offset)};
          return res;
        }
      }
    }

    MojoValidateResult res = {static_cast<uint32_t>(MojoValidateStatus::kOk), 0};
    return res;
  }
};

}  // namespace chromium_rust_perf

#endif  // CPP_MOJO_VALIDATOR_BASELINE_H_
