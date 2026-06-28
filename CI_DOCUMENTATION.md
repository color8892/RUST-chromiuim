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

Run the lightweight standalone readiness suite:
```powershell
powershell -ExecutionPolicy Bypass -File tools/run_standalone_readiness.ps1
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
   - Run `python tools/check_fuzz_corpus_manifest.py` to ensure every P0 component has valid, truncated, malformed, and component-specific fuzz seed coverage.
   - Run `tools/run_fuzz_corpus_replay.ps1` to replay committed seeds through both Rust FFI and rollback C++ paths.
   - Run `tools/run_rollback_gate.ps1` to verify every P0 adapter can switch Rust -> C++ rollback -> Rust at runtime.
   - Run `tools/run_local_fuzz.ps1 --runs 10000` to ensure no panics or segmentation faults are introduced in FFI interfaces.

---

## 2. CI Quality Gates Overview

The repository enforces the following automated quality gates:

| Gate | Command | Description |
|---|---|---|
| **Rust Unit Tests** | `cargo test` | Verifies correctness of low-level Rust libraries. |
| **P0 Hot Leaf Registry** | `check_p0_hot_leaf_registry.py` | Ensures every P0 leaf has Rust source, C++ adapter, baseline, budgets, rollback, fuzz, benchmark, and differential coverage. |
| **P0 Fuzz Corpus Manifest** | `check_fuzz_corpus_manifest.py` | Ensures every P0 leaf has bounded seed data for required valid, malformed, truncated, and component-specific fuzz categories. |
| **P0 Fuzz Corpus Replay** | `run_fuzz_corpus_replay.ps1` | Generates and runs a C++ replay harness so committed seeds execute through Rust FFI and rollback C++ paths. |
| **P0 Runtime Rollback Gate** | `run_rollback_gate.ps1` | Generates and runs a C++ harness proving each P0 adapter can toggle Rust, C++ rollback, and Rust restore. |
| **P0 Standalone Reports** | `emit_fuzz_corpus_report.py`, `emit_p0_artifact_summary.py`, `emit_chromium_import_report.py` | Writes reviewable JSON reports under `target/reports/` for corpus coverage, artifacts, and Chromium import dry-run planning. |
| **Chromium Integration Checklist** | `check_chromium_integration_checklist.py` | Keeps standalone-complete items separate from work that requires a real Chromium checkout. |
| **Chromium Import Consistency** | `check_chromium_import_consistency.py` | Verifies `BUILD.gn`, the P0 registry, and the import manifest stay aligned before a Chromium checkout import. |
| **Chromium CL Handoff Package** | `emit_chromium_cl_handoff.py` | Writes JSON and Markdown handoff artifacts for the first real Chromium CL under `target/reports/`. |
| **Chromium Checkout Preflight** | `check_chromium_checkout_preflight.py` | Writes a non-mutating report for a real Chromium checkout path, or a placeholder report when no path is provided. |
| **Chromium Next Tasks** | `check_chromium_next_tasks.py` | Validates an agent-ready task graph and Markdown brief for work that requires a real Chromium checkout. |
| **Standalone Readiness Report** | `emit_standalone_readiness_report.py` | Summarizes completed standalone gates, remaining Chromium-checkout blockers, and next commands under `target/reports/`. |
| **Reports Manifest** | `emit_reports_manifest.py` | Indexes generated report artifacts and their reading order under `target/reports/reports_manifest.json`. |
| **P0 Perf Stability Settings** | `check_perf_stability.py` | Prevents benchmark gates from silently dropping below the required sample count or losing perf budgets. |
| **Source / Artifact Guard** | `rust_hot_leaf_guard.py` | Enforces `#![no_std]` rules and ensures no disallowed external crate imports. |
| **Binary Size Gate** | `rust_size_gate.py` | Ensures that Rust static libraries and individual rlib sizes stay within strict bounds. |
| **C++ Differential Tests** | `run_cpp_tests.ps1` | Runs 15,000+ prefix and mutation test cases, comparing C++ and Rust outputs. |
| **C++ Benchmark Gate** | `run_cpp_bench.ps1` | Compares microbenchmark throughput of Rust FFI vs C++ baselines. |
| **FFI Mutation Fuzzer** | `run_local_fuzz.ps1` | Mutates headers, URLs, and Mojo inputs to detect memory corruption or panic aborts. |
| **Chromium Integration Readiness** | `check_chromium_integration_readiness.ps1` | Verifies this repo has the local scaffold required before importing into a real Chromium checkout. |

---

## 2.1 Chromium Integration Boundary

The following work cannot be honestly completed inside this standalone repo:

- Blink LayoutNG Rust migration.
- V8 parser / JIT / GC Rust migration.
- Browser process object graph replacement.
- Chromium TaskRunner / ThreadPool replacement.
- GPU command runtime replacement.
- Android official `supersize diff`.
- Blink `web_tests` / WPT coverage.
- Chromium fuzz corpus integration.

Those tasks require a real Chromium checkout. Use
`docs/chromium_integration_roadmap.md` as the controlling document and run:

```powershell
powershell -ExecutionPolicy Bypass -File tools/check_chromium_integration_readiness.ps1 -ChromiumRoot C:\path\to\chromium\src
```

To stage the scaffold into a Chromium checkout without editing unrelated
Chromium files, run:

```powershell
powershell -ExecutionPolicy Bypass -File tools/prepare_chromium_import.ps1 -ChromiumRoot C:\path\to\chromium\src -DryRun
```

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
