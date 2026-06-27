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
pub enum UrlParseStatus {
    Ok = 0,
    NullInput = 1,
    LengthOverflow = 2,
    OutputNull = 3,
    InvalidScheme = 4,
    InvalidHost = 5,
    InvalidPort = 6,
}

#[repr(C)]
#[derive(Clone, Copy, Eq, PartialEq)]
#[cfg_attr(test, derive(Debug))]
pub struct ChromiumRustUrlComponent {
    pub begin: i32,
    pub len: i32,
}

impl ChromiumRustUrlComponent {
    const fn new(begin: i32, len: i32) -> Self {
        Self { begin, len }
    }

    const fn missing() -> Self {
        Self { begin: -1, len: -1 }
    }
}

#[repr(C)]
#[derive(Clone, Copy, Eq, PartialEq)]
#[cfg_attr(test, derive(Debug))]
pub struct ChromiumRustUrlParseResult {
    pub status: u32,
    pub scheme: ChromiumRustUrlComponent,
    pub username: ChromiumRustUrlComponent,
    pub password: ChromiumRustUrlComponent,
    pub host: ChromiumRustUrlComponent,
    pub port: i32,
    pub port_component: ChromiumRustUrlComponent,
    pub path: ChromiumRustUrlComponent,
    pub query: ChromiumRustUrlComponent,
    pub fragment: ChromiumRustUrlComponent,
}

impl ChromiumRustUrlParseResult {
    const fn new(status: UrlParseStatus) -> Self {
        Self {
            status: status as u32,
            scheme: ChromiumRustUrlComponent::missing(),
            username: ChromiumRustUrlComponent::missing(),
            password: ChromiumRustUrlComponent::missing(),
            host: ChromiumRustUrlComponent::missing(),
            port: -1,
            port_component: ChromiumRustUrlComponent::missing(),
            path: ChromiumRustUrlComponent::missing(),
            query: ChromiumRustUrlComponent::missing(),
            fragment: ChromiumRustUrlComponent::missing(),
        }
    }
}

/// # Safety
///
/// `out` must point to a writable `ChromiumRustUrlParseResult` for the duration of this call.
/// If `len` is non-zero, `data` must point to `len` readable bytes for the duration of this call.
pub unsafe extern "C" fn chromium_rust_url_parse_v1_internal(
    data: *const u8,
    len: usize,
    out: *mut ChromiumRustUrlParseResult,
) -> u32 {
    if out.is_null() {
        return UrlParseStatus::OutputNull as u32;
    }

    if len > isize::MAX as usize {
        let res = ChromiumRustUrlParseResult::new(UrlParseStatus::LengthOverflow);
        unsafe { out.write(res) };
        return res.status;
    }

    if len == 0 {
        let res = parse_url(&[]);
        unsafe { out.write(res) };
        return res.status;
    }

    if data.is_null() {
        let res = ChromiumRustUrlParseResult::new(UrlParseStatus::NullInput);
        unsafe { out.write(res) };
        return res.status;
    }

    // SAFETY: data is non-null, len <= isize::MAX, and Caller guarantees readability.
    let input = unsafe { core::slice::from_raw_parts(data, len) };
    let res = parse_url(input);
    unsafe { out.write(res) };
    res.status
}

/// # Safety
///
/// `out` must point to a writable `ChromiumRustUrlParseResult` for the duration of this call.
/// If `len` is non-zero, `data` must point to `len` readable bytes for the duration of this call.
/// Rust never stores either pointer after returning.
pub unsafe extern "C" fn chromium_rust_url_parse_v1(
    data: *const u8,
    len: usize,
    out: *mut ChromiumRustUrlParseResult,
) -> u32 {
    // SAFETY: caller guarantees the same pointer validity contract.
    unsafe { chromium_rust_url_parse_v1_internal(data, len, out) }
}

#[inline(always)]
fn parse_url(input: &[u8]) -> ChromiumRustUrlParseResult {
    let mut cursor = 0usize;
    let len = input.len();
    let base = input.as_ptr();

    let mut scheme = ChromiumRustUrlComponent::missing();
    let mut username = ChromiumRustUrlComponent::missing();
    let mut password = ChromiumRustUrlComponent::missing();
    let mut host = ChromiumRustUrlComponent::missing();
    let mut port_val = -1i32;
    let mut port_comp = ChromiumRustUrlComponent::missing();
    let mut path = ChromiumRustUrlComponent::missing();
    let mut query = ChromiumRustUrlComponent::missing();
    let mut fragment = ChromiumRustUrlComponent::missing();

    // 1. Parse Scheme: look for ':' before '/', '?', '#'
    let mut colon_idx = None;
    for i in 0..len {
        // SAFETY: i is in 0..len.
        let b = unsafe { *base.add(i) };
        if b == b':' {
            colon_idx = Some(i);
            break;
        }
        if b == b'/' || b == b'?' || b == b'#' {
            break;
        }
    }

    let authority_start = if let Some(idx) = colon_idx {
        // Validate scheme characters: RFC 3986: scheme = alpha *( alpha / digit / "+" / "-" / "." )
        let mut valid = idx > 0;
        if valid {
            // SAFETY: idx > 0 guarantees len > 0.
            let first = unsafe { *base };
            if !first.is_ascii_alphabetic() {
                valid = false;
            }
            for i in 1..idx {
                // SAFETY: i < idx <= len.
                let b = unsafe { *base.add(i) };
                if !b.is_ascii_alphanumeric() && b != b'+' && b != b'-' && b != b'.' {
                    valid = false;
                    break;
                }
            }
        }
        if !valid {
            return ChromiumRustUrlParseResult::new(UrlParseStatus::InvalidScheme);
        }
        scheme = ChromiumRustUrlComponent::new(0, idx as i32);
        cursor = idx + 1; // skip ':'

        // Check for double slash scheme separator (e.g. `://`)
        if cursor + 1 < len
            && unsafe { *base.add(cursor) } == b'/'
            && unsafe { *base.add(cursor + 1) } == b'/'
        {
            cursor += 2;
            true // has authority
        } else {
            false // no authority part (like mailto:)
        }
    } else {
        // Schemeless: if starts with `//`, authority starts after `//`
        if len >= 2 && unsafe { *base } == b'/' && unsafe { *base.add(1) } == b'/' {
            cursor = 2;
            true
        } else {
            false
        }
    };

    // 2. Parse Authority (Userinfo, Host, Port)
    if authority_start {
        // Find end of authority: first '/', '?', or '#'
        let mut auth_end = len;
        for i in cursor..len {
            // SAFETY: i is in cursor..len.
            let b = unsafe { *base.add(i) };
            if b == b'/' || b == b'?' || b == b'#' {
                auth_end = i;
                break;
            }
        }

        if cursor <= auth_end {
            // SAFETY: cursor and auth_end are bounded by len and cursor <= auth_end.
            let auth_span =
                unsafe { core::slice::from_raw_parts(base.add(cursor), auth_end - cursor) };
            let auth_len = auth_span.len();

            if auth_len > 0 {
                // Find userinfo separator `@`
                let mut at_idx = None;
                for (i, &b) in auth_span.iter().enumerate() {
                    if b == b'@' {
                        at_idx = Some(i);
                        break;
                    }
                }

                let (host_port_span, host_port_offset) = if let Some(idx) = at_idx {
                    // Parse userinfo
                    if let Some(userinfo) = auth_span.get(..idx) {
                        let mut user_colon = None;
                        for (j, &b) in userinfo.iter().enumerate() {
                            if b == b':' {
                                user_colon = Some(j);
                                break;
                            }
                        }

                        if let Some(c_idx) = user_colon {
                            username = ChromiumRustUrlComponent::new(cursor as i32, c_idx as i32);
                            password = ChromiumRustUrlComponent::new(
                                (cursor + c_idx + 1) as i32,
                                (userinfo.len() - c_idx - 1) as i32,
                            );
                        } else {
                            username =
                                ChromiumRustUrlComponent::new(cursor as i32, userinfo.len() as i32);
                        }
                    }

                    (
                        // SAFETY: idx is within auth_span and idx + 1 <= auth_span.len().
                        unsafe {
                            core::slice::from_raw_parts(
                                auth_span.as_ptr().add(idx + 1),
                                auth_span.len() - idx - 1,
                            )
                        },
                        cursor + idx + 1,
                    )
                } else {
                    (auth_span, cursor)
                };

                // Parse Host & Port
                let hp_len = host_port_span.len();
                if hp_len > 0 {
                    // Look for port separator `:` (scanning backwards to support IPv6 host like `[::1]:80`)
                    let mut last_colon = None;
                    let hp_base = host_port_span.as_ptr();
                    for j in (0..hp_len).rev() {
                        // SAFETY: j is in 0..hp_len.
                        if unsafe { *hp_base.add(j) } == b':' {
                            // Ensure we aren't matching colons inside IPv6 brackets
                            let mut inside_brackets = false;
                            let mut has_bracket_end = false;
                            for k in j..hp_len {
                                // SAFETY: k is in j..hp_len.
                                if unsafe { *hp_base.add(k) } == b']' {
                                    has_bracket_end = true;
                                    break;
                                }
                            }
                            for k in 0..j {
                                // SAFETY: k is in 0..j.
                                if unsafe { *hp_base.add(k) } == b'[' {
                                    if has_bracket_end {
                                        inside_brackets = true;
                                    }
                                    break;
                                }
                            }
                            if !inside_brackets {
                                last_colon = Some(j);
                                break;
                            }
                        }
                    }

                    let host_span = if let Some(c_idx) = last_colon {
                        // Extract port component
                        // SAFETY: c_idx is within host_port_span.
                        let port_span = unsafe {
                            core::slice::from_raw_parts(
                                hp_base.add(c_idx + 1),
                                hp_len - c_idx - 1,
                            )
                        };
                        if !port_span.is_empty() {
                            // Parse port number manually
                            let mut val = 0u32;
                            let mut valid_port = true;
                            for &b in port_span {
                                if b.is_ascii_digit() {
                                    val = val.saturating_mul(10).saturating_add((b - b'0') as u32);
                                    if val > 65535 {
                                        valid_port = false;
                                    }
                                } else {
                                    valid_port = false;
                                    break;
                                }
                            }
                            if valid_port {
                                port_val = val as i32;
                            } else {
                                return ChromiumRustUrlParseResult::new(
                                    UrlParseStatus::InvalidPort,
                                );
                            }
                            port_comp = ChromiumRustUrlComponent::new(
                                (host_port_offset + c_idx + 1) as i32,
                                port_span.len() as i32,
                            );
                        }
                        // SAFETY: c_idx <= hp_len.
                        unsafe { core::slice::from_raw_parts(hp_base, c_idx) }
                    } else {
                        host_port_span
                    };

                    // Validate Host characters: should not contain spaces or controls
                    for &b in host_span {
                        if b <= 32 || b >= 127 || b == b'/' || b == b'?' || b == b'#' {
                            return ChromiumRustUrlParseResult::new(UrlParseStatus::InvalidHost);
                        }
                    }

                    host = ChromiumRustUrlComponent::new(
                        host_port_offset as i32,
                        host_span.len() as i32,
                    );
                }
            }
        }
        cursor = auth_end;
    }

    // 3. Parse Path, Query, Fragment
    if cursor < len && unsafe { *base.add(cursor) } != b'?' && unsafe { *base.add(cursor) } != b'#' {
        let mut path_end = len;
        for i in cursor..len {
            // SAFETY: i is in cursor..len.
            let b = unsafe { *base.add(i) };
            if b == b'?' || b == b'#' {
                path_end = i;
                break;
            }
        }
        path = ChromiumRustUrlComponent::new(cursor as i32, (path_end - cursor) as i32);
        cursor = path_end;
    }

    if cursor < len && unsafe { *base.add(cursor) } == b'?' {
        let mut query_end = len;
        for i in (cursor + 1)..len {
            // SAFETY: i is in cursor + 1..len.
            if unsafe { *base.add(i) } == b'#' {
                query_end = i;
                break;
            }
        }
        query = ChromiumRustUrlComponent::new((cursor + 1) as i32, (query_end - cursor - 1) as i32);
        cursor = query_end;
    }

    if cursor < len && unsafe { *base.add(cursor) } == b'#' {
        fragment = ChromiumRustUrlComponent::new((cursor + 1) as i32, (len - cursor - 1) as i32);
    }

    ChromiumRustUrlParseResult {
        status: UrlParseStatus::Ok as u32,
        scheme,
        username,
        password,
        host,
        port: port_val,
        port_component: port_comp,
        path,
        query,
        fragment,
    }
}

/// Canonicalizes the host by converting ASCII uppercase characters to lowercase,
/// and returns the written length if valid.
pub fn canonicalize_host(host: &[u8], out: &mut [u8]) -> Option<usize> {
    if host.len() > out.len() {
        return None;
    }
    for i in 0..host.len() {
        // SAFETY: host.len() <= out.len(), and i is in [0, host.len())
        unsafe {
            let b = *host.get_unchecked(i);
            if b <= 32 || b >= 127 || b == b'/' || b == b'?' || b == b'#' {
                return None;
            }
            *out.get_unchecked_mut(i) = b.to_ascii_lowercase();
        }
    }
    Some(host.len())
}

/// Decodes percent-encoded characters in place or into a buffer, but only
/// decodes alphanumeric characters (RFC 3986 safe) and validates UTF-8.
pub fn percent_decode_safe(input: &[u8], out: &mut [u8]) -> Option<usize> {
    let mut in_idx = 0usize;
    let mut out_idx = 0usize;
    let in_len = input.len();

    while in_idx < in_len {
        // SAFETY: in_idx is strictly less than in_len
        let b = unsafe { *input.get_unchecked(in_idx) };
        if b == b'%' {
            if in_idx + 2 < in_len {
                // SAFETY: in_idx + 2 < in_len
                let h1 = unsafe { *input.get_unchecked(in_idx + 1) };
                let h2 = unsafe { *input.get_unchecked(in_idx + 2) };
                if let (Some(d1), Some(d2)) = (hex_digit(h1), hex_digit(h2)) {
                    let decoded = (d1 << 4) | d2;
                    // Only decode alphanumeric and safe characters: A-Z, a-z, 0-9, -, ., _, ~
                    let should_decode = decoded.is_ascii_alphanumeric()
                        || decoded == b'-'
                        || decoded == b'.'
                        || decoded == b'_'
                        || decoded == b'~';
                    if should_decode {
                        if out_idx < out.len() {
                            // SAFETY: out_idx is checked
                            unsafe { *out.get_unchecked_mut(out_idx) = decoded; }
                            out_idx += 1;
                        } else {
                            return None;
                        }
                    } else {
                        // Keep percent encoded representation
                        if out_idx + 2 < out.len() {
                            // SAFETY: out_idx + 2 is checked
                            unsafe {
                                *out.get_unchecked_mut(out_idx) = b'%';
                                *out.get_unchecked_mut(out_idx + 1) = h1;
                                *out.get_unchecked_mut(out_idx + 2) = h2;
                            }
                            out_idx += 3;
                        } else {
                            return None;
                        }
                    }
                    in_idx += 3;
                    continue;
                }
            }
            // If % is not followed by 2 hex digits, we treat the URL as invalid/malformed
            return None;
        } else {
            if out_idx < out.len() {
                // SAFETY: out_idx is checked
                unsafe { *out.get_unchecked_mut(out_idx) = b; }
                out_idx += 1;
            } else {
                return None;
            }
            in_idx += 1;
        }
    }
    Some(out_idx)
}

fn hex_digit(b: u8) -> Option<u8> {
    match b {
        b'0'..=b'9' => Some(b - b'0'),
        b'a'..=b'f' => Some(b - b'a' + 10),
        b'A'..=b'F' => Some(b - b'A' + 10),
        _ => None,
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn parses_simple_http_url() {
        let url = b"http://example.com/path?query=1#frag";
        let res = parse_url(url);

        assert_eq!(res.status, UrlParseStatus::Ok as u32);
        assert_eq!(res.scheme, ChromiumRustUrlComponent::new(0, 4));
        assert_eq!(res.host, ChromiumRustUrlComponent::new(7, 11));
        assert_eq!(res.port, -1);
        assert_eq!(res.path, ChromiumRustUrlComponent::new(18, 5));
        assert_eq!(res.query, ChromiumRustUrlComponent::new(24, 7));
        assert_eq!(res.fragment, ChromiumRustUrlComponent::new(32, 4));
    }

    #[test]
    fn parses_userinfo_and_port() {
        let url = b"ftp://user:pass@127.0.0.1:21/dir";
        let res = parse_url(url);

        assert_eq!(res.status, UrlParseStatus::Ok as u32);
        assert_eq!(res.scheme, ChromiumRustUrlComponent::new(0, 3));
        assert_eq!(res.username, ChromiumRustUrlComponent::new(6, 4));
        assert_eq!(res.password, ChromiumRustUrlComponent::new(11, 4));
        assert_eq!(res.host, ChromiumRustUrlComponent::new(16, 9));
        assert_eq!(res.port, 21);
        assert_eq!(res.path, ChromiumRustUrlComponent::new(28, 4));
    }

    #[test]
    fn parses_ipv6_host_with_port() {
        let url = b"http://[::1]:8080/";
        let res = parse_url(url);

        assert_eq!(res.status, UrlParseStatus::Ok as u32);
        assert_eq!(res.host, ChromiumRustUrlComponent::new(7, 5));
        assert_eq!(res.port, 8080);
    }

    #[test]
    fn rejects_invalid_ports() {
        let url = b"http://example.com:99999/";
        let res = parse_url(url);
        assert_eq!(res.status, UrlParseStatus::InvalidPort as u32);

        let url_bad_chars = b"http://example.com:80a/";
        let res_bad = parse_url(url_bad_chars);
        assert_eq!(res_bad.status, UrlParseStatus::InvalidPort as u32);
    }

    #[test]
    fn test_canonicalize_host() {
        let mut buf = [0u8; 32];
        let len = canonicalize_host(b"GOOgle.COM", &mut buf).unwrap();
        assert_eq!(&buf[..len], b"google.com");

        assert!(canonicalize_host(b"google.com/path", &mut buf).is_none());
        assert!(canonicalize_host(b"google.com?", &mut buf).is_none());
    }

    #[test]
    fn test_percent_decode_safe() {
        let mut buf = [0u8; 64];
        
        // %41 -> A, %2f -> %2f (not decoded because it's not alphanumeric or safe)
        let len = percent_decode_safe(b"hello%41world%2f%2Ffoo", &mut buf).unwrap();
        assert_eq!(&buf[..len], b"helloAworld%2f%2Ffoo");

        // Invalid hex
        assert!(percent_decode_safe(b"hello%4gworld", &mut buf).is_none());
        // Truncated percent
        assert!(percent_decode_safe(b"hello%", &mut buf).is_none());
    }
}
