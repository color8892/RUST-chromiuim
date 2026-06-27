// Copyright 2026 The Chromium Authors
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

use std::path::{Path, PathBuf};
use std::fs;

fn find_file_recursive(dir: &Path, filename: &str) -> Option<PathBuf> {
    if dir.is_dir() {
        if let Ok(entries) = fs::read_dir(dir) {
            for entry in entries.flatten() {
                let path = entry.path();
                if path.is_dir() {
                    if let Some(p) = find_file_recursive(&path, filename) {
                        return Some(p);
                    }
                } else if path.file_name().and_then(|n| n.to_str()) == Some(filename) {
                    return Some(path);
                }
            }
        }
    }
    None
}

fn main() {
    cxx_build::bridge("src/cxx_bridge.rs")
        .compile("cxx-bridge-mojo");

    println!("cargo:rerun-if-changed=src/cxx_bridge.rs");

    // Copy generated cxx header to our public include path
    let out_dir_str = std::env::var("OUT_DIR").unwrap();
    let out_dir = Path::new(&out_dir_str);
    
    if let Some(header_src) = find_file_recursive(out_dir, "cxx_bridge.rs.h") {
        let manifest_dir = std::env::var("CARGO_MANIFEST_DIR").unwrap();
        let dest_header = Path::new(&manifest_dir)
            .parent().unwrap() // rust/
            .parent().unwrap() // root/
            .join("include")
            .join("chromium_rust_perf")
            .join("cxx_bridge.rs.h");

        // Ensure target directory exists
        if let Some(parent) = dest_header.parent() {
            fs::create_dir_all(parent).unwrap();
        }
        
        fs::copy(&header_src, &dest_header).unwrap();
    }
}
