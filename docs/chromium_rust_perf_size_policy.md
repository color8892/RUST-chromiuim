# Chromium Rust 極致效能與體積優化策略

本專案的排序是 **Performance = Binary Size >> Rust safety**。Rust migration 只有在可量化提升 latency、throughput、startup locality 或 binary size 時才成立。Memory safety 是副產品，不是合入理由。

## Non-Negotiable Gates

- Hot path Rust crate 預設使用 `#![no_std]`，只允許 `core`。需要 `alloc` 或 `std` 時必須提交 waiver，說明無法使用 caller-owned buffer、bounded arena 或 C++ ownership 的原因。
- Release profile 必須使用 `panic = "abort"`、ThinLTO、單一 codegen unit、無 debug info、strip symbols。
- FFI-facing Rust function 不得 panic crossing；錯誤一律回傳 compact numeric status。
- Hot path 禁止 `format!`、`write!`、`println!`、`dbg!`、`Debug`/`Display` formatting、`unwrap`、`expect`、`panic!`、`todo!`、`unimplemented!`。
- Hot path 應避免使用隱式邊界檢查（例如常規的 `slice[index]` 索引）。應優先使用迭代器（Iterator）、安全的 `get` API，或在經靜態證明安全的前提下使用 `unsafe { *slice.get_unchecked(index) }`。凡是在 Release 產物中引發 `panic_bounds_check` 符號的代碼均無法通過 Gate。
- Hot path 禁止跨 FFI owned `String`、`Vec`、`CxxString` conversion。C++ owns input memory，Rust 僅建立 call-scoped slice。
- Rust 不得保存 C++ raw pointer。Async work 必須改傳 shared-memory ownership handle 或 ref-counted mapping lease。
- Public Rust API 禁止 unconstrained generics。會造成超過兩個 instantiation 的策略型泛型必須改為 `enum` 或是經過效能與體積評估的 table-driven dispatch，儘量避免使用帶有間接跳轉（Indirect Branch）開銷與 vtable 的 `dyn Trait`。
- 每個 migration 必須有 differential tests、fuzz target plan、microbenchmark、binary size diff、rollback flag。
- 每個 migration 必須跑 `tools/rust_size_gate.py` 或等價 CI step，輸出 artifact bytes、registry dependency count 與 JSON report。
- 每個 microbenchmark 必須輸出 machine-readable JSON，並由 `tools/rust_perf_gate.py` 或等價 CI step 檢查 speedup、latency cap 或 regression budget。

## Hot Path ABI

Hot path ABI 使用 C ABI，不使用 `cxx` 的 owned type bridge。允許：

- `const uint8_t* + size_t`
- caller-owned output struct
- caller-owned output range table
- numeric status and compact enum
- caller-owned scratch buffer

不允許：

- Rust-owned `String`/`Vec` return
- per-token callback into C++
- C++ object pointer retained by Rust
- treating borrowed C++ memory as Rust `'static`（FFI 借用指標必須在文檔中明確標註生命週期約束）
- 未遵循統一命名空間命名之 `#[no_mangle]` 函數（所有暴露給 C++ 的函數必須使用 `chromium_rust_<crate_name>_<func_name>` 格式，並建議包含版本號後綴如 `_v1`）

## Component Order

1. Mojo IPC validation / serialization fast path.
2. Network byte parsers and URL/cookie canonicalization.
3. Blink CSS tokenizer / selector prefilter / stylesheet leaf parser.
4. Base JSON / manifest / prefs parser only if materialization cost does not erase startup wins.
5. Image/font/media metadata parser only for metadata and bounds validation.

Do not Rust-migrate Browser process object graphs, TaskRunner, Blink LayoutNG core, Oilpan DOM, V8 JIT/GC, or GPU command runtime for this performance-first phase.

## Review Checklist

- `python tools/rust_hot_leaf_guard.py rust/hot_leaf` passes.
- `cargo test` passes.
- `cargo build --release` produces an artifact that passes the artifact scan.
- Microbenchmark demonstrates at least 5% target improvement or a measurable p95 latency reduction.
- Size diff is neutral or negative; any growth is offset in the same CL.
- FFI call granularity is one call per buffer/message, never one call per byte/token.
