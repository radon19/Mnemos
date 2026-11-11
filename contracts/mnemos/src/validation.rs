use crate::types::*;

pub fn fail(code: &str, message: &str) -> String {
    format!("{code}: {message}")
}

pub fn is_valid_scope(scope: &str) -> bool {
    let bytes = scope.as_bytes();
    !bytes.is_empty()
        && bytes.len() <= MAX_SCOPE_LEN
        && bytes
            .iter()
            .all(|b| matches!(b, b'a'..=b'z' | b'0'..=b'9' | b'-'))
}

pub fn is_lower_hex_64(value: &str) -> bool {
    value.len() == 64
        && value
            .bytes()
            .all(|b| matches!(b, b'0'..=b'9' | b'a'..=b'f'))
}

pub fn validate_scopes(scopes: &[String]) -> Result<(), String> {
    if scopes.is_empty() {
        return Err(fail(E_INVALID_SCOPE, "at least one scope is required"));
    }
    if scopes.len() > MAX_SCOPES {
        return Err(fail(
            E_INVALID_SCOPE,
            &format!("at most {MAX_SCOPES} scopes are allowed"),
        ));
    }
    let mut seen: Vec<&str> = Vec::with_capacity(scopes.len());
    for scope in scopes {
        if !is_valid_scope(scope) {
            return Err(fail(E_INVALID_SCOPE, "scope must match [a-z0-9-]{1,32}"));
        }
        if seen.contains(&scope.as_str()) {
            return Err(fail(E_INVALID_SCOPE, "scopes must be unique"));
        }
        seen.push(scope);
    }
    Ok(())
}

pub fn validate_reason(reason: &str) -> Result<(), String> {
    let trimmed = reason.trim();
    if trimmed.is_empty() || reason.len() > MAX_REASON_LEN {
        return Err(fail(
            E_INVALID_REASON,
            &format!("reason must be 1 to {MAX_REASON_LEN} bytes"),
        ));
    }
    if reason.chars().any(char::is_control) {
        return Err(fail(
            E_INVALID_REASON,
            "reason must not contain control characters",
        ));
    }
    Ok(())
}
