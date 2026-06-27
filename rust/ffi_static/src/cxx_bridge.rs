// Copyright 2026 The Chromium Authors
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

#[cxx::bridge(namespace = "chromium_rust_perf")]
pub mod ffi {
    struct MojoValidateResultCxx {
        status: u32,
        error_offset: u32,
    }

    extern "Rust" {
        fn validate_mojo_cxx(data: &[u8], method_id: u32) -> MojoValidateResultCxx;
    }
}

pub fn validate_mojo_cxx(data: &[u8], method_id: u32) -> ffi::MojoValidateResultCxx {
    let fields = [
        chromium_rust_mojo_validator::MojoFieldConstraint { offset: 0, expected_size: 4, is_nullable: 0 },
    ];
    let methods = [
        chromium_rust_mojo_validator::MojoMethodConstraint {
            method_id,
            expected_payload_size: 8,
            field_constraints: fields.as_ptr(),
            field_count: fields.len() as u32,
        },
    ];
    let schema = chromium_rust_mojo_validator::MojoSchemaTable {
        methods: methods.as_ptr(),
        method_count: methods.len() as u32,
    };

    let res = unsafe {
        chromium_rust_mojo_validator::validate_mojo_message(
            data.as_ptr(),
            data.len(),
            &schema as *const _,
        )
    };

    ffi::MojoValidateResultCxx {
        status: res.status,
        error_offset: res.error_offset,
    }
}
