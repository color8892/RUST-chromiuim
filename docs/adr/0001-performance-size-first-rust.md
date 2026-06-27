# ADR 0001: Performance and Binary Size First Rust Migration

## Status

Accepted.

## Context

The project uses Rust only where it improves Chromium hot leaf performance, binary size, or startup locality. Safety alone is insufficient justification because Rust can increase binary size through panic paths, formatting, generic monomorphization, and transitive crates.

## Decision

Rust migrations must target small leaf modules with stable C ABI boundaries. Hot modules must be `no_std`, zero allocation, zero copy, panic-aborting, and measurable. C++ retains ownership, scheduling, process orchestration, and rollback wiring.

## Consequences

- The first implementation target is an HTTP header byte scanner with a zero-copy C ABI.
- The project includes a guard tool that rejects common panic, formatting, allocation, and FFI-copy hazards.
- Future agents must update policy and guard tests before broadening allowed Rust patterns.
