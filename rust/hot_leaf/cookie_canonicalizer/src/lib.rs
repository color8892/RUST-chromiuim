#![cfg_attr(not(test), no_std)]
#![deny(unsafe_op_in_unsafe_fn)]
#![deny(clippy::expect_used)]
#![deny(clippy::panic)]
#![deny(clippy::print_stdout)]
#![deny(clippy::print_stderr)]
#![deny(clippy::todo)]
#![deny(clippy::unwrap_used)]

#[repr(u32)]
#[derive(Clone, Copy, Eq, PartialEq)]
#[cfg_attr(test, derive(Debug))]
pub enum CanonicalizeStatus {
    Ok = 0,
    Incomplete = 1,
    NullInput = 2,
    LengthOverflow = 3,
    OutputNull = 4,
    InvalidByte = 5,
    EmptyName = 6,
    InvalidName = 7,
    UnclosedQuote = 8,
    TooManyAttributes = 9,
    AttrNameTooLong = 10,
    AttrValueTooLong = 11,
    InvalidPolicy = 12,
    InvalidSameSite = 13,
}

impl CanonicalizeStatus {
    #[inline(always)]
    const fn code(self) -> u32 {
        self as u32
    }
}

#[repr(u32)]
#[derive(Clone, Copy, Eq, PartialEq)]
#[cfg_attr(test, derive(Debug))]
pub enum SameSiteValue {
    None = 0,
    Strict = 1,
    Lax = 2,
    NoneValue = 3,
}

#[repr(C)]
#[derive(Clone, Copy, Eq, PartialEq)]
#[cfg_attr(test, derive(Debug))]
pub struct ChromiumRustCookieComponent {
    pub begin: i32,
    pub len: i32,
}

impl ChromiumRustCookieComponent {
    #[inline(always)]
    const fn missing() -> Self {
        Self { begin: -1, len: -1 }
    }

    #[inline(always)]
    const fn span(begin: usize, len: usize) -> Self {
        Self {
            begin: begin as i32,
            len: len as i32,
        }
    }
}

#[repr(C)]
#[derive(Clone, Copy, Eq, PartialEq)]
#[cfg_attr(test, derive(Debug))]
pub struct ChromiumRustCookieCanonicalizeResult {
    pub status: u32,
    pub name: ChromiumRustCookieComponent,
    pub value: ChromiumRustCookieComponent,
    pub attribute_count: u32,
    pub max_attr_name_length: u32,
    pub max_attr_value_length: u32,
    pub has_secure: u8,
    pub has_httponly: u8,
    pub same_site: u32,
    pub bytes_consumed: usize,
}

impl ChromiumRustCookieCanonicalizeResult {
    #[inline(always)]
    const fn new(status: CanonicalizeStatus) -> Self {
        Self {
            status: status.code(),
            name: ChromiumRustCookieComponent::missing(),
            value: ChromiumRustCookieComponent::missing(),
            attribute_count: 0,
            max_attr_name_length: 0,
            max_attr_value_length: 0,
            has_secure: 0,
            has_httponly: 0,
            same_site: SameSiteValue::None as u32,
            bytes_consumed: 0,
        }
    }
}

#[derive(Clone, Copy, Eq, PartialEq)]
#[cfg_attr(test, derive(Debug))]
pub struct CanonicalizePolicy {
    max_attributes: u32,
    max_attr_name_length: u32,
    max_attr_value_length: u32,
}

impl CanonicalizePolicy {
    #[inline(always)]
    pub const fn new(
        max_attributes: u32,
        max_attr_name_length: u32,
        max_attr_value_length: u32,
    ) -> Option<Self> {
        if max_attributes == 0 || max_attr_name_length == 0 || max_attr_value_length == 0 {
            None
        } else {
            Some(Self {
                max_attributes,
                max_attr_name_length,
                max_attr_value_length,
            })
        }
    }
}

/// # Safety
///
/// `out` must point to a writable `ChromiumRustCookieCanonicalizeResult` for the duration of this call.
/// If `len` is non-zero, `data` must point to `len` readable bytes for the duration of this call.
pub unsafe extern "C" fn chromium_rust_cookie_canonicalize_v1_internal(
    data: *const u8,
    len: usize,
    max_attributes: u32,
    max_attr_name_length: u32,
    max_attr_value_length: u32,
    out: *mut ChromiumRustCookieCanonicalizeResult,
) -> u32 {
    if out.is_null() {
        return CanonicalizeStatus::OutputNull.code();
    }

    let result = match CanonicalizePolicy::new(
        max_attributes,
        max_attr_name_length,
        max_attr_value_length,
    ) {
        Some(policy) => canonicalize_from_raw_parts(data, len, policy),
        None => ChromiumRustCookieCanonicalizeResult::new(CanonicalizeStatus::InvalidPolicy),
    };

    unsafe {
        out.write(result);
    }
    result.status
}

#[inline(always)]
fn canonicalize_from_raw_parts(
    data: *const u8,
    len: usize,
    policy: CanonicalizePolicy,
) -> ChromiumRustCookieCanonicalizeResult {
    if len > isize::MAX as usize {
        return ChromiumRustCookieCanonicalizeResult::new(CanonicalizeStatus::LengthOverflow);
    }
    if len == 0 {
        return canonicalize_cookie(&[], policy);
    }
    if data.is_null() {
        return ChromiumRustCookieCanonicalizeResult::new(CanonicalizeStatus::NullInput);
    }

    let input = unsafe { core::slice::from_raw_parts(data, len) };
    canonicalize_cookie(input, policy)
}

#[inline(always)]
fn is_ctl(b: u8) -> bool {
    b < 0x20 || b == 0x7F
}

#[inline(always)]
fn is_separator(b: u8) -> bool {
    matches!(
        b,
        b'(' | b')' | b'<' | b'>' | b'@' | b',' | b';' | b':' | b'\\' | b'"' | b'/' | b'['
            | b']' | b'?' | b'=' | b'{' | b'}' | b' ' | b'\t'
    )
}

#[inline(always)]
fn is_token_char(b: u8) -> bool {
    !is_ctl(b) && !is_separator(b)
}

#[inline(always)]
fn is_ows(b: u8) -> bool {
    b == b' ' || b == b'\t'
}

#[inline(always)]
fn ascii_eq_ignore_case(left: &[u8], right: &[u8]) -> bool {
    if left.len() != right.len() {
        return false;
    }
    for i in 0..left.len() {
        let a = left[i];
        let b = right[i];
        let la = if a >= b'A' && a <= b'Z' { a + 32 } else { a };
        let lb = if b >= b'A' && b <= b'Z' { b + 32 } else { b };
        if la != lb {
            return false;
        }
    }
    true
}

struct ScanState {
    attribute_count: u32,
    max_attr_name_length: u32,
    max_attr_value_length: u32,
    has_secure: u8,
    has_httponly: u8,
    same_site: u32,
    bytes_consumed: usize,
}

impl ScanState {
    const fn new() -> Self {
        Self {
            attribute_count: 0,
            max_attr_name_length: 0,
            max_attr_value_length: 0,
            has_secure: 0,
            has_httponly: 0,
            same_site: SameSiteValue::None as u32,
            bytes_consumed: 0,
        }
    }

    fn finish(
        self,
        status: CanonicalizeStatus,
        name: ChromiumRustCookieComponent,
        value: ChromiumRustCookieComponent,
    ) -> ChromiumRustCookieCanonicalizeResult {
        ChromiumRustCookieCanonicalizeResult {
            status: status.code(),
            name,
            value,
            attribute_count: self.attribute_count,
            max_attr_name_length: self.max_attr_name_length,
            max_attr_value_length: self.max_attr_value_length,
            has_secure: self.has_secure,
            has_httponly: self.has_httponly,
            same_site: self.same_site,
            bytes_consumed: self.bytes_consumed,
        }
    }

    fn error(
        &self,
        status: CanonicalizeStatus,
        name: ChromiumRustCookieComponent,
        value: ChromiumRustCookieComponent,
        cursor: usize,
    ) -> ChromiumRustCookieCanonicalizeResult {
        ChromiumRustCookieCanonicalizeResult {
            status: status.code(),
            name,
            value,
            attribute_count: self.attribute_count,
            max_attr_name_length: self.max_attr_name_length,
            max_attr_value_length: self.max_attr_value_length,
            has_secure: self.has_secure,
            has_httponly: self.has_httponly,
            same_site: self.same_site,
            bytes_consumed: cursor,
        }
    }
}

fn canonicalize_cookie(
    input: &[u8],
    policy: CanonicalizePolicy,
) -> ChromiumRustCookieCanonicalizeResult {
    let len = input.len();
    let base = input.as_ptr();
    let mut state = ScanState::new();
    let mut cursor = 0usize;

    while cursor < len && is_ows(unsafe { *base.add(cursor) }) {
        cursor += 1;
    }

    if cursor >= len {
        return state.error(
            CanonicalizeStatus::EmptyName,
            ChromiumRustCookieComponent::missing(),
            ChromiumRustCookieComponent::missing(),
            cursor,
        );
    }

    let name_start = cursor;
    while cursor < len {
        let b = unsafe { *base.add(cursor) };
        if b == 0 {
            return state.error(
                CanonicalizeStatus::InvalidByte,
                ChromiumRustCookieComponent::missing(),
                ChromiumRustCookieComponent::missing(),
                cursor,
            );
        }
        if !is_token_char(b) {
            break;
        }
        cursor += 1;
    }

    if cursor == name_start {
        return state.error(
            CanonicalizeStatus::EmptyName,
            ChromiumRustCookieComponent::missing(),
            ChromiumRustCookieComponent::missing(),
            cursor,
        );
    }

    let name = ChromiumRustCookieComponent::span(name_start, cursor - name_start);
    let mut value = ChromiumRustCookieComponent::span(cursor, 0);

    if cursor < len && unsafe { *base.add(cursor) } == b'=' {
        cursor += 1;
        if cursor >= len {
            value = ChromiumRustCookieComponent::span(cursor, 0);
            state.bytes_consumed = cursor;
            return state.finish(CanonicalizeStatus::Ok, name, value);
        }

        let value_start = cursor;
        let first = unsafe { *base.add(cursor) };
        if first == b'"' {
            cursor += 1;
            let mut closed = false;
            while cursor < len {
                let b = unsafe { *base.add(cursor) };
                if b == 0 {
                    return state.error(
                        CanonicalizeStatus::InvalidByte,
                        name,
                        value,
                        cursor,
                    );
                }
                if b == b'"' {
                    cursor += 1;
                    closed = true;
                    break;
                }
                cursor += 1;
            }
            if !closed {
                return state.error(
                    CanonicalizeStatus::UnclosedQuote,
                    name,
                    ChromiumRustCookieComponent::span(value_start, cursor - value_start),
                    value_start,
                );
            }
            value = ChromiumRustCookieComponent::span(value_start + 1, cursor - value_start - 2);
        } else {
            while cursor < len {
                let b = unsafe { *base.add(cursor) };
                if b == 0 {
                    return state.error(
                        CanonicalizeStatus::InvalidByte,
                        name,
                        value,
                        cursor,
                    );
                }
                if b == b';' {
                    break;
                }
                cursor += 1;
            }
            value = ChromiumRustCookieComponent::span(value_start, cursor - value_start);
        }
    }

    state.bytes_consumed = cursor;

    while cursor < len {
        if unsafe { *base.add(cursor) } != b';' {
            return state.error(
                CanonicalizeStatus::InvalidName,
                name,
                value,
                cursor,
            );
        }
        cursor += 1;

        while cursor < len && is_ows(unsafe { *base.add(cursor) }) {
            cursor += 1;
        }
        if cursor >= len {
            return state.error(
                CanonicalizeStatus::Incomplete,
                name,
                value,
                cursor,
            );
        }

        let attr_start = cursor;
        while cursor < len {
            let b = unsafe { *base.add(cursor) };
            if b == 0 {
                return state.error(
                    CanonicalizeStatus::InvalidByte,
                    name,
                    value,
                    cursor,
                );
            }
            if !is_token_char(b) {
                break;
            }
            cursor += 1;
        }

        if cursor == attr_start {
            return state.error(
                CanonicalizeStatus::Incomplete,
                name,
                value,
                cursor,
            );
        }

        let attr_name_len = (cursor - attr_start) as u32;
        if attr_name_len > policy.max_attr_name_length {
            return state.error(
                CanonicalizeStatus::AttrNameTooLong,
                name,
                value,
                attr_start,
            );
        }
        if attr_name_len > state.max_attr_name_length {
            state.max_attr_name_length = attr_name_len;
        }

        let attr_name = unsafe { core::slice::from_raw_parts(base.add(attr_start), cursor - attr_start) };

        if cursor < len && unsafe { *base.add(cursor) } == b'=' {
            cursor += 1;
            if cursor >= len {
                return state.error(
                    CanonicalizeStatus::Incomplete,
                    name,
                    value,
                    cursor,
                );
            }
            let value_start = cursor;
            while cursor < len {
                let b = unsafe { *base.add(cursor) };
                if b == 0 {
                    return state.error(
                        CanonicalizeStatus::InvalidByte,
                        name,
                        value,
                        cursor,
                    );
                }
                if b == b';' {
                    break;
                }
                cursor += 1;
            }
            let attr_value_len = (cursor - value_start) as u32;
            if attr_value_len > policy.max_attr_value_length {
                return state.error(
                    CanonicalizeStatus::AttrValueTooLong,
                    name,
                    value,
                    value_start,
                );
            }
            if attr_value_len > state.max_attr_value_length {
                state.max_attr_value_length = attr_value_len;
            }

            if ascii_eq_ignore_case(attr_name, b"SameSite") {
                let attr_value =
                    unsafe { core::slice::from_raw_parts(base.add(value_start), cursor - value_start) };
                if ascii_eq_ignore_case(attr_value, b"Strict") {
                    state.same_site = SameSiteValue::Strict as u32;
                } else if ascii_eq_ignore_case(attr_value, b"Lax") {
                    state.same_site = SameSiteValue::Lax as u32;
                } else if ascii_eq_ignore_case(attr_value, b"None") {
                    state.same_site = SameSiteValue::NoneValue as u32;
                } else {
                    return state.error(
                        CanonicalizeStatus::InvalidSameSite,
                        name,
                        value,
                        value_start,
                    );
                }
            }
        } else if ascii_eq_ignore_case(attr_name, b"Secure") {
            state.has_secure = 1;
        } else if ascii_eq_ignore_case(attr_name, b"HttpOnly") {
            state.has_httponly = 1;
        }

        if state.attribute_count >= policy.max_attributes {
            return state.error(
                CanonicalizeStatus::TooManyAttributes,
                name,
                value,
                attr_start,
            );
        }
        state.attribute_count += 1;
        state.bytes_consumed = cursor;
    }

    state.finish(CanonicalizeStatus::Ok, name, value)
}

#[cfg(test)]
mod tests {
    use super::*;

    const POLICY: CanonicalizePolicy = CanonicalizePolicy {
        max_attributes: 16,
        max_attr_name_length: 64,
        max_attr_value_length: 256,
    };

    #[test]
    fn canonicalizes_simple_cookie() {
        let cookie = b"session_id=abc123; Path=/; Secure; HttpOnly; SameSite=Strict";
        let res = canonicalize_cookie(cookie, POLICY);
        assert_eq!(res.status, CanonicalizeStatus::Ok.code());
        assert_eq!(res.name.begin, 0);
        assert_eq!(res.name.len, 10);
        assert_eq!(res.value.begin, 11);
        assert_eq!(res.value.len, 6);
        assert_eq!(res.attribute_count, 4);
        assert_eq!(res.has_secure, 1);
        assert_eq!(res.has_httponly, 1);
        assert_eq!(res.same_site, SameSiteValue::Strict as u32);
        assert_eq!(res.bytes_consumed, cookie.len());
    }

    #[test]
    fn rejects_unclosed_quoted_value() {
        let cookie = b"name=\"unterminated";
        let res = canonicalize_cookie(cookie, POLICY);
        assert_eq!(res.status, CanonicalizeStatus::UnclosedQuote.code());
    }

    #[test]
    fn rejects_invalid_samesite() {
        let cookie = b"name=value; SameSite=Bad";
        let res = canonicalize_cookie(cookie, POLICY);
        assert_eq!(res.status, CanonicalizeStatus::InvalidSameSite.code());
    }

    #[test]
    fn accepts_name_without_value() {
        let cookie = b"flag";
        let res = canonicalize_cookie(cookie, POLICY);
        assert_eq!(res.status, CanonicalizeStatus::Ok.code());
        assert_eq!(res.name.len, 4);
        assert_eq!(res.value.len, 0);
    }
}