$ErrorActionPreference = "Stop"

Write-Host "================================================================"
Write-Host "           Building Rust FFI Static Library (Release)           "
Write-Host "================================================================"
cargo build --release -p chromium_rust_perf_ffi_static

$staticLib = "target/release/chromium_rust_perf_ffi_static.lib"
if (-not (Test-Path $staticLib)) {
    $staticLib = "target/release/libchromium_rust_perf_ffi_static.a"
}

if (-not (Test-Path $staticLib)) {
    Write-Error "Could not find compiled Rust FFI static library artifact."
}

Write-Host "================================================================"
Write-Host "           Running Rust Source / Artifact Guard                 "
Write-Host "================================================================"
python tools/rust_hot_leaf_guard.py rust/hot_leaf rust/ffi_static `
    --artifact $staticLib `
    --artifact target/release/libchromium_rust_http_header_scanner.rlib `
    --artifact target/release/libchromium_rust_url_canonicalizer.rlib

Write-Host "================================================================"
Write-Host "           Running Binary Size Gate                             "
Write-Host "================================================================"
python tools/rust_size_gate.py `
    --artifact $staticLib `
    --artifact target/release/libchromium_rust_http_header_scanner.rlib `
    --artifact target/release/libchromium_rust_url_canonicalizer.rlib `
    --budget-file budgets/rust_artifacts_size.json `
    --max-registry-packages 0 `
    --json-output target/size-gate/report.json

Write-Host "Size gate report written to target/size-gate/report.json"
