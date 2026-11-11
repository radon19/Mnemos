use near_sdk::env;
use serde_json::{json, Value};

/// NEP-297 style event. The log line is `EVENT_JSON:` followed by JSON with
/// standard, version, event and data fields.
pub fn emit(event: &str, data: Value) {
    let payload = json!({
        "standard": "mnemos",
        "version": "1.0.0",
        "event": event,
        "data": data,
    });
    let encoded = serde_json::to_string(&payload).expect("event JSON serialization cannot fail");
    env::log_str(&format!("EVENT_JSON:{encoded}"));
}
