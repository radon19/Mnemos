use near_workspaces::network::Sandbox;
use near_workspaces::types::NearToken;
use near_workspaces::{Account, Contract, Worker};
use serde_json::{json, Value};

const PRICE: &str = "10000000000000000000000"; // 0.01 NEAR in yocto
const DAY_NS: u64 = 86_400_000_000_000;
const HASH_A: &str = "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa";
const HASH_B: &str = "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb";

struct Env {
    worker: Worker<Sandbox>,
    contract: Contract,
    owner: Account,
    agent: Account,
    broker: Account,
}

async fn setup() -> anyhow::Result<Env> {
    let worker = near_workspaces::sandbox().await?;
    let wasm = near_workspaces::compile_project("./").await?;
    let contract = worker.dev_deploy(&wasm).await?;
    let owner = worker.dev_create_account().await?;
    let agent = worker.dev_create_account().await?;
    let broker = worker.dev_create_account().await?;

    contract
        .call("new")
        .args_json(json!({ "owner": owner.id() }))
        .transact()
        .await?
        .into_result()?;

    owner
        .call(contract.id(), "set_broker")
        .args_json(json!({
            "broker_account": broker.id(),
            "broker_pubkey_fingerprint": HASH_B,
        }))
        .transact()
        .await?
        .into_result()?;

    Ok(Env {
        worker,
        contract,
        owner,
        agent,
        broker,
    })
}

async fn create_grant(
    env: &Env,
    scopes: &[&str],
    price: &str,
    cap: u32,
    expires_in_ns: u64,
    max_tokens: u32,
) -> anyhow::Result<()> {
    let now = env.worker.view_block().await?.timestamp();
    env.owner
        .call(env.contract.id(), "create_grant")
        .args_json(json!({
            "agent": env.agent.id(),
            "scopes": scopes,
            "price": price,
            "daily_cap": cap,
            "expires_ns": (now + expires_in_ns).to_string(),
            "max_answer_tokens": max_tokens,
        }))
        .transact()
        .await?
        .into_result()?;
    Ok(())
}

async fn expect_error(
    env: &Env,
    account: &Account,
    method: &str,
    args: Value,
    code: &str,
) -> anyhow::Result<()> {
    let result = account
        .call(env.contract.id(), method)
        .args_json(args)
        .transact()
        .await?;
    assert!(
        result.is_failure(),
        "{method} unexpectedly succeeded: {result:?}"
    );
    let failure = result.into_result().unwrap_err();
    let text = format!("{failure:?}\n{}", failure.logs().join("\n"));
    assert!(
        text.contains(code),
        "expected {code} from {method}, got: {text}"
    );
    Ok(())
}

async fn request(env: &Env, scope: &str, q_hash: &str) -> anyhow::Result<u64> {
    let result = env
        .agent
        .call(env.contract.id(), "request_read")
        .args_json(json!({
            "owner": env.owner.id(),
            "scope": scope,
            "q_hash": q_hash,
        }))
        .transact()
        .await?
        .into_result()?;
    Ok(result.json()?)
}

#[tokio::test]
async fn full_lifecycle_and_negative_paths() -> anyhow::Result<()> {
    let env = setup().await?;

    // Validation paths.
    expect_error(
        &env,
        &env.owner,
        "create_grant",
        json!({
            "agent": env.agent.id(),
            "scopes": ["Bad Scope"],
            "price": PRICE,
            "daily_cap": 2,
            "expires_ns": (env.worker.view_block().await?.timestamp() + DAY_NS).to_string(),
            "max_answer_tokens": 128,
        }),
        "E_INVALID_SCOPE",
    )
    .await?;
    expect_error(
        &env,
        &env.agent,
        "request_read",
        json!({"owner": env.owner.id(), "scope": "travel", "q_hash": HASH_A}),
        "E_GRANT_NOT_FOUND",
    )
    .await?;

    create_grant(&env, &["travel", "preferences"], PRICE, 5, 3 * DAY_NS, 128).await?;
    let grant: Value = env
        .contract
        .view("get_grant")
        .args_json(json!({"owner": env.owner.id(), "agent": env.agent.id()}))
        .await?
        .json()?;
    assert_eq!(grant["price"], PRICE);
    assert_eq!(grant["daily_cap"], 5);
    assert_eq!(grant["remaining_today"], 5);
    assert_eq!(grant["revoked"], false);

    // Scope isolation: a travel grant must not expose work.
    expect_error(
        &env,
        &env.agent,
        "request_read",
        json!({"owner": env.owner.id(), "scope": "work", "q_hash": HASH_A}),
        "E_SCOPE_DENIED",
    )
    .await?;

    // No credit yet.
    expect_error(
        &env,
        &env.agent,
        "request_read",
        json!({"owner": env.owner.id(), "scope": "travel", "q_hash": HASH_A}),
        "E_INSUFFICIENT_CREDIT",
    )
    .await?;

    env.agent
        .call(env.contract.id(), "deposit_credit")
        .deposit(NearToken::from_near(1))
        .transact()
        .await?
        .into_result()?;
    let credit: String = env
        .contract
        .view("credit_of")
        .args_json(json!({"agent": env.agent.id()}))
        .await?
        .json()?;
    assert_eq!(credit, "1000000000000000000000000");

    let req_id = request(&env, "travel", HASH_A).await?;
    let req: Value = env
        .contract
        .view("get_request")
        .args_json(json!({"req_id": req_id}))
        .await?
        .json()?;
    assert_eq!(req["status"], "Approved");
    assert_eq!(req["owner"], env.owner.id().as_str());
    assert_eq!(req["agent"], env.agent.id().as_str());
    assert_eq!(req["price"], PRICE);

    // A stranger cannot record a receipt.
    expect_error(
        &env,
        &env.agent,
        "record_receipt",
        json!({"req_id": req_id, "receipt_hash": HASH_A}),
        "E_NOT_BROKER",
    )
    .await?;
    expect_error(
        &env,
        &env.agent,
        "refund",
        json!({"req_id": req_id, "reason": "not allowed"}),
        "E_NOT_BROKER",
    )
    .await?;

    env.broker
        .call(env.contract.id(), "record_receipt")
        .args_json(json!({"req_id": req_id, "receipt_hash": HASH_A}))
        .transact()
        .await?
        .into_result()?;

    let earnings: String = env
        .contract
        .view("earnings_of")
        .args_json(json!({"owner": env.owner.id()}))
        .await?
        .json()?;
    assert_eq!(earnings, PRICE);
    let receipts: Value = env
        .contract
        .view("recent_receipts")
        .args_json(json!({"owner": env.owner.id(), "from": 0, "limit": 10}))
        .await?
        .json()?;
    assert_eq!(receipts.as_array().map(Vec::len), Some(1));
    assert_eq!(receipts[0]["receipt_hash"], HASH_A);

    // Double receipt is rejected.
    expect_error(
        &env,
        &env.broker,
        "record_receipt",
        json!({"req_id": req_id, "receipt_hash": HASH_A}),
        "E_DUPLICATE_RECEIPT",
    )
    .await?;

    // Cap: grant allows 5, one served, four more requests fill it.
    for i in 0..4 {
        let id = request(&env, "travel", HASH_A).await?;
        env.broker
            .call(env.contract.id(), "record_receipt")
            .args_json(json!({"req_id": id, "receipt_hash": HASH_B}))
            .transact()
            .await?
            .into_result()?;
        assert!(id > req_id, "request id {i} should increase");
    }
    expect_error(
        &env,
        &env.agent,
        "request_read",
        json!({"owner": env.owner.id(), "scope": "travel", "q_hash": HASH_A}),
        "E_CAP_REACHED",
    )
    .await?;

    // Re-creating the grant resets the daily usage.
    create_grant(&env, &["travel", "preferences"], PRICE, 5, 3 * DAY_NS, 128).await?;
    let grant: Value = env
        .contract
        .view("get_grant")
        .args_json(json!({"owner": env.owner.id(), "agent": env.agent.id()}))
        .await?
        .json()?;
    assert_eq!(grant["used_today"], 0);

    // Refund restores credit and the daily slot.
    let req_id_after_reset = request(&env, "travel", HASH_A).await?;
    let credit_before: String = env
        .contract
        .view("credit_of")
        .args_json(json!({"agent": env.agent.id()}))
        .await?
        .json()?;
    env.broker
        .call(env.contract.id(), "refund")
        .args_json(json!({"req_id": req_id_after_reset, "reason": "model verification failed"}))
        .transact()
        .await?
        .into_result()?;
    let credit_after: String = env
        .contract
        .view("credit_of")
        .args_json(json!({"agent": env.agent.id()}))
        .await?
        .json()?;
    assert_ne!(credit_before, credit_after);
    let grant: Value = env
        .contract
        .view("get_grant")
        .args_json(json!({"owner": env.owner.id(), "agent": env.agent.id()}))
        .await?
        .json()?;
    assert_eq!(grant["used_today"], 0);

    // Request expiry restores credit and is permissionless.
    let expiring = request(&env, "travel", HASH_A).await?;
    expect_error(
        &env,
        &env.owner,
        "expire_request",
        json!({"req_id": expiring}),
        "E_REQUEST_NOT_EXPIRED",
    )
    .await?;
    let ts_before = env.worker.view_block().await?.timestamp();
    env.worker.fast_forward(2_500).await?;
    let ts_after = env.worker.view_block().await?.timestamp();
    eprintln!(
        "fast forward delta ns: {}",
        ts_after.saturating_sub(ts_before)
    );
    env.owner
        .call(env.contract.id(), "expire_request")
        .args_json(json!({"req_id": expiring}))
        .transact()
        .await?
        .into_result()?;
    assert!(env
        .contract
        .view("get_request")
        .args_json(json!({"req_id": expiring}))
        .await?
        .json::<Option<Value>>()?
        .is_none());

    // Revocation takes effect immediately for new requests.
    env.owner
        .call(env.contract.id(), "revoke_grant")
        .args_json(json!({"agent": env.agent.id()}))
        .transact()
        .await?
        .into_result()?;
    expect_error(
        &env,
        &env.agent,
        "request_read",
        json!({"owner": env.owner.id(), "scope": "travel", "q_hash": HASH_A}),
        "E_GRANT_REVOKED",
    )
    .await?;

    // Grant expiry.
    create_grant(&env, &["travel"], PRICE, 5, 2_000_000_000, 128).await?;
    env.worker.fast_forward(10).await?;
    expect_error(
        &env,
        &env.agent,
        "request_read",
        json!({"owner": env.owner.id(), "scope": "travel", "q_hash": HASH_A}),
        "E_GRANT_EXPIRED",
    )
    .await?;

    Ok(())
}

#[tokio::test]
async fn pause_and_withdrawals() -> anyhow::Result<()> {
    let env = setup().await?;
    create_grant(&env, &["travel"], PRICE, 5, DAY_NS, 128).await?;
    env.agent
        .call(env.contract.id(), "deposit_credit")
        .deposit(NearToken::from_near(1))
        .transact()
        .await?
        .into_result()?;
    let req_id = request(&env, "travel", HASH_A).await?;
    env.broker
        .call(env.contract.id(), "record_receipt")
        .args_json(json!({"req_id": req_id, "receipt_hash": HASH_A}))
        .transact()
        .await?
        .into_result()?;

    // Only the contract owner can pause.
    expect_error(&env, &env.agent, "pause", json!({}), "E_NOT_CONTRACT_OWNER").await?;
    env.owner
        .call(env.contract.id(), "pause")
        .args_json(json!({}))
        .transact()
        .await?
        .into_result()?;
    expect_error(
        &env,
        &env.agent,
        "request_read",
        json!({"owner": env.owner.id(), "scope": "travel", "q_hash": HASH_A}),
        "E_PAUSED",
    )
    .await?;
    env.owner
        .call(env.contract.id(), "unpause")
        .args_json(json!({}))
        .transact()
        .await?
        .into_result()?;

    // Earnings withdrawal pays the owner and zeroes the balance.
    let owner_before = env.owner.view_account().await?.balance;
    env.owner
        .call(env.contract.id(), "withdraw_earnings")
        .args_json(json!({}))
        .gas(near_workspaces::types::Gas::from_tgas(100))
        .transact()
        .await?
        .into_result()?;
    let mut owner_after = env.owner.view_account().await?.balance;
    for _ in 0..20 {
        if owner_after > owner_before {
            break;
        }
        tokio::time::sleep(std::time::Duration::from_millis(500)).await;
        owner_after = env.owner.view_account().await?.balance;
    }
    assert!(
        owner_after > owner_before,
        "owner balance should increase: {owner_before:?} -> {owner_after:?}"
    );
    let earnings: String = env
        .contract
        .view("earnings_of")
        .args_json(json!({"owner": env.owner.id()}))
        .await?
        .json()?;
    assert_eq!(earnings, "0");
    expect_error(
        &env,
        &env.owner,
        "withdraw_earnings",
        json!({}),
        "E_INSUFFICIENT_BALANCE",
    )
    .await?;

    // Credit withdrawal returns unused credit.
    let agent_before = env.agent.view_account().await?.balance;
    env.agent
        .call(env.contract.id(), "withdraw_credit")
        .args_json(json!({"amount": "100000000000000000000000"}))
        .gas(near_workspaces::types::Gas::from_tgas(100))
        .transact()
        .await?
        .into_result()?;
    let mut agent_after = env.agent.view_account().await?.balance;
    for _ in 0..20 {
        if agent_after > agent_before {
            break;
        }
        tokio::time::sleep(std::time::Duration::from_millis(500)).await;
        agent_after = env.agent.view_account().await?.balance;
    }
    assert!(
        agent_after > agent_before,
        "agent balance should increase: {agent_before:?} -> {agent_after:?}"
    );
    expect_error(
        &env,
        &env.agent,
        "withdraw_credit",
        json!({"amount": "999999999999999999999999999999"}),
        "E_INSUFFICIENT_BALANCE",
    )
    .await?;

    Ok(())
}
