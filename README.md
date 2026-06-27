# Chromium Rust Performance / Size Scaffold

This workspace implements the performance-first Rust migration policy for a Chromium fork.

It intentionally starts with a hot leaf module instead of touching Chromium orchestration code:

- `rust/hot_leaf/http_header_scanner`: `#![no_std]` Rust scanner with a zero-copy C ABI.
- `include/chromium_rust_perf/http_header_scanner_ffi.h`: stable C ABI contract.
- `cpp/http_header_scanner_adapter.*`: small C++ facade for Chromium-side ownership and rollback integration.
- `tools/rust_hot_leaf_guard.py`: source and artifact guard for panic, formatting, allocation, generic, and FFI-copy hazards.
- `docs/chromium_rust_perf_size_policy.md`: project policy that future agents must follow.

Run checks:

```powershell
cargo test
python -m unittest discover -s tests
python tools/rust_hot_leaf_guard.py rust/hot_leaf
```

Release size guard example:

```powershell
cargo build --release
python tools/rust_hot_leaf_guard.py rust/hot_leaf --artifact target/release/libchromium_rust_http_header_scanner.rlib
```

Chromium GN should wrap this crate with `rust_static_library` for final C++ linkage. Local Cargo builds use the `rlib` artifact so unit tests do not require rebuilding `core` with `panic=abort`.
