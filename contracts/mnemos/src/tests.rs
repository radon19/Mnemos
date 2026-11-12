use super::*;
use near_sdk::json_types::U128;
use near_sdk::test_utils::{get_logs, VMContextBuilder};
use near_sdk::{testing_env, AccountId, NearToken, PromiseResult, RuntimeFeesConfig, VMContext};

const CONTRACT: &str = "mnemos.testnet";
const OWNER: &str = "owner.testnet";
const AGENT: &str = "agent.testnet";
const BROKER: &str = "broker.testnet";
const STRANGER: &str = "stranger.testnet";
const START: u64 = 1_700_000_000_000_000_000;
const PRICE: u128 = 10_000_000_000_000_000_000_000_000; // 0.01 NEAR
const HASH_A: &str = "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa";
const FINGERPRINT: &str = "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb";

fn acct(value: &str) -> AccountId {
    value.parse().expect("valid account id")
}

fn context(predecessor: &str, deposit: u128, timestamp: u64) -> VMContext {
    VMContextBuilder::new()
        .current_account_id(acct(CONTRACT))
        .predecessor_account_id(acct(predecessor))
        .attached_deposit(NearToken::from_yoctonear(deposit))
        .block_timestamp(timestamp)
        .build()
}

fn with_context(predecessor: &str, deposit: u128, timestamp: u64) {
    testing_env!(context(predecessor, deposit, timestamp));
}

fn with_promise_results(predecessor: &str, timestamp: u64, results: Vec<PromiseResult>) {
    testing_env!(
        context(predecessor, 0, timestamp),
        near_sdk::test_vm_config(),
        RuntimeFeesConfig::test(),
        Default::default(),
        results
    );
}

fn new_contract() -> Contract {
    with_context(OWNER, 0, START);
    Contract::new(acct(OWNER))
}

fn register_broker(contract: &mut Contract) {
    with_context(OWNER, 0, START);
    contract
        .set_broker(acct(BROKER), FINGERPRINT.to_string())
        .expect("broker registration");
}

fn create_grant(contract: &mut Contract, price: u128, cap: u32, expires: u64) {
    with_context(OWNER, 0, START);
    contract
        .create_grant(
            acct(AGENT),
            vec!["travel".to_string(), "preferences".to_string()],
            U128(price),
            cap,
            U128(expires.into()),
            128,
        )
        .expect("grant creation");
}

fn deposit(contract: &mut Contract, amount: u128) {
    with_context(AGENT, amount, START);
    contract.deposit_credit().expect("credit deposit");
}

fn request(contract: &mut Contract, scope: &str) -> u64 {
    with_context(AGENT, 0, START);
    contract
        .request_read(acct(OWNER), scope.to_string(), HASH_A.to_string())
        .expect("read request")
}

fn serve(contract: &mut Contract, req_id: u64) {
    with_context(BROKER, 0, START);
    contract
        .record_receipt(req_id, HASH_A.to_string())
        .expect("receipt");
}

#[test]
fn broker_and_grant_are_registered_and_viewed() {
    let mut contract = new_contract();
    register_broker(&mut contract);
    let broker = contract.get_broker(acct(OWNER)).expect("broker");
    assert_eq!(broker.broker_account, acct(BROKER));
    assert_eq!(broker.broker_pubkey_fingerprint, FINGERPRINT);

    create_grant(&mut contract, PRICE, 3, START + DAY_NS);
    let grant = contract.get_grant(acct(OWNER), acct(AGENT)).expect("grant");
    assert_eq!(grant.scopes, vec!["travel", "preferences"]);
    assert_eq!(grant.price.0, PRICE);
    assert_eq!(grant.remaining_today, 3);
    assert!(!grant.revoked);
    assert!(get_logs()
        .iter()
        .any(|line| line.contains("\"event\":\"grant_created\"")));
}

#[test]
fn grants_by_owner_lists_every_grant_the_owner_gave() {
    let mut contract = new_contract();
    create_grant(&mut contract, PRICE, 3, START + DAY_NS);
    with_context(OWNER, 0, START);
    contract
        .create_grant(
            acct("second-agent.testnet"),
            vec!["work".to_string()],
            U128(PRICE),
            1,
            U128((START + 2 * DAY_NS).into()),
            128,
        )
        .expect("second grant");

    let grants = contract.grants_by_owner(acct(OWNER));
    assert_eq!(grants.len(), 2);
    assert_eq!(grants[0].agent, acct("second-agent.testnet"));
    assert_eq!(grants[1].agent, acct(AGENT));
    assert_eq!(grants[1].scopes, vec!["travel", "preferences"]);

    // Another owner sees nothing.
    assert!(contract.grants_by_owner(acct("other.testnet")).is_empty());
}

#[test]
fn invalid_inputs_are_rejected() {
    let mut contract = new_contract();
    with_context(OWNER, 0, START);
    let err = contract
        .create_grant(
            acct(AGENT),
            vec!["Travel".to_string()],
            U128(PRICE),
            1,
            U128((START + DAY_NS).into()),
            64,
        )
        .unwrap_err();
    assert!(err.starts_with(E_INVALID_SCOPE));

    let err = contract
        .create_grant(
            acct(AGENT),
            vec!["travel".to_string()],
            U128(MAX_PRICE_YOCTO + 1),
            1,
            U128((START + DAY_NS).into()),
            64,
        )
        .unwrap_err();
    assert!(err.starts_with(E_INVALID_PRICE));

    let err = contract
        .create_grant(
            acct(AGENT),
            vec!["travel".to_string()],
            U128(PRICE),
            0,
            U128((START + DAY_NS).into()),
            64,
        )
        .unwrap_err();
    assert!(err.starts_with(E_INVALID_CAP));

    let err = contract
        .create_grant(
            acct(AGENT),
            vec!["travel".to_string()],
            U128(PRICE),
            1,
            U128((START).into()),
            64,
        )
        .unwrap_err();
    assert!(err.starts_with(E_INVALID_EXPIRY));

    let err = contract
        .create_grant(
            acct(AGENT),
            vec!["travel".to_string()],
            U128(PRICE),
            1,
            U128((START + DAY_NS).into()),
            1,
        )
        .unwrap_err();
    assert!(err.starts_with(E_INVALID_TOKENS));

    let err = contract
        .set_broker(acct(BROKER), "not-a-fingerprint".to_string())
        .unwrap_err();
    assert!(err.starts_with(E_INVALID_FINGERPRINT));
}

#[test]
fn read_escrows_credit_and_receipt_pays_owner() {
    let mut contract = new_contract();
    register_broker(&mut contract);
    create_grant(&mut contract, PRICE, 5, START + DAY_NS);
    deposit(&mut contract, PRICE * 3);
    assert_eq!(contract.credit_of(acct(AGENT)).0, PRICE * 3);

    let req_id = request(&mut contract, "travel");
    assert_eq!(contract.credit_of(acct(AGENT)).0, PRICE * 2);
    let req = contract.get_request(req_id).expect("request");
    assert_eq!(req.status, "Approved");
    assert_eq!(req.price.0, PRICE);

    serve(&mut contract, req_id);
    assert_eq!(contract.credit_of(acct(AGENT)).0, PRICE * 2);
    assert_eq!(contract.earnings_of(acct(OWNER)).0, PRICE);
    assert!(contract.get_request(req_id).is_none());
    let receipts = contract.recent_receipts(acct(OWNER), 0, 10);
    assert_eq!(receipts.len(), 1);
    assert_eq!(receipts[0].req_id, req_id);
    assert_eq!(receipts[0].scope, "travel");

    with_context(BROKER, 0, START);
    let err = contract
        .record_receipt(req_id, HASH_A.to_string())
        .unwrap_err();
    assert!(err.starts_with(E_DUPLICATE_RECEIPT));
}

#[test]
fn revoked_expired_scope_and_credit_paths() {
    let mut contract = new_contract();
    register_broker(&mut contract);
    create_grant(&mut contract, PRICE, 5, START + DAY_NS);
    deposit(&mut contract, PRICE);

    with_context(AGENT, 0, START);
    let err = contract
        .request_read(acct(OWNER), "work".to_string(), HASH_A.to_string())
        .unwrap_err();
    assert!(err.starts_with(E_SCOPE_DENIED));

    with_context(OWNER, 0, START);
    contract.revoke_grant(acct(AGENT)).expect("revoke");
    with_context(AGENT, 0, START);
    let err = contract
        .request_read(acct(OWNER), "travel".to_string(), HASH_A.to_string())
        .unwrap_err();
    assert!(err.starts_with(E_GRANT_REVOKED));

    let mut expired = new_contract();
    register_broker(&mut expired);
    create_grant(&mut expired, PRICE, 5, START + 10_000_000_000);
    deposit(&mut expired, PRICE);
    with_context(AGENT, 0, START + 11_000_000_000);
    let err = expired
        .request_read(acct(OWNER), "travel".to_string(), HASH_A.to_string())
        .unwrap_err();
    assert!(err.starts_with(E_GRANT_EXPIRED));

    let mut broke = new_contract();
    register_broker(&mut broke);
    create_grant(&mut broke, PRICE, 5, START + DAY_NS);
    with_context(AGENT, 0, START);
    let err = broke
        .request_read(acct(OWNER), "travel".to_string(), HASH_A.to_string())
        .unwrap_err();
    assert!(err.starts_with(E_INSUFFICIENT_CREDIT));
}

#[test]
fn daily_cap_blocks_then_resets_next_day() {
    let mut contract = new_contract();
    register_broker(&mut contract);
    create_grant(&mut contract, PRICE, 1, START + 3 * DAY_NS);
    deposit(&mut contract, PRICE * 2);

    let first = request(&mut contract, "travel");
    with_context(AGENT, 0, START);
    let err = contract
        .request_read(acct(OWNER), "travel".to_string(), HASH_A.to_string())
        .unwrap_err();
    assert!(err.starts_with(E_CAP_REACHED));

    let next_day = START + DAY_NS;
    with_context(AGENT, 0, next_day);
    let second = contract
        .request_read(acct(OWNER), "travel".to_string(), HASH_A.to_string())
        .expect("next-day request");
    assert_ne!(first, second);
    let grant = contract.get_grant(acct(OWNER), acct(AGENT)).expect("grant");
    assert_eq!(grant.used_today, 1);
    assert_eq!(grant.remaining_today, 0);
}

#[test]
fn refund_restores_credit_and_cap() {
    let mut contract = new_contract();
    register_broker(&mut contract);
    create_grant(&mut contract, PRICE, 2, START + DAY_NS);
    deposit(&mut contract, PRICE);
    let req_id = request(&mut contract, "travel");
    assert_eq!(contract.credit_of(acct(AGENT)).0, 0);

    with_context(BROKER, 0, START);
    contract
        .refund(req_id, "model verification failed".to_string())
        .expect("refund");
    assert_eq!(contract.credit_of(acct(AGENT)).0, PRICE);
    assert!(contract.get_request(req_id).is_none());
    let grant = contract.get_grant(acct(OWNER), acct(AGENT)).expect("grant");
    assert_eq!(grant.used_today, 0);

    with_context(STRANGER, 0, START);
    let err = contract.refund(req_id, "again".to_string()).unwrap_err();
    assert!(err.starts_with(E_REQUEST_NOT_FOUND));
}

#[test]
fn expiry_restores_credit_and_is_permissionless() {
    let mut contract = new_contract();
    register_broker(&mut contract);
    create_grant(&mut contract, PRICE, 2, START + DAY_NS);
    deposit(&mut contract, PRICE);
    let req_id = request(&mut contract, "travel");

    with_context(STRANGER, 0, START + REQUEST_TTL_NS - 1);
    let err = contract.expire_request(req_id).unwrap_err();
    assert!(err.starts_with(E_REQUEST_NOT_EXPIRED));

    with_context(STRANGER, 0, START + REQUEST_TTL_NS + 1);
    contract.expire_request(req_id).expect("expire");
    assert_eq!(contract.credit_of(acct(AGENT)).0, PRICE);
    assert!(contract.get_request(req_id).is_none());
}

#[test]
fn non_broker_cannot_record_or_refund() {
    let mut contract = new_contract();
    register_broker(&mut contract);
    create_grant(&mut contract, PRICE, 2, START + DAY_NS);
    deposit(&mut contract, PRICE);
    let req_id = request(&mut contract, "travel");

    with_context(STRANGER, 0, START);
    let err = contract
        .record_receipt(req_id, HASH_A.to_string())
        .unwrap_err();
    assert!(err.starts_with(E_NOT_BROKER));

    with_context(STRANGER, 0, START);
    let err = contract
        .refund(req_id, "not allowed".to_string())
        .unwrap_err();
    assert!(err.starts_with(E_NOT_BROKER));
}

#[test]
fn pause_blocks_new_grants_and_reads() {
    let mut contract = new_contract();
    register_broker(&mut contract);
    create_grant(&mut contract, PRICE, 2, START + DAY_NS);
    deposit(&mut contract, PRICE);

    with_context(OWNER, 0, START);
    contract.pause().expect("pause");
    with_context(OWNER, 0, START);
    let err = contract
        .create_grant(
            acct(AGENT),
            vec!["work".to_string()],
            U128(PRICE),
            1,
            U128((START + DAY_NS).into()),
            64,
        )
        .unwrap_err();
    assert!(err.starts_with(E_PAUSED));
    with_context(AGENT, 0, START);
    let err = contract
        .request_read(acct(OWNER), "travel".to_string(), HASH_A.to_string())
        .unwrap_err();
    assert!(err.starts_with(E_PAUSED));

    with_context(STRANGER, 0, START);
    assert!(contract
        .pause()
        .unwrap_err()
        .starts_with(E_NOT_CONTRACT_OWNER));
    with_context(OWNER, 0, START);
    contract.unpause().expect("unpause");
    request(&mut contract, "travel");
}

#[test]
fn withdrawal_failure_callbacks_restore_balances() {
    let mut contract = new_contract();
    register_broker(&mut contract);
    create_grant(&mut contract, PRICE, 5, START + DAY_NS);
    deposit(&mut contract, PRICE * 2);
    let req_id = request(&mut contract, "travel");
    serve(&mut contract, req_id);

    with_context(AGENT, 0, START);
    let _promise = contract
        .withdraw_credit(U128(PRICE))
        .expect("withdraw credit promise");
    assert_eq!(contract.credit_of(acct(AGENT)).0, 0);
    with_promise_results(CONTRACT, START, vec![PromiseResult::Failed]);
    contract.on_withdraw_credit(acct(AGENT), U128(PRICE));
    assert_eq!(contract.credit_of(acct(AGENT)).0, PRICE);

    with_context(OWNER, 0, START);
    let _promise = contract
        .withdraw_earnings()
        .expect("withdraw earnings promise");
    assert_eq!(contract.earnings_of(acct(OWNER)).0, 0);
    with_promise_results(CONTRACT, START, vec![PromiseResult::Failed]);
    contract.on_withdraw_earnings(acct(OWNER), U128(PRICE));
    assert_eq!(contract.earnings_of(acct(OWNER)).0, PRICE);
}

#[test]
fn withdrawal_success_callbacks_emit_events() {
    let mut contract = new_contract();
    deposit(&mut contract, PRICE);
    with_context(AGENT, 0, START);
    let _promise = contract.withdraw_credit(U128(PRICE)).expect("promise");
    with_promise_results(CONTRACT, START, vec![PromiseResult::Successful(vec![])]);
    contract.on_withdraw_credit(acct(AGENT), U128(PRICE));
    assert_eq!(contract.credit_of(acct(AGENT)).0, 0);
    let logs = get_logs();
    assert!(logs
        .iter()
        .any(|line| line.contains("\"event\":\"credit_withdrawn\"")));
}

#[test]
fn recent_receipts_ring_is_capped_and_newest_first() {
    let mut contract = new_contract();
    register_broker(&mut contract);
    create_grant(&mut contract, 1, 100, START + DAY_NS);
    deposit(&mut contract, 100);
    for _ in 0..51 {
        let req_id = request(&mut contract, "travel");
        serve(&mut contract, req_id);
    }
    let receipts = contract.recent_receipts(acct(OWNER), 0, 50);
    assert_eq!(receipts.len(), 50);
    assert_eq!(receipts[0].req_id, 51);
    assert_eq!(receipts[49].req_id, 2);
    let page = contract.recent_receipts(acct(OWNER), 48, 50);
    assert_eq!(page.len(), 2);
    assert_eq!(page[0].req_id, 3);
}

#[test]
fn grant_upsert_resets_usage_and_unrevokes() {
    let mut contract = new_contract();
    register_broker(&mut contract);
    create_grant(&mut contract, PRICE, 2, START + DAY_NS);
    deposit(&mut contract, PRICE);
    request(&mut contract, "travel");
    with_context(OWNER, 0, START);
    contract.revoke_grant(acct(AGENT)).expect("revoke");
    with_context(OWNER, 0, START);
    contract
        .create_grant(
            acct(AGENT),
            vec!["work".to_string()],
            U128(PRICE),
            7,
            U128((START + DAY_NS).into()),
            64,
        )
        .expect("upsert");
    let grant = contract.get_grant(acct(OWNER), acct(AGENT)).expect("grant");
    assert!(!grant.revoked);
    assert_eq!(grant.used_today, 0);
    assert_eq!(grant.daily_cap, 7);
    assert_eq!(grant.scopes, vec!["work"]);
}
