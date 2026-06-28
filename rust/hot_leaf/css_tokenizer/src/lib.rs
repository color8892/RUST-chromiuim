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
pub enum TokenizeStatus {
    Ok = 0,
    Incomplete = 1,
    NullInput = 2,
    LengthOverflow = 3,
    OutputNull = 4,
    InvalidByte = 5,
    BadEscape = 6,
    UnclosedComment = 7,
    UnclosedString = 8,
    TooManyTokens = 9,
    TokenTooLong = 10,
    InvalidPolicy = 11,
}

impl TokenizeStatus {
    #[inline(always)]
    const fn code(self) -> u32 {
        self as u32
    }
}

#[repr(C)]
#[derive(Clone, Copy, Eq, PartialEq)]
#[cfg_attr(test, derive(Debug))]
pub struct ChromiumRustCssTokenizeResult {
    pub status: u32,
    pub token_count: u32,
    pub max_token_length: u32,
    pub bytes_consumed: usize,
}

impl ChromiumRustCssTokenizeResult {
    #[inline(always)]
    const fn new(status: TokenizeStatus) -> Self {
        Self {
            status: status.code(),
            token_count: 0,
            max_token_length: 0,
            bytes_consumed: 0,
        }
    }
}

#[derive(Clone, Copy, Eq, PartialEq)]
#[cfg_attr(test, derive(Debug))]
pub struct TokenizePolicy {
    max_tokens: u32,
    max_token_length: u32,
}

impl TokenizePolicy {
    #[inline(always)]
    pub const fn new(max_tokens: u32, max_token_length: u32) -> Option<Self> {
        if max_tokens == 0 || max_token_length == 0 {
            None
        } else {
            Some(Self {
                max_tokens,
                max_token_length,
            })
        }
    }
}

/// # Safety
///
/// `out` must point to a writable `ChromiumRustCssTokenizeResult` for the duration of this call.
/// If `len` is non-zero, `data` must point to `len` readable bytes for the duration of this call.
pub unsafe extern "C" fn chromium_rust_css_tokenize_v1_internal(
    data: *const u8,
    len: usize,
    max_tokens: u32,
    max_token_length: u32,
    out: *mut ChromiumRustCssTokenizeResult,
) -> u32 {
    if out.is_null() {
        return TokenizeStatus::OutputNull.code();
    }

    let result = match TokenizePolicy::new(max_tokens, max_token_length) {
        Some(policy) => tokenize_from_raw_parts(data, len, policy),
        None => ChromiumRustCssTokenizeResult::new(TokenizeStatus::InvalidPolicy),
    };

    unsafe {
        out.write(result);
    }
    result.status
}

#[inline(always)]
fn tokenize_from_raw_parts(
    data: *const u8,
    len: usize,
    policy: TokenizePolicy,
) -> ChromiumRustCssTokenizeResult {
    if len > isize::MAX as usize {
        return ChromiumRustCssTokenizeResult::new(TokenizeStatus::LengthOverflow);
    }
    if len == 0 {
        return tokenize_css(&[], policy);
    }
    if data.is_null() {
        return ChromiumRustCssTokenizeResult::new(TokenizeStatus::NullInput);
    }

    let input = unsafe { core::slice::from_raw_parts(data, len) };
    tokenize_css(input, policy)
}

#[inline(always)]
fn is_whitespace(b: u8) -> bool {
    matches!(b, b'\t' | b'\n' | b'\r' | b'\x0C' | b' ')
}

#[inline(always)]
fn is_ident(b: u8) -> bool {
    b.is_ascii_alphanumeric() || b == b'_' || b == b'-'
}

#[inline(always)]
fn is_ident_start(b: u8) -> bool {
    b.is_ascii_alphabetic() || b == b'_' || b == b'-'
}

struct ScanState {
    token_count: u32,
    observed_max_token_length: u32,
    bytes_consumed: usize,
}

impl ScanState {
    const fn new() -> Self {
        Self {
            token_count: 0,
            observed_max_token_length: 0,
            bytes_consumed: 0,
        }
    }

    fn record_token(
        &mut self,
        policy: TokenizePolicy,
        token_len: u32,
        cursor: usize,
    ) -> Option<ChromiumRustCssTokenizeResult> {
        if token_len > policy.max_token_length {
            return Some(self.error(TokenizeStatus::TokenTooLong, cursor));
        }
        if self.token_count >= policy.max_tokens {
            return Some(self.error(TokenizeStatus::TooManyTokens, cursor));
        }
        self.token_count += 1;
        if token_len > self.observed_max_token_length {
            self.observed_max_token_length = token_len;
        }
        self.bytes_consumed = cursor;
        None
    }

    fn error(&self, status: TokenizeStatus, cursor: usize) -> ChromiumRustCssTokenizeResult {
        ChromiumRustCssTokenizeResult {
            status: status.code(),
            token_count: self.token_count,
            max_token_length: self.observed_max_token_length,
            bytes_consumed: cursor,
        }
    }

    fn ok(self, total_len: usize) -> ChromiumRustCssTokenizeResult {
        ChromiumRustCssTokenizeResult {
            status: TokenizeStatus::Ok.code(),
            token_count: self.token_count,
            max_token_length: self.observed_max_token_length,
            bytes_consumed: total_len,
        }
    }
}

fn tokenize_css(input: &[u8], policy: TokenizePolicy) -> ChromiumRustCssTokenizeResult {
    let len = input.len();
    let base = input.as_ptr();
    let mut state = ScanState::new();
    let mut cursor = 0usize;

    while cursor < len {
        let b = unsafe { *base.add(cursor) };
        if b == 0 {
            return state.error(TokenizeStatus::InvalidByte, cursor);
        }

        if is_whitespace(b) {
            let start = cursor;
            cursor += 1;
            while cursor < len && is_whitespace(unsafe { *base.add(cursor) }) {
                cursor += 1;
            }
            if let Some(err) = state.record_token(policy, (cursor - start) as u32, cursor) {
                return err;
            }
            continue;
        }

        if b == b'/' && cursor + 1 < len && unsafe { *base.add(cursor + 1) } == b'*' {
            let start = cursor;
            cursor += 2;
            let mut closed = false;
            while cursor + 1 < len {
                if unsafe { *base.add(cursor) } == b'*' && unsafe { *base.add(cursor + 1) } == b'/' {
                    cursor += 2;
                    closed = true;
                    break;
                }
                cursor += 1;
            }
            if !closed {
                return state.error(TokenizeStatus::UnclosedComment, start);
            }
            if let Some(err) = state.record_token(policy, (cursor - start) as u32, cursor) {
                return err;
            }
            continue;
        }

        if b == b'\'' || b == b'"' {
            let quote = b;
            let start = cursor;
            cursor += 1;
            let mut closed = false;
            while cursor < len {
                let ch = unsafe { *base.add(cursor) };
                if ch == quote {
                    cursor += 1;
                    closed = true;
                    break;
                }
                if ch == b'\\' {
                    if cursor + 1 >= len {
                        return state.error(TokenizeStatus::BadEscape, cursor);
                    }
                    let next = unsafe { *base.add(cursor + 1) };
                    if next == b'\n' || next == b'\r' || next == b'\x0C' {
                        cursor += 2;
                        if cursor < len && next == b'\r' && unsafe { *base.add(cursor) } == b'\n' {
                            cursor += 1;
                        }
                        continue;
                    }
                    cursor += 2;
                    continue;
                }
                if ch == 0 {
                    return state.error(TokenizeStatus::InvalidByte, cursor);
                }
                cursor += 1;
            }
            if !closed {
                return state.error(TokenizeStatus::UnclosedString, start);
            }
            if let Some(err) = state.record_token(policy, (cursor - start) as u32, cursor) {
                return err;
            }
            continue;
        }

        if b == b'#' {
            let start = cursor;
            cursor += 1;
            while cursor < len && is_ident(unsafe { *base.add(cursor) }) {
                cursor += 1;
            }
            if let Some(err) = state.record_token(policy, (cursor - start) as u32, cursor) {
                return err;
            }
            continue;
        }

        if is_ident_start(b) {
            if b == b'-' {
                if cursor + 1 >= len || !is_ident(unsafe { *base.add(cursor + 1) }) {
                    if let Some(err) = state.record_token(policy, 1, cursor + 1) {
                        return err;
                    }
                    cursor += 1;
                    continue;
                }
            }
            let start = cursor;
            cursor += 1;
            while cursor < len && is_ident(unsafe { *base.add(cursor) }) {
                cursor += 1;
            }
            if let Some(err) = state.record_token(policy, (cursor - start) as u32, cursor) {
                return err;
            }
            continue;
        }

        if let Some(err) = state.record_token(policy, 1, cursor + 1) {
            return err;
        }
        cursor += 1;
    }

    state.ok(len)
}

#[cfg(test)]
mod tests {
    use super::*;

    const POLICY: TokenizePolicy = TokenizePolicy {
        max_tokens: 64,
        max_token_length: 128,
    };

    #[test]
    fn tokenizes_simple_stylesheet() {
        let css = b".class { color: red; }";
        let res = tokenize_css(css, POLICY);
        assert_eq!(res.status, TokenizeStatus::Ok.code());
        assert!(res.token_count >= 5);
        assert_eq!(res.bytes_consumed, css.len());
    }

    #[test]
    fn rejects_unclosed_string() {
        let css = b"\"unterminated";
        let res = tokenize_css(css, POLICY);
        assert_eq!(res.status, TokenizeStatus::UnclosedString.code());
    }

    #[test]
    fn rejects_unclosed_comment() {
        let css = b"/* comment";
        let res = tokenize_css(css, POLICY);
        assert_eq!(res.status, TokenizeStatus::UnclosedComment.code());
    }
}