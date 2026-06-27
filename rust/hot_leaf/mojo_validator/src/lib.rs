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

pub unsafe fn validate_mojo_message(
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

#[cfg(any(test, feature = "prototype"))]
pub struct MojoMessageReader<'a> {
    data: &'a [u8],
    payload_offset: usize,
}

#[cfg(any(test, feature = "prototype"))]
impl<'a> MojoMessageReader<'a> {
    pub fn new(data: &'a [u8]) -> Option<Self> {
        if data.len() < 24 {
            return None;
        }
        let header_num_bytes = u32::from_le_bytes([data[0], data[1], data[2], data[3]]) as usize;
        if header_num_bytes < 24 || header_num_bytes > data.len() {
            return None;
        }
        Some(Self {
            data,
            payload_offset: header_num_bytes,
        })
    }

    pub fn get_field_u32(&self, offset: usize) -> Option<u32> {
        let f_offset = self.payload_offset + offset;
        if f_offset + 4 > self.data.len() {
            return None;
        }
        // SAFETY: boundary check guarantees slice index validity
        unsafe {
            let b0 = *self.data.get_unchecked(f_offset);
            let b1 = *self.data.get_unchecked(f_offset + 1);
            let b2 = *self.data.get_unchecked(f_offset + 2);
            let b3 = *self.data.get_unchecked(f_offset + 3);
            Some(u32::from_le_bytes([b0, b1, b2, b3]))
        }
    }

    pub fn get_field_bytes(&self, offset: usize, size: usize) -> Option<&'a [u8]> {
        let f_offset = self.payload_offset + offset;
        if f_offset + size > self.data.len() {
            return None;
        }
        // SAFETY: boundary check guarantees pointer dereference validity
        unsafe {
            Some(core::slice::from_raw_parts(self.data.as_ptr().add(f_offset), size))
        }
    }

    pub fn get_field_str(&self, offset: usize, size: usize) -> Option<&'a str> {
        let bytes = self.get_field_bytes(offset, size)?;
        core::str::from_utf8(bytes).ok()
    }

    pub fn get_field_string(&self, offset: usize) -> Option<&'a str> {
        let ptr_offset = self.payload_offset + offset;
        if ptr_offset + 8 > self.data.len() {
            return None;
        }
        
        let rel_offset = unsafe {
            let b0 = *self.data.get_unchecked(ptr_offset);
            let b1 = *self.data.get_unchecked(ptr_offset + 1);
            let b2 = *self.data.get_unchecked(ptr_offset + 2);
            let b3 = *self.data.get_unchecked(ptr_offset + 3);
            let b4 = *self.data.get_unchecked(ptr_offset + 4);
            let b5 = *self.data.get_unchecked(ptr_offset + 5);
            let b6 = *self.data.get_unchecked(ptr_offset + 6);
            let b7 = *self.data.get_unchecked(ptr_offset + 7);
            u64::from_le_bytes([b0, b1, b2, b3, b4, b5, b6, b7]) as usize
        };
        
        if rel_offset == 0 {
            return None;
        }
        
        let abs_offset = ptr_offset + rel_offset;
        if abs_offset + 8 > self.data.len() {
            return None;
        }
        
        let num_bytes = unsafe {
            let b0 = *self.data.get_unchecked(abs_offset);
            let b1 = *self.data.get_unchecked(abs_offset + 1);
            let b2 = *self.data.get_unchecked(abs_offset + 2);
            let b3 = *self.data.get_unchecked(abs_offset + 3);
            u32::from_le_bytes([b0, b1, b2, b3]) as usize
        };
        
        let num_elements = unsafe {
            let b0 = *self.data.get_unchecked(abs_offset + 4);
            let b1 = *self.data.get_unchecked(abs_offset + 5);
            let b2 = *self.data.get_unchecked(abs_offset + 6);
            let b3 = *self.data.get_unchecked(abs_offset + 7);
            u32::from_le_bytes([b0, b1, b2, b3]) as usize
        };
        
        if abs_offset + num_bytes > self.data.len() || 8 + num_elements > num_bytes {
            return None;
        }
        
        unsafe {
            let ptr = self.data.as_ptr().add(abs_offset + 8);
            let slice = core::slice::from_raw_parts(ptr, num_elements);
            core::str::from_utf8(slice).ok()
        }
    }

    pub fn get_field_array_u32(&self, offset: usize, out: &mut [u32]) -> Option<usize> {
        let ptr_offset = self.payload_offset + offset;
        if ptr_offset + 8 > self.data.len() {
            return None;
        }
        
        let rel_offset = unsafe {
            let b0 = *self.data.get_unchecked(ptr_offset);
            let b1 = *self.data.get_unchecked(ptr_offset + 1);
            let b2 = *self.data.get_unchecked(ptr_offset + 2);
            let b3 = *self.data.get_unchecked(ptr_offset + 3);
            let b4 = *self.data.get_unchecked(ptr_offset + 4);
            let b5 = *self.data.get_unchecked(ptr_offset + 5);
            let b6 = *self.data.get_unchecked(ptr_offset + 6);
            let b7 = *self.data.get_unchecked(ptr_offset + 7);
            u64::from_le_bytes([b0, b1, b2, b3, b4, b5, b6, b7]) as usize
        };
        
        if rel_offset == 0 {
            return Some(0);
        }
        
        let abs_offset = ptr_offset + rel_offset;
        if abs_offset + 8 > self.data.len() {
            return None;
        }
        
        let num_bytes = unsafe {
            let b0 = *self.data.get_unchecked(abs_offset);
            let b1 = *self.data.get_unchecked(abs_offset + 1);
            let b2 = *self.data.get_unchecked(abs_offset + 2);
            let b3 = *self.data.get_unchecked(abs_offset + 3);
            u32::from_le_bytes([b0, b1, b2, b3]) as usize
        };
        
        let num_elements = unsafe {
            let b0 = *self.data.get_unchecked(abs_offset + 4);
            let b1 = *self.data.get_unchecked(abs_offset + 5);
            let b2 = *self.data.get_unchecked(abs_offset + 6);
            let b3 = *self.data.get_unchecked(abs_offset + 7);
            u32::from_le_bytes([b0, b1, b2, b3]) as usize
        };
        
        if abs_offset + num_bytes > self.data.len() || 8 + num_elements * 4 > num_bytes {
            return None;
        }
        
        let copy_len = core::cmp::min(num_elements, out.len());
        for i in 0..copy_len {
            let item_offset = abs_offset + 8 + i * 4;
            unsafe {
                let b0 = *self.data.get_unchecked(item_offset);
                let b1 = *self.data.get_unchecked(item_offset + 1);
                let b2 = *self.data.get_unchecked(item_offset + 2);
                let b3 = *self.data.get_unchecked(item_offset + 3);
                out[i] = u32::from_le_bytes([b0, b1, b2, b3]);
            }
        }
        Some(num_elements)
    }
}

#[cfg(any(test, feature = "prototype"))]
pub struct MojoMessageBuilder<'a> {
    buf: &'a mut [u8],
    next_offset: usize,
}

#[cfg(any(test, feature = "prototype"))]
impl<'a> MojoMessageBuilder<'a> {
    pub fn new(buf: &'a mut [u8], initial_payload_size: usize) -> Self {
        Self {
            buf,
            next_offset: 24 + initial_payload_size,
        }
    }

    pub fn write_header(&mut self, header_size: u32, method_id: u32) -> Result<(), ()> {
        if self.buf.len() < header_size as usize {
            return Err(());
        }
        self.buf[0..4].copy_from_slice(&header_size.to_le_bytes());
        if header_size >= 16 {
            self.buf[12..16].copy_from_slice(&method_id.to_le_bytes());
        }
        Ok(())
    }

    pub fn write_field_u32(&mut self, payload_offset: usize, offset: usize, val: u32) -> Result<(), ()> {
        let f_offset = payload_offset + offset;
        if f_offset + 4 > self.buf.len() {
            return Err(());
        }
        self.buf[f_offset..f_offset + 4].copy_from_slice(&val.to_le_bytes());
        Ok(())
    }

    pub fn write_field_bytes(&mut self, payload_offset: usize, offset: usize, data: &[u8]) -> Result<(), ()> {
        let f_offset = payload_offset + offset;
        if f_offset + data.len() > self.buf.len() {
            return Err(());
        }
        self.buf[f_offset..f_offset + data.len()].copy_from_slice(data);
        Ok(())
    }

    pub fn write_field_string(&mut self, payload_offset: usize, offset: usize, val: &str) -> Result<(), ()> {
        let ptr_offset = payload_offset + offset;
        if ptr_offset + 8 > self.buf.len() {
            return Err(());
        }
        
        let aligned_offset = (self.next_offset + 7) & !7;
        let rel_offset = (aligned_offset - ptr_offset) as u64;
        self.buf[ptr_offset..ptr_offset + 8].copy_from_slice(&rel_offset.to_le_bytes());
        
        let num_elements = val.len();
        let num_bytes = (8 + num_elements + 7) & !7;
        
        if aligned_offset + num_bytes > self.buf.len() {
            return Err(());
        }
        
        self.buf[aligned_offset..aligned_offset + 4].copy_from_slice(&(num_bytes as u32).to_le_bytes());
        self.buf[aligned_offset + 4..aligned_offset + 8].copy_from_slice(&(num_elements as u32).to_le_bytes());
        self.buf[aligned_offset + 8..aligned_offset + 8 + num_elements].copy_from_slice(val.as_bytes());
        
        for i in (8 + num_elements)..num_bytes {
            self.buf[aligned_offset + i] = 0;
        }
        
        self.next_offset = aligned_offset + num_bytes;
        Ok(())
    }

    pub fn write_field_array_u32(&mut self, payload_offset: usize, offset: usize, val: &[u32]) -> Result<(), ()> {
        let ptr_offset = payload_offset + offset;
        if ptr_offset + 8 > self.buf.len() {
            return Err(());
        }
        
        let aligned_offset = (self.next_offset + 7) & !7;
        let rel_offset = (aligned_offset - ptr_offset) as u64;
        self.buf[ptr_offset..ptr_offset + 8].copy_from_slice(&rel_offset.to_le_bytes());
        
        let num_elements = val.len();
        let num_bytes = (8 + num_elements * 4 + 7) & !7;
        
        if aligned_offset + num_bytes > self.buf.len() {
            return Err(());
        }
        
        self.buf[aligned_offset..aligned_offset + 4].copy_from_slice(&(num_bytes as u32).to_le_bytes());
        self.buf[aligned_offset + 4..aligned_offset + 8].copy_from_slice(&(num_elements as u32).to_le_bytes());
        
        for i in 0..num_elements {
            let item_offset = aligned_offset + 8 + i * 4;
            self.buf[item_offset..item_offset + 4].copy_from_slice(&val[i].to_le_bytes());
        }
        
        for i in (8 + num_elements * 4)..num_bytes {
            self.buf[aligned_offset + i] = 0;
        }
        
        self.next_offset = aligned_offset + num_bytes;
        Ok(())
    }

    pub fn next_offset(&self) -> usize {
        self.next_offset
    }
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

        let mut msg = [0u8; 40];
        msg[0..4].copy_from_slice(&24u32.to_le_bytes());
        msg[12..16].copy_from_slice(&42u32.to_le_bytes());

        let res = unsafe { validate_mojo_message(msg.as_ptr(), msg.len(), &schema as *const _) };
        assert_eq!(res.status, MojoValidateStatus::Ok as u32);
        assert_eq!(res.error_offset, 0);
    }

    #[test]
    fn test_mojo_reader_writer_roundtrip() {
        let mut buffer = [0u8; 128];
        let mut builder = MojoMessageBuilder::new(&mut buffer, 16);

        assert!(builder.write_header(24, 101).is_ok());
        assert!(builder.write_field_u32(24, 0, 9999).is_ok());
        assert!(builder.write_field_string(24, 8, "hello_mojo_string").is_ok());

        let reader = MojoMessageReader::new(&buffer).expect("Reader init");
        assert_eq!(reader.get_field_u32(0), Some(9999));
        assert_eq!(reader.get_field_string(8), Some("hello_mojo_string"));
    }

    #[test]
    fn test_mojo_array_roundtrip() {
        let mut buffer = [0u8; 128];
        let mut builder = MojoMessageBuilder::new(&mut buffer, 16);

        assert!(builder.write_header(24, 102).is_ok());
        assert!(builder.write_field_array_u32(24, 0, &[10, 20, 30, 40]).is_ok());

        let reader = MojoMessageReader::new(&buffer).expect("Reader init");
        let mut out = [0u32; 4];
        let len = reader.get_field_array_u32(0, &mut out).expect("Read array");
        assert_eq!(len, 4);
        assert_eq!(out, [10, 20, 30, 40]);
    }
}
