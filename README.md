# Chromium Rust Performance / Size Scaffold

This workspace implements the performance-first Rust migration policy for a Chromium fork.

It intentionally starts with hot leaf modules instead of touching Chromium orchestration code:

- `rust/hot_leaf/http_header_scanner`: `#![no_std]` Rust scanner with a zero-copy C ABI.
- `rust/hot_leaf/url_canonicalizer`: `#![no_std]` URL component parser with caller-owned input.
- `rust/ffi_static`: release-only staticlib aggregator for C++ linkage.
- `include/chromium_rust_perf/http_header_scanner_ffi.h`: stable C ABI contract.
- `include/chromium_rust_perf/url_canonicalizer_ffi.h`: stable URL parser C ABI contract.
- `cpp/http_header_scanner_adapter.*`: small C++ facade for Chromium-side ownership and rollback integration.
- `cpp/url_canonicalizer_adapter.*`: C++ facade that maps returned ranges into `std::string_view`.
- `tools/rust_hot_leaf_guard.py`: source and artifact guard for panic, formatting, allocation, generic, and FFI-copy hazards.
- `docs/chromium_rust_perf_size_policy.md`: project policy that future agents must follow.

Run checks:

```powershell
cargo test
python -m unittest discover -s tests
python tools/rust_hot_leaf_guard.py rust/hot_leaf rust/ffi_static
powershell -ExecutionPolicy Bypass -File tools/run_size_gate.ps1
```

Release size guard example:

```powershell
cargo build --release -p chromium_rust_perf_ffi_static
python tools/rust_hot_leaf_guard.py rust/hot_leaf rust/ffi_static --artifact target/release/chromium_rust_perf_ffi_static.lib
python tools/rust_size_gate.py --artifact target/release/chromium_rust_perf_ffi_static.lib --max-registry-packages 0
```

Committed budgets live under `budgets/`:

- `budgets/rust_artifacts_size.json`
- `budgets/http_header_scanner_perf.json`

Local C++ harnesses:

```powershell
powershell -ExecutionPolicy Bypass -File tools/run_cpp_tests.ps1
powershell -ExecutionPolicy Bypass -File tools/run_cpp_bench.ps1
powershell -ExecutionPolicy Bypass -File tools/run_local_fuzz.ps1
```

`run_cpp_bench.ps1` writes `target/bench/http_header_scanner.json` and runs `tools/rust_perf_gate.py` so benchmark output is machine-checkable.

Leaf crates intentionally stay as `rlib` so unit tests do not require rebuilding `core` with `panic=abort`. C++ linkage goes through `chromium_rust_perf_ffi_static`.
