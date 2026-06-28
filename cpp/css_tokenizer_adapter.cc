#include "cpp/css_tokenizer_adapter.h"

#include <atomic>

#include "cpp/css_tokenizer_baseline.h"

namespace chromium_rust_perf {

namespace {

std::atomic_bool g_rollback_enabled{false};

CssTokenizeResult FromFfi(const ChromiumRustCssTokenizeResult& result) noexcept {
  return CssTokenizeResult{
      static_cast<CssTokenizeStatus>(result.status),
      result.token_count,
      result.max_token_length,
      result.bytes_consumed,
  };
}

}  // namespace

CssTokenizer::CssTokenizer(CssTokenizeOptions options) noexcept
    : options_(options), options_valid_(options.IsValid()) {}

void CssTokenizer::SetRollbackEnabled(bool enabled) noexcept {
  g_rollback_enabled.store(enabled, std::memory_order_relaxed);
}

bool CssTokenizer::IsRollbackEnabled() noexcept {
  return g_rollback_enabled.load(std::memory_order_relaxed);
}

CssTokenizeResult CssTokenizer::Tokenize(const uint8_t* data, size_t len) const noexcept {
  if (!options_valid_) {
    return CssTokenizeResult{CssTokenizeStatus::kInvalidPolicy, 0, 0, 0};
  }

  if (g_rollback_enabled.load(std::memory_order_relaxed)) {
    CppBaselineCssTokenizer baseline(options_);
    return baseline.Tokenize(data, len);
  }

  ChromiumRustCssTokenizeResult ffi_result = {};
  chromium_rust_css_tokenize_v1(
      data, len, options_.max_tokens, options_.max_token_length, &ffi_result);
  return FromFfi(ffi_result);
}

}  // namespace chromium_rust_perf