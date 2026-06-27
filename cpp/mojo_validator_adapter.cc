// Copyright 2026 The Chromium Authors
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

#include "cpp/mojo_validator_adapter.h"
#include "cpp/mojo_validator_baseline.h"

#include <atomic>

namespace chromium_rust_perf {

namespace {
std::atomic<bool> g_mojo_rollback_enabled{false};
}  // namespace

MojoValidateResult MojoMessageValidator::Validate(
    const uint8_t* data,
    size_t len,
    const MojoSchemaTable* schema) const noexcept {
  if (g_mojo_rollback_enabled.load(std::memory_order_relaxed)) {
    return CppBaselineMojoValidator::Validate(data, len, schema);
  }

  MojoValidateResult result;
  chromium_rust_mojo_validate_v1(data, len, schema, &result);
  return result;
}

void MojoMessageValidator::SetRollbackEnabled(bool enabled) noexcept {
  g_mojo_rollback_enabled.store(enabled, std::memory_order_relaxed);
}

bool MojoMessageValidator::IsRollbackEnabled() noexcept {
  return g_mojo_rollback_enabled.load(std::memory_order_relaxed);
}

}  // namespace chromium_rust_perf
