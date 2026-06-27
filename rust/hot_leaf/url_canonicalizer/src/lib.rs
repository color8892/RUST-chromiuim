#![cfg_attr(all(not(test), not(feature = "std")), no_std)]
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

fn parse_url(input: &[u8]) -> ChromiumRustUrlParseResult {
    let mut cursor = 0usize;
    let len = input.len();

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
        if let Some(&b) = input.get(i) {
            if b == b':' {
                colon_idx = Some(i);
                break;
            }
            if b == b'/' || b == b'?' || b == b'#' {
                break;
            }
        }
    }

    let authority_start = if let Some(idx) = colon_idx {
        // Validate scheme characters: RFC 3986: scheme = alpha *( alpha / digit / "+" / "-" / "." )
        let mut valid = idx > 0;
        if valid {
            if let Some(&first) = input.first() {
                if !first.is_ascii_alphabetic() {
                    valid = false;
                }
            } else {
                valid = false;
            }
            if let Some(sub) = input.get(1..idx) {
                for &b in sub {
                    if !b.is_ascii_alphanumeric() && b != b'+' && b != b'-' && b != b'.' {
                        valid = false;
                        break;
                    }
                }
            } else {
                valid = false;
            }
        }
        if !valid {
            return ChromiumRustUrlParseResult::new(UrlParseStatus::InvalidScheme);
        }
        scheme = ChromiumRustUrlComponent::new(0, idx as i32);
        cursor = idx + 1; // skip ':'

        // Check for double slash scheme separator (e.g. `://`)
        if cursor + 1 < len
            && input.get(cursor) == Some(&b'/')
            && input.get(cursor + 1) == Some(&b'/')
        {
            cursor += 2;
            true // has authority
        } else {
            false // no authority part (like mailto:)
        }
    } else {
        // Schemeless: if starts with `//`, authority starts after `//`
        if len >= 2 && input.first() == Some(&b'/') && input.get(1) == Some(&b'/') {
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
            if let Some(&b) = input.get(i) {
                if b == b'/' || b == b'?' || b == b'#' {
                    auth_end = i;
                    break;
                }
            }
        }

        if let Some(auth_span) = input.get(cursor..auth_end) {
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

                    (auth_span.get(idx + 1..).unwrap_or(&[]), cursor + idx + 1)
                } else {
                    (auth_span, cursor)
                };

                // Parse Host & Port
                let hp_len = host_port_span.len();
                if hp_len > 0 {
                    // Look for port separator `:` (scanning backwards to support IPv6 host like `[::1]:80`)
                    let mut last_colon = None;
                    for j in (0..hp_len).rev() {
                        if host_port_span.get(j) == Some(&b':') {
                            // Ensure we aren't matching colons inside IPv6 brackets
                            let mut inside_brackets = false;
                            let mut has_bracket_end = false;
                            for k in j..hp_len {
                                if host_port_span.get(k) == Some(&b']') {
                                    has_bracket_end = true;
                                    break;
                                }
                            }
                            for k in 0..j {
                                if host_port_span.get(k) == Some(&b'[') {
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
                        let port_span = host_port_span.get(c_idx + 1..).unwrap_or(&[]);
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
                        host_port_span.get(..c_idx).unwrap_or(&[])
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
    if cursor < len && input.get(cursor) != Some(&b'?') && input.get(cursor) != Some(&b'#') {
        let mut path_end = len;
        for i in cursor..len {
            if let Some(&b) = input.get(i) {
                if b == b'?' || b == b'#' {
                    path_end = i;
                    break;
                }
            }
        }
        path = ChromiumRustUrlComponent::new(cursor as i32, (path_end - cursor) as i32);
        cursor = path_end;
    }

    if cursor < len && input.get(cursor) == Some(&b'?') {
        let mut query_end = len;
        for i in (cursor + 1)..len {
            if input.get(i) == Some(&b'#') {
                query_end = i;
                break;
            }
        }
        query = ChromiumRustUrlComponent::new((cursor + 1) as i32, (query_end - cursor - 1) as i32);
        cursor = query_end;
    }

    if cursor < len && input.get(cursor) == Some(&b'#') {
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
}
