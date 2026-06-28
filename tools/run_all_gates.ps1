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
    python tools/check_p0_hot_leaf_registry.py --help > $null
    python tools/check_fuzz_corpus_manifest.py --help > $null
    python tools/emit_fuzz_corpus_replay.py --help > $null
    python tools/emit_rollback_gate.py --help > $null
    python tools/emit_fuzz_corpus_report.py --help > $null
    python tools/emit_p0_artifact_summary.py --help > $null
    python tools/emit_chromium_import_report.py --help > $null
    python tools/check_perf_stability.py --help > $null
    python tools/check_chromium_integration_checklist.py --help > $null
    python tools/check_chromium_import_consistency.py --help > $null
    python tools/emit_chromium_cl_handoff.py --help > $null
    python tools/check_chromium_checkout_preflight.py --help > $null
    python tools/check_chromium_next_tasks.py --help > $null
    python tools/select_chromium_next_task.py --help > $null
    python tools/check_chromium_rust_safety_candidates.py --help > $null
    python tools/emit_standalone_readiness_report.py --help > $null
    python tools/emit_reports_manifest.py --help > $null
}

# 2.0 P0 component registry.
Run-GateStep "P0 Hot Leaf Registry" {
    python tools/check_p0_hot_leaf_registry.py
}

# 2.0.1 P0 fuzz corpus coverage contract.
Run-GateStep "P0 Fuzz Corpus Manifest" {
    python tools/check_fuzz_corpus_manifest.py
}

# 2.0.2 Replay committed P0 corpus seeds through Rust and rollback C++ paths.
Run-GateStep "P0 Fuzz Corpus Replay" {
    powershell -ExecutionPolicy Bypass -File tools/run_fuzz_corpus_replay.ps1
}

# 2.0.3 Runtime rollback contract for every P0 adapter.
Run-GateStep "P0 Runtime Rollback Gate" {
    powershell -ExecutionPolicy Bypass -File tools/run_rollback_gate.ps1
}

# 2.0.4 Standalone reporting artifacts for review and import planning.
Run-GateStep "P0 Standalone Reports" {
    python tools/check_chromium_import_consistency.py
    python tools/emit_fuzz_corpus_report.py
    python tools/emit_p0_artifact_summary.py
    python tools/emit_chromium_import_report.py
    python tools/check_chromium_integration_checklist.py
    python tools/emit_chromium_cl_handoff.py
    python tools/check_chromium_checkout_preflight.py
    python tools/check_chromium_next_tasks.py
    python tools/select_chromium_next_task.py
    python tools/check_chromium_rust_safety_candidates.py
    python tools/emit_standalone_readiness_report.py
    python tools/emit_reports_manifest.py
}

# 2.0.5 Benchmark stability guard.
Run-GateStep "P0 Perf Stability Settings" {
    python tools/check_perf_stability.py
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
