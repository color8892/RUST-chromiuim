# Chromium Rust 極致效能與體積優化策略

本專案的排序是 **Performance = Binary Size >> Rust safety**。Rust migration 只有在可量化提升 latency、throughput、startup locality 或 binary size 時才成立。Memory safety 是副產品，不是合入理由。

## Non-Negotiable Gates

- Hot path Rust crate 預設使用 `#![no_std]`，只允許 `core`。需要 `alloc` 或 `std` 時必須提交 waiver，說明無法使用 caller-owned buffer、bounded arena 或 C++ ownership 的原因。
- Release profile 必須使用 `panic = "abort"`、ThinLTO、單一 codegen unit、無 debug info、strip symbols。
- FFI-facing Rust function 不得 panic crossing；錯誤一律回傳 compact numeric status。
- Hot path 禁止 `format!`、`write!`、`println!`、`dbg!`、`Debug`/`Display` formatting、`unwrap`、`expect`、`panic!`、`todo!`、`unimplemented!`。
- Hot path 禁止跨 FFI owned `String`、`Vec`、`CxxString` conversion。C++ owns input memory，Rust 僅建立 call-scoped slice。
- Rust 不得保存 C++ raw pointer。Async work 必須改傳 shared-memory ownership handle 或 ref-counted mapping lease。
- Public Rust API 禁止 unconstrained generics。會造成超過兩個 instantiation 的策略型泛型必須改為 `enum`、table-driven dispatch 或 `&dyn Trait`。
- 每個 migration 必須有 differential tests、fuzz target plan、microbenchmark、binary size diff、rollback flag。

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
- treating borrowed C++ memory as Rust `'static`

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
