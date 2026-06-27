# Chromium Rust/C++ Integration CI & Performance Budget Documentation

This document describes the quality gates, Pull Request (PR) checklist, and performance budget workflow for the Chromium Rust migration project.

---

## 1. PR Checklist (Pre-Merge Requirements)

Before submitting a PR or merging code, developers MUST execute and verify all CI Quality Gates.

### Quick Commands
Run all gates in one command:
```powershell
powershell -ExecutionPolicy Bypass -File tools/run_all_gates.ps1
```

### Manual Checklist
1. **Rust Verification**:
   - Run `cargo test --workspace` to ensure all Rust units, integration tests, and doc tests pass.
   - Run `cargo clippy --workspace --all-targets` and fix any lints/warnings.
2. **C++ Integration Verification**:
   - Run `tools/run_cpp_tests.ps1` to run all differential and contract validation tests.
   - Verify that there are 0 differential failures.
3. **Performance Budget & Size Verification**:
   - Run `tools/run_cpp_bench.ps1` and verify that all speedup ratios meet budgets.
   - Run `tools/run_size_gate.ps1` to ensure binary bloat and import guards are respected.
4. **Fuzz Smoke Verification**:
   - Run `tools/run_local_fuzz.ps1 --runs 10000` to ensure no panics or segmentation faults are introduced in FFI interfaces.

---

## 2. CI Quality Gates Overview

The repository enforces six automated quality gates:

| Gate | Command | Description |
|---|---|---|
| **Rust Unit Tests** | `cargo test` | Verifies correctness of low-level Rust libraries. |
| **Source / Artifact Guard** | `rust_hot_leaf_guard.py` | Enforces `#![no_std]` rules and ensures no disallowed external crate imports. |
| **Binary Size Gate** | `rust_size_gate.py` | Ensures that Rust static libraries and individual rlib sizes stay within strict bounds. |
| **C++ Differential Tests** | `run_cpp_tests.ps1` | Runs 15,000+ prefix and mutation test cases, comparing C++ and Rust outputs. |
| **C++ Benchmark Gate** | `run_cpp_bench.ps1` | Compares microbenchmark throughput of Rust FFI vs C++ baselines. |
| **FFI Mutation Fuzzer** | `run_local_fuzz.ps1` | Mutates headers, URLs, and Mojo inputs to detect memory corruption or panic aborts. |

---

## 3. Performance Budget Update Workflow

Our performance budgets are located under the `budgets/` directory:
- `budgets/http_header_scanner_perf.json`
- `budgets/url_canonicalizer_perf.json`
- `budgets/mojo_validator_perf.json`

### When is it Permitted to Update Budgets?

Modifying budgets is allowed **only** under the following scenarios:
1. **FFI Overhead Calibration**: For extremely fast C++ operations (e.g. Mojo message headers running in <5 ns), the fixed 5-8 ns C-FFI transition cost represents a physical lower bound. Budgets can be calibrated downward to reflect this overhead.
2. **Baseline C++ Improvements**: If the baseline C++ implementation gets optimized (lowering C++ runtime), the relative speedup of Rust might decrease even if Rust performance is unchanged.
3. **Hardware Environment Changes**: Run-to-run variations or migrating to new CI runner instance types with different CPU/memory specifications.

### Steps to Update Performance Budgets

1. **Run Multi-Sample Benchmarks**:
   Ensure you run the benchmarks with enough samples (e.g., `--samples 15`) to filter out thermal throttling or background system noise:
   ```powershell
   & target/bench/main.exe --mode <mode> --samples 15 --json temp_report.json
   ```
2. **Analyze Speedup Ratios**:
   Extract the measured speedups from the JSON output.
3. **Edit the Budget File**:
   Update `budgets/<component>_perf.json` by adjusting the `min_speedup` values to match the new floor speedup.
4. **Justification**:
   Include a brief explanation in the PR description justifying the change (e.g., *"Calibrating Valid Mojo budget to 0.35x because measured C++ baseline is 4.1ns while Rust FFI transition takes 6.8ns"*).
