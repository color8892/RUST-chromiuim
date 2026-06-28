# Chromium Rust Integration Roadmap

This document defines the next integration steps after the local hot-leaf
prototype. It is intentionally strict: a component is not considered "Rust
migrated" until it is wired into a real Chromium checkout and passes Chromium
quality gates.

## Current Scope

The repository currently proves the performance-first Rust migration pattern for
three hot leaf areas:

- HTTP header scanning
- URL component parsing and canonicalization leaves
- Mojo IPC message validation leaves

These are local C++/Rust harnesses. They are not yet integrated into upstream
Chromium targets.

## Integration Readiness Matrix

| Area | Current status | Next valid step | Do not do yet |
|---|---|---|---|
| Blink LayoutNG | Not started | Identify tokenizer or selector-prefilter leaf candidates inside a Chromium checkout | Do not rewrite layout object graph, fragment tree, Oilpan-managed DOM, or style orchestration |
| V8 parser/JIT/GC | Not started | Restrict to boundary validators or generated metadata checkers, if any measurable leaf exists | Do not rewrite parser, bytecode compiler, JIT, GC, handles, or isolate object graph |
| Browser process object graph | Not started | Add Rust only behind C ABI leaf helpers with no ownership transfer | Do not replace keyed services, profiles, WebContents, navigation, or lifecycle orchestration |
| Chromium TaskRunner / ThreadPool | Prototype only | Keep async bridge as an experimental feature-gated adapter | Do not replace `base::TaskRunner`, `SequenceManager`, or `ThreadPool` |
| GPU command runtime | Not started | Evaluate generated command buffer validation tables only | Do not rewrite command decoder, scheduler, context ownership, or driver-facing runtime |
| Chromium GN target integration | Sketch exists | Import this repo under `//third_party/rust/chromium_rust_perf` or equivalent and wire `BUILD.gn` into a real Chromium build | Do not assume this standalone GN file is buildable outside Chromium's build graph |
| Android official build / supersize | Not started | Run Android official build and compare `supersize diff` against baseline | Do not update size budgets without the diff artifact |
| web_tests / WPT | Not started | Add differential tests only after a real Blink-facing integration point exists | Do not claim browser compatibility from local parser tests |
| Chromium fuzz corpus | Local smoke only | Connect libFuzzer targets to Chromium fuzzing style and seed corpora | Do not rely on local random mutation smoke tests as fuzz coverage |

## Required Chromium Checkout Gates

A real Chromium integration CL must pass these gates before it can be called
production-ready:

1. `gn gen` succeeds with the Rust target enabled.
2. The relevant Chromium C++ target links against the Rust static library.
3. The old C++ path remains behind a build flag or runtime rollback flag.
4. Differential tests compare old C++ and Rust outputs on the same corpus.
5. Android official build produces a `supersize diff`.
6. Browser benchmarks show no regression for startup, memory, Speedometer, and
   page-load metrics relevant to the touched component.
7. Fuzz targets cover malformed input, truncation, alignment, endian, and
   capacity exhaustion cases.
8. Component-specific web tests or WPT run only after the Rust leaf is wired into
   a user-visible browser path.

## First Chromium CL Shape

The first real Chromium CL should be deliberately small:

- Add a Rust target for one hot leaf crate.
- Add a C++ adapter target with a narrow C ABI.
- Add a GN arg or feature flag to choose Rust vs existing C++.
- Add differential tests that call both implementations.
- Add a benchmark target that reports both latency and allocation count.
- Add size reporting instructions to the CL description.

The recommended first CL is HTTP header scanning or URL component parsing. Mojo
validation should remain prototype/informational until the FFI fixed-cost problem
is resolved with a coarser message batch or generated validator table.

## Import Preparation

Use `chromium_import_manifest.json` and `tools/prepare_chromium_import.ps1` to
stage this scaffold into a real Chromium checkout.
The machine-readable boundary between standalone-complete work and
Chromium-checkout work is tracked in `chromium_integration_checklist.json`.
Validate it with:

```powershell
python tools/check_chromium_integration_checklist.py
python tools/check_chromium_import_consistency.py
```

Dry run:

```powershell
powershell -ExecutionPolicy Bypass -File tools/prepare_chromium_import.ps1 `
  -ChromiumRoot C:\path\to\chromium\src `
  -DryRun
```

Copy into the default destination:

```powershell
powershell -ExecutionPolicy Bypass -File tools/prepare_chromium_import.ps1 `
  -ChromiumRoot C:\path\to\chromium\src
```

Default destination:

```text
third_party/rust/chromium_rust_perf
```

The import script validates that the target tree looks like Chromium before it
copies anything. It does not edit Chromium build files outside the destination;
the integration CL must wire the imported `BUILD.gn` into the relevant Chromium
target explicitly.

## Non-Goals

These items are explicitly out of scope for the current repository:

- Rewriting Blink LayoutNG core.
- Rewriting V8 parser, JIT, or GC.
- Replacing Browser process ownership/lifecycle graphs.
- Replacing Chromium task scheduling primitives.
- Replacing GPU command runtime ownership or driver-facing code.

Those areas can only be evaluated after hot leaf integration proves a measurable
performance or binary-size win inside a real Chromium build.
