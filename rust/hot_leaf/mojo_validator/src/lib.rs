#![cfg_attr(not(test), no_std)]
#![deny(unsafe_op_in_unsafe_fn)]
#![deny(clippy::expect_used)]
#![deny(clippy::panic)]
#![deny(clippy::print_stdout)]
#![deny(clippy::print_stderr)]
#![deny(clippy::todo)]
#![deny(clippy::unwrap_used)]

#[repr(C)]
#[derive(Clone, Copy, Eq, PartialEq)]
pub struct MojoFieldConstraint {
    pub offset: u32,
    pub expected_size: u32,
    pub is_nullable: u32, // 1 for true, 0 for false
}

#[repr(C)]
#[derive(Clone, Copy, Eq, PartialEq)]
pub struct MojoMethodConstraint {
    pub method_id: u32,
    pub expected_payload_size: u32,
    pub field_constraints: *const MojoFieldConstraint,
    pub field_count: u32,
}

#[repr(C)]
#[derive(Clone, Copy, Eq, PartialEq)]
pub struct MojoSchemaTable {
    pub methods: *const MojoMethodConstraint,
    pub method_count: u32,
}

#[repr(u32)]
#[derive(Clone, Copy, Eq, PartialEq)]
#[cfg_attr(test, derive(Debug))]
pub enum MojoValidateStatus {
    Ok = 0,
    NullInput = 1,
    MessageTooShort = 2,
    InvalidHeaderSize = 3,
    UnknownMethod = 4,
    PayloadTooShort = 5,
    FieldOutOfBounds = 6,
    InvalidAlignment = 7,
}

#[repr(C)]
#[derive(Clone, Copy, Eq, PartialEq)]
#[cfg_attr(test, derive(Debug))]
pub struct MojoValidateResult {
    pub status: u32,
    pub error_offset: u32,
}

impl MojoValidateResult {
    pub fn new(status: MojoValidateStatus, error_offset: u32) -> Self {
        Self {
            status: status as u32,
            error_offset,
        }
    }
}

unsafe fn validate_mojo_message(
    data: *const u8,
    len: usize,
    schema: *const MojoSchemaTable,
) -> MojoValidateResult {
    if data.is_null() || schema.is_null() {
        return MojoValidateResult::new(MojoValidateStatus::NullInput, 0);
    }

    let input = unsafe { core::slice::from_raw_parts(data, len) };

    if len < 24 {
        return MojoValidateResult::new(MojoValidateStatus::MessageTooShort, len as u32);
    }

    let mut header_bytes = [0u8; 4];
    if let Some(bytes) = input.get(0..4) {
        header_bytes.copy_from_slice(bytes);
    } else {
        return MojoValidateResult::new(MojoValidateStatus::MessageTooShort, 0);
    }
    let header_num_bytes = u32::from_le_bytes(header_bytes);

    if header_num_bytes != 24 && header_num_bytes != 32 {
        return MojoValidateResult::new(MojoValidateStatus::InvalidHeaderSize, 0);
    }
    if (header_num_bytes % 8) != 0 {
        return MojoValidateResult::new(MojoValidateStatus::InvalidAlignment, 0);
    }
    if len < header_num_bytes as usize {
        return MojoValidateResult::new(MojoValidateStatus::MessageTooShort, header_num_bytes);
    }

    let mut name_bytes = [0u8; 4];
    if let Some(bytes) = input.get(12..16) {
        name_bytes.copy_from_slice(bytes);
    } else {
        return MojoValidateResult::new(MojoValidateStatus::InvalidHeaderSize, 12);
    }
    let method_name = u32::from_le_bytes(name_bytes);

    let schema_table = unsafe { &*schema };
    if schema_table.methods.is_null() && schema_table.method_count > 0 {
        return MojoValidateResult::new(MojoValidateStatus::NullInput, 0);
    }
    let methods = unsafe { core::slice::from_raw_parts(schema_table.methods, schema_table.method_count as usize) };

    let mut found_method = None;
    for m in methods {
        if m.method_id == method_name {
            found_method = Some(m);
            break;
        }
    }
    let method = match found_method {
        Some(m) => m,
        None => return MojoValidateResult::new(MojoValidateStatus::UnknownMethod, 12),
    };

    let payload_offset = header_num_bytes as usize;
    let payload_len = len - payload_offset;

    if payload_len < method.expected_payload_size as usize {
        return MojoValidateResult::new(MojoValidateStatus::PayloadTooShort, payload_offset as u32);
    }

    if method.field_constraints.is_null() && method.field_count > 0 {
        return MojoValidateResult::new(MojoValidateStatus::NullInput, 0);
    }
    let fields = unsafe { core::slice::from_raw_parts(method.field_constraints, method.field_count as usize) };

    for field in fields {
        let f_offset = payload_offset + field.offset as usize;
        if field.is_nullable == 0 {
            let f_end = f_offset + field.expected_size as usize;
            if f_end > len {
                return MojoValidateResult::new(
                    MojoValidateStatus::FieldOutOfBounds,
                    (payload_offset as u32) + field.offset,
                );
            }
        } else if field.expected_size > 0 {
            let f_end = f_offset + field.expected_size as usize;
            if f_end > len {
                return MojoValidateResult::new(
                    MojoValidateStatus::FieldOutOfBounds,
                    (payload_offset as u32) + field.offset,
                );
            }
        }
    }

    MojoValidateResult::new(MojoValidateStatus::Ok, 0)
}

#[no_mangle]
pub unsafe extern "C" fn chromium_rust_mojo_validate_v1_internal(
    data: *const u8,
    len: usize,
    schema: *const MojoSchemaTable,
    out: *mut MojoValidateResult,
) -> u32 {
    if data.is_null() || schema.is_null() || out.is_null() {
        return MojoValidateStatus::NullInput as u32;
    }
    let res = unsafe { validate_mojo_message(data, len, schema) };
    unsafe { out.write(res) };
    res.status
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_valid_mojo_message() {
        let fields = [
            MojoFieldConstraint { offset: 0, expected_size: 4, is_nullable: 0 },
            MojoFieldConstraint { offset: 4, expected_size: 8, is_nullable: 1 },
        ];
        let methods = [
            MojoMethodConstraint {
                method_id: 42,
                expected_payload_size: 16,
                field_constraints: fields.as_ptr(),
                field_count: fields.len() as u32,
            },
        ];
        let schema = MojoSchemaTable {
            methods: methods.as_ptr(),
            method_count: methods.len() as u32,
        };

        // Construct 24 bytes header + 16 bytes payload = 40 bytes total message
        let mut msg = [0u8; 40];
        // num_bytes (header size) = 24
        msg[0..4].copy_from_slice(&24u32.to_le_bytes());
        // name (method_id) = 42
        msg[12..16].copy_from_slice(&42u32.to_le_bytes());

        let mut out = MojoValidateResult { status: 99, error_offset: 99 };
        let status = unsafe {
            chromium_rust_mojo_validate_v1_internal(
                msg.as_ptr(),
                msg.len(),
                &schema as *const _,
                &mut out as *mut _,
            )
        };

        assert_eq!(status, MojoValidateStatus::Ok as u32);
        assert_eq!(out.status, MojoValidateStatus::Ok as u32);
        assert_eq!(out.error_offset, 0);
    }
}
