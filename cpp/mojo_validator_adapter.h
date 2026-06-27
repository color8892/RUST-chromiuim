// Copyright 2026 The Chromium Authors
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

#ifndef CPP_MOJO_VALIDATOR_ADAPTER_H_
#define CPP_MOJO_VALIDATOR_ADAPTER_H_

#include "include/chromium_rust_perf/mojo_validator_ffi.h"

namespace chromium_rust_perf {

class MojoMessageValidator {
 public:
  MojoMessageValidator() noexcept = default;
  ~MojoMessageValidator() noexcept = default;

  // Validate a Mojo message.
  [[nodiscard]] MojoValidateResult Validate(
      const uint8_t* data,
      size_t len,
      const MojoSchemaTable* schema) const noexcept;

  // Configure feature flags for A/B testing or fallback
  static void SetRollbackEnabled(bool enabled) noexcept;
  static bool IsRollbackEnabled() noexcept;
};

}  // namespace chromium_rust_perf

#endif  // CPP_MOJO_VALIDATOR_ADAPTER_H_
