# Ensure script execution fails on error
$ErrorActionPreference = "Stop"

Write-Host "================================================================"
Write-Host "         Chromium Rust/C++ Integration CI Quality Gates         "
Write-Host "================================================================"
Write-Host ""

# Helper to run a step and fail if it returns non-zero
function Run-GateStep {
    param(
        [string]$Name,
        [scriptblock]$Script
    )
    Write-Host ">>> Running Gate Step: $Name..." -ForegroundColor Cyan
    try {
        & $Script
        $exitCode = $LASTEXITCODE
        if ($exitCode -ne 0 -and $exitCode -ne $null) {
            Write-Error "FAILURE: Step '$Name' exited with code $exitCode"
        }
        Write-Host ">>> SUCCESS: '$Name' passed." -ForegroundColor Green
        Write-Host ""
    } catch {
        Write-Error "FAILURE: Step '$Name' encountered an error: $_"
    }
}

# 1. Cargo Workspace Tests
Run-GateStep "Cargo Workspace Unit & Doc Tests" {
    cargo test --workspace
}

# 2. Python CLI verification
Run-GateStep "Python Gate Tools CLI Verification" {
    python tools/rust_hot_leaf_guard.py --help > $null
    python tools/rust_size_gate.py --help > $null
    python tools/rust_perf_gate.py --help > $null
}

# 2.1 Chromium integration readiness scaffold.
Run-GateStep "Chromium Integration Readiness Scaffold" {
    powershell -ExecutionPolicy Bypass -File tools/check_chromium_integration_readiness.ps1
}

# 3. Source / Artifact Guard & Size Gate
Run-GateStep "Source/Artifact Guard & Size Gate" {
    powershell -ExecutionPolicy Bypass -File tools/run_size_gate.ps1
}

# 4. C++ Differential Tests
Run-GateStep "C++ FFI Differential Tests" {
    powershell -ExecutionPolicy Bypass -File tools/run_cpp_tests.ps1
}

# 5. C++ Benchmark & Performance budget gates
Run-GateStep "C++ Benchmark & Perf Budget Gate: HTTP Headers" {
    powershell -ExecutionPolicy Bypass -File tools/run_cpp_bench.ps1 -Mode header
}
Run-GateStep "C++ Benchmark & Perf Budget Gate: URLs" {
    powershell -ExecutionPolicy Bypass -File tools/run_cpp_bench.ps1 -Mode url
}
Run-GateStep "C++ Benchmark & Perf Budget Gate: Mojo (Prototype)" {
    powershell -ExecutionPolicy Bypass -File tools/run_cpp_bench.ps1 -Mode mojo
}

# 6. Fuzz Smoke Test (10k iterations)
Run-GateStep "FFI Fuzzer Smoke Test" {
    powershell -ExecutionPolicy Bypass -File tools/run_local_fuzz.ps1 --runs 10000
}

Write-Host "================================================================"
Write-Host "   ALL CI QUALITY GATES COMPLETED SUCCESSFULLY!                 "
Write-Host "================================================================" -ForegroundColor Green
