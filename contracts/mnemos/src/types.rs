use near_sdk::json_types::U128;
use near_sdk::store::LookupMap;
use near_sdk::{AccountId, BorshStorageKey};

pub const DAY_NS: u64 = 86_400_000_000_000;
pub const REQUEST_TTL_NS: u64 = 600_000_000_000;
pub const MAX_GRANTS_PER_OWNER: usize = 32;
pub const MAX_SCOPES: usize = 16;
pub const MAX_SCOPE_LEN: usize = 32;
pub const MAX_DAILY_CAP: u32 = 10_000;
pub const MIN_ANSWER_TOKENS: u32 = 16;
pub const MAX_ANSWER_TOKENS: u32 = 8_192;
pub const MAX_PRICE_YOCTO: u128 = 1_000u128 * 1_000_000_000_000_000_000_000_000u128;
pub const MAX_GRANT_DURATION_NS: u64 = 365 * DAY_NS;
pub const RECENT_RECEIPTS_CAP: usize = 50;
pub const RECENT_SERVED_CAP: usize = 512;
pub const MAX_PENDING_PER_AGENT: u32 = 32;
pub const MAX_REASON_LEN: usize = 200;

pub const E_NOT_CONTRACT_OWNER: &str = "E_NOT_CONTRACT_OWNER";
pub const E_NOT_BROKER: &str = "E_NOT_BROKER";
pub const E_BROKER_NOT_SET: &str = "E_BROKER_NOT_SET";
pub const E_GRANT_NOT_FOUND: &str = "E_GRANT_NOT_FOUND";
pub const E_GRANT_REVOKED: &str = "E_GRANT_REVOKED";
pub const E_GRANT_EXPIRED: &str = "E_GRANT_EXPIRED";
pub const E_SCOPE_DENIED: &str = "E_SCOPE_DENIED";
pub const E_CAP_REACHED: &str = "E_CAP_REACHED";
pub const E_INSUFFICIENT_CREDIT: &str = "E_INSUFFICIENT_CREDIT";
pub const E_INSUFFICIENT_BALANCE: &str = "E_INSUFFICIENT_BALANCE";
pub const E_PAUSED: &str = "E_PAUSED";
pub const E_INVALID_SCOPE: &str = "E_INVALID_SCOPE";
pub const E_INVALID_PRICE: &str = "E_INVALID_PRICE";
pub const E_INVALID_CAP: &str = "E_INVALID_CAP";
pub const E_INVALID_EXPIRY: &str = "E_INVALID_EXPIRY";
pub const E_INVALID_TOKENS: &str = "E_INVALID_TOKENS";
pub const E_INVALID_FINGERPRINT: &str = "E_INVALID_FINGERPRINT";
pub const E_INVALID_AGENT: &str = "E_INVALID_AGENT";
pub const E_INVALID_OWNER: &str = "E_INVALID_OWNER";
pub const E_INVALID_HASH: &str = "E_INVALID_HASH";
pub const E_INVALID_AMOUNT: &str = "E_INVALID_AMOUNT";
pub const E_INVALID_REASON: &str = "E_INVALID_REASON";
pub const E_REQUEST_NOT_FOUND: &str = "E_REQUEST_NOT_FOUND";
pub const E_REQUEST_NOT_APPROVED: &str = "E_REQUEST_NOT_APPROVED";
pub const E_REQUEST_NOT_EXPIRED: &str = "E_REQUEST_NOT_EXPIRED";
pub const E_DUPLICATE_RECEIPT: &str = "E_DUPLICATE_RECEIPT";
pub const E_TOO_MANY_GRANTS: &str = "E_TOO_MANY_GRANTS";
pub const E_TOO_MANY_PENDING: &str = "E_TOO_MANY_PENDING";
pub const E_OVERFLOW: &str = "E_OVERFLOW";
pub const E_CALLBACK_ONLY: &str = "E_CALLBACK_ONLY";

#[near_sdk::near(serializers = [borsh])]
#[derive(BorshStorageKey)]
pub enum StorageKey {
    Brokers,
    Grants,
    GrantsByOwner,
    Credits,
    Earnings,
    Requests,
    Receipts,
    PendingByAgent,
}

#[near_sdk::near(serializers = [borsh])]
#[derive(Clone, PartialEq, Eq, PartialOrd, Ord)]
pub struct GrantKey {
    pub owner: AccountId,
    pub agent: AccountId,
}

#[near_sdk::near(serializers = [borsh, json])]
#[derive(Clone)]
pub struct BrokerInfo {
    pub broker_account: AccountId,
    pub broker_pubkey_fingerprint: String,
}

#[near_sdk::near(serializers = [borsh])]
#[derive(Clone)]
pub struct Grant {
    pub owner: AccountId,
    pub agent: AccountId,
    pub scopes: Vec<String>,
    pub price: u128,
    pub daily_cap: u32,
    pub expires_ns: u64,
    pub max_answer_tokens: u32,
    pub revoked: bool,
    pub used_today: u32,
    pub day_index: u64,
}

#[near_sdk::near(serializers = [borsh])]
#[derive(Clone, Copy, PartialEq, Eq)]
pub enum RequestStatus {
    Approved,
    Served,
}

impl RequestStatus {
    pub fn as_str(self) -> &'static str {
        match self {
            RequestStatus::Approved => "Approved",
            RequestStatus::Served => "Served",
        }
    }
}

#[near_sdk::near(serializers = [borsh])]
#[derive(Clone)]
pub struct ReadReq {
    pub id: u64,
    pub owner: AccountId,
    pub agent: AccountId,
    pub scope: String,
    pub price: u128,
    pub q_hash: String,
    pub status: RequestStatus,
    pub created_ns: u64,
    pub receipt_hash: Option<String>,
}

#[near_sdk::near(serializers = [borsh])]
#[derive(Clone)]
pub struct ReceiptEntry {
    pub req_id: u64,
    pub agent: AccountId,
    pub scope: String,
    pub price: u128,
    pub receipt_hash: String,
    pub served_ns: u64,
}

#[near_sdk::near(serializers = [json])]
pub struct GrantView {
    pub owner: AccountId,
    pub agent: AccountId,
    pub scopes: Vec<String>,
    pub price: U128,
    pub daily_cap: u32,
    pub expires_ns: U128,
    pub max_answer_tokens: u32,
    pub revoked: bool,
    pub used_today: u32,
    pub remaining_today: u32,
    pub day_index: u64,
}

#[near_sdk::near(serializers = [json])]
pub struct ReadReqView {
    pub id: u64,
    pub owner: AccountId,
    pub agent: AccountId,
    pub scope: String,
    pub price: U128,
    pub q_hash: String,
    pub status: String,
    pub created_ns: U128,
    pub receipt_hash: Option<String>,
}

#[near_sdk::near(serializers = [json])]
pub struct ReceiptView {
    pub req_id: u64,
    pub agent: AccountId,
    pub scope: String,
    pub price: U128,
    pub receipt_hash: String,
    pub served_ns: U128,
}

#[near_sdk::near(serializers = [json])]
pub struct ConfigView {
    pub owner: AccountId,
    pub paused: bool,
    pub next_request_id: u64,
    pub request_ttl_ns: U128,
    pub day_ns: U128,
}

pub type Brokers = LookupMap<AccountId, BrokerInfo>;
pub type Grants = LookupMap<GrantKey, Grant>;
pub type GrantsByOwner = LookupMap<AccountId, Vec<AccountId>>;
pub type Balances = LookupMap<AccountId, u128>;
pub type Requests = LookupMap<u64, ReadReq>;
pub type Receipts = LookupMap<AccountId, Vec<ReceiptEntry>>;
pub type Pending = LookupMap<AccountId, u32>;
