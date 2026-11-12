mod events;
#[cfg(test)]
mod tests;
mod types;
mod validation;

use crate::events::emit;
use crate::types::*;
use crate::validation::{fail, is_lower_hex_64, is_valid_scope, validate_reason, validate_scopes};
use near_sdk::json_types::U128;
use near_sdk::store::LookupMap;
use near_sdk::{env, near, AccountId, Gas, NearToken, PanicOnDefault, Promise};
use serde_json::json;

#[near(contract_state)]
#[derive(PanicOnDefault)]
pub struct Contract {
    owner: AccountId,
    paused: bool,
    next_request_id: u64,
    brokers: Brokers,
    grants: Grants,
    grants_by_owner: GrantsByOwner,
    credits: Balances,
    earnings: Balances,
    requests: Requests,
    receipts: Receipts,
    recent_served: Vec<u64>,
    pending_by_agent: Pending,
}

#[near]
impl Contract {
    #[init]
    pub fn new(owner: AccountId) -> Self {
        if owner == env::current_account_id() {
            env::panic_str(&fail(
                E_INVALID_OWNER,
                "contract owner must be a separate account",
            ));
        }
        Self {
            owner,
            paused: false,
            next_request_id: 1,
            brokers: LookupMap::new(StorageKey::Brokers),
            grants: LookupMap::new(StorageKey::Grants),
            grants_by_owner: LookupMap::new(StorageKey::GrantsByOwner),
            credits: LookupMap::new(StorageKey::Credits),
            earnings: LookupMap::new(StorageKey::Earnings),
            requests: LookupMap::new(StorageKey::Requests),
            receipts: LookupMap::new(StorageKey::Receipts),
            recent_served: Vec::new(),
            pending_by_agent: LookupMap::new(StorageKey::PendingByAgent),
        }
    }

    // ── Owner configuration ────────────────────────────────────────────────

    #[handle_result]
    pub fn set_broker(
        &mut self,
        broker_account: AccountId,
        broker_pubkey_fingerprint: String,
    ) -> Result<(), String> {
        let owner = env::predecessor_account_id();
        if broker_account == env::current_account_id() {
            return Err(fail(
                E_INVALID_AGENT,
                "the contract account cannot be a broker",
            ));
        }
        if !is_lower_hex_64(&broker_pubkey_fingerprint) {
            return Err(fail(
                E_INVALID_FINGERPRINT,
                "fingerprint must be 64 lowercase hex characters",
            ));
        }
        let now = env::block_timestamp();
        self.brokers.insert(
            owner.clone(),
            BrokerInfo {
                broker_account: broker_account.clone(),
                broker_pubkey_fingerprint: broker_pubkey_fingerprint.clone(),
            },
        );
        emit(
            "broker_set",
            json!({
                "owner": owner,
                "broker_account": broker_account,
                "broker_pubkey_fingerprint": broker_pubkey_fingerprint,
                "set_ns": now.to_string(),
            }),
        );
        Ok(())
    }

    #[handle_result]
    pub fn create_grant(
        &mut self,
        agent: AccountId,
        scopes: Vec<String>,
        price: U128,
        daily_cap: u32,
        expires_ns: U128,
        max_answer_tokens: u32,
    ) -> Result<(), String> {
        if self.paused {
            return Err(fail(E_PAUSED, "contract is paused"));
        }
        let owner = env::predecessor_account_id();
        validate_scopes(&scopes)?;
        let price = price.0;
        if price > MAX_PRICE_YOCTO {
            return Err(fail(E_INVALID_PRICE, "price exceeds the maximum"));
        }
        if daily_cap == 0 || daily_cap > MAX_DAILY_CAP {
            return Err(fail(
                E_INVALID_CAP,
                &format!("daily cap must be 1 to {MAX_DAILY_CAP}"),
            ));
        }
        let now = env::block_timestamp();
        let expires = u64::try_from(expires_ns.0)
            .map_err(|_| fail(E_INVALID_EXPIRY, "expiry is out of range"))?;
        if expires <= now || expires - now > MAX_GRANT_DURATION_NS {
            return Err(fail(
                E_INVALID_EXPIRY,
                "expiry must be in the future and at most 365 days away",
            ));
        }
        if !(MIN_ANSWER_TOKENS..=MAX_ANSWER_TOKENS).contains(&max_answer_tokens) {
            return Err(fail(
                E_INVALID_TOKENS,
                &format!("max answer tokens must be {MIN_ANSWER_TOKENS} to {MAX_ANSWER_TOKENS}"),
            ));
        }

        let key = GrantKey {
            owner: owner.clone(),
            agent: agent.clone(),
        };
        let exists = self.grants.get(&key).is_some();
        let mut agents = self
            .grants_by_owner
            .get(&owner)
            .cloned()
            .unwrap_or_default();
        if !exists {
            if agents.len() >= MAX_GRANTS_PER_OWNER {
                return Err(fail(
                    E_TOO_MANY_GRANTS,
                    &format!("at most {MAX_GRANTS_PER_OWNER} grants per owner"),
                ));
            }
            agents.push(agent.clone());
            self.grants_by_owner.insert(owner.clone(), agents);
        }

        let day_index = now / DAY_NS;
        self.grants.insert(
            key,
            Grant {
                owner: owner.clone(),
                agent: agent.clone(),
                scopes: scopes.clone(),
                price,
                daily_cap,
                expires_ns: expires,
                max_answer_tokens,
                revoked: false,
                used_today: 0,
                day_index,
            },
        );
        emit(
            "grant_created",
            json!({
                "owner": owner,
                "agent": agent,
                "scopes": scopes,
                "price": price.to_string(),
                "daily_cap": daily_cap,
                "expires_ns": expires.to_string(),
                "max_answer_tokens": max_answer_tokens,
                "day_index": day_index,
                "created_ns": now.to_string(),
            }),
        );
        Ok(())
    }

    #[handle_result]
    pub fn revoke_grant(&mut self, agent: AccountId) -> Result<(), String> {
        let owner = env::predecessor_account_id();
        let key = GrantKey {
            owner: owner.clone(),
            agent: agent.clone(),
        };
        let mut grant = self
            .grants
            .get(&key)
            .cloned()
            .ok_or_else(|| fail(E_GRANT_NOT_FOUND, "grant does not exist"))?;
        if grant.revoked {
            return Ok(());
        }
        grant.revoked = true;
        self.grants.insert(key, grant);
        let now = env::block_timestamp();
        emit(
            "grant_revoked",
            json!({
                "owner": owner,
                "agent": agent,
                "revoked_ns": now.to_string(),
            }),
        );
        Ok(())
    }

    // ── Credit and earnings ────────────────────────────────────────────────

    #[payable]
    #[handle_result]
    pub fn deposit_credit(&mut self) -> Result<U128, String> {
        let agent = env::predecessor_account_id();
        let amount = env::attached_deposit().as_yoctonear();
        if amount == 0 {
            return Err(fail(E_INVALID_AMOUNT, "attach a non-zero deposit"));
        }
        let current = self.credits.get(&agent).copied().unwrap_or(0);
        let balance = current
            .checked_add(amount)
            .ok_or_else(|| fail(E_OVERFLOW, "credit balance overflow"))?;
        self.credits.insert(agent.clone(), balance);
        emit(
            "credit_deposited",
            json!({
                "agent": agent,
                "amount": amount.to_string(),
                "balance": balance.to_string(),
            }),
        );
        Ok(U128(balance))
    }

    #[handle_result]
    pub fn withdraw_credit(&mut self, amount: U128) -> Result<Promise, String> {
        let agent = env::predecessor_account_id();
        let amount = amount.0;
        if amount == 0 {
            return Err(fail(E_INVALID_AMOUNT, "amount must be greater than zero"));
        }
        let balance = self.credits.get(&agent).copied().unwrap_or(0);
        let remaining = balance
            .checked_sub(amount)
            .ok_or_else(|| fail(E_INSUFFICIENT_BALANCE, "credit balance is too low"))?;
        self.credits.insert(agent.clone(), remaining);
        let callback_args = json!({
            "agent": agent.clone(),
            "amount": U128(amount),
        })
        .to_string()
        .into_bytes();
        Ok(Promise::new(agent.clone())
            .transfer(NearToken::from_yoctonear(amount))
            .then(Promise::new(env::current_account_id()).function_call(
                "on_withdraw_credit".to_string(),
                callback_args,
                NearToken::from_yoctonear(0),
                Gas::from_tgas(25),
            )))
    }

    #[handle_result]
    pub fn withdraw_earnings(&mut self) -> Result<Promise, String> {
        let owner = env::predecessor_account_id();
        let amount = self.earnings.get(&owner).copied().unwrap_or(0);
        if amount == 0 {
            return Err(fail(
                E_INSUFFICIENT_BALANCE,
                "there are no earnings to withdraw",
            ));
        }
        self.earnings.insert(owner.clone(), 0);
        let callback_args = json!({
            "owner": owner.clone(),
            "amount": U128(amount),
        })
        .to_string()
        .into_bytes();
        Ok(Promise::new(owner.clone())
            .transfer(NearToken::from_yoctonear(amount))
            .then(Promise::new(env::current_account_id()).function_call(
                "on_withdraw_earnings".to_string(),
                callback_args,
                NearToken::from_yoctonear(0),
                Gas::from_tgas(25),
            )))
    }

    #[private]
    pub fn on_withdraw_credit(&mut self, agent: AccountId, amount: U128) {
        if env::promise_results_count() != 1 {
            env::panic_str(&fail(
                E_CALLBACK_ONLY,
                "expected exactly one promise result",
            ));
        }
        let balance = self.credits.get(&agent).copied().unwrap_or(0);
        match env::promise_result_checked(0, 1024) {
            Ok(_) => {
                emit(
                    "credit_withdrawn",
                    json!({
                        "agent": agent,
                        "amount": amount.0.to_string(),
                        "balance": balance.to_string(),
                    }),
                );
            }
            _ => {
                let restored = balance.checked_add(amount.0).unwrap_or_else(|| {
                    env::panic_str(&fail(E_OVERFLOW, "credit balance overflow"))
                });
                self.credits.insert(agent.clone(), restored);
                emit(
                    "credit_withdrawal_failed",
                    json!({
                        "agent": agent,
                        "amount": amount.0.to_string(),
                        "balance": restored.to_string(),
                    }),
                );
            }
        }
    }

    #[private]
    pub fn on_withdraw_earnings(&mut self, owner: AccountId, amount: U128) {
        if env::promise_results_count() != 1 {
            env::panic_str(&fail(
                E_CALLBACK_ONLY,
                "expected exactly one promise result",
            ));
        }
        let balance = self.earnings.get(&owner).copied().unwrap_or(0);
        match env::promise_result_checked(0, 1024) {
            Ok(_) => {
                emit(
                    "earnings_withdrawn",
                    json!({
                        "owner": owner,
                        "amount": amount.0.to_string(),
                        "balance": balance.to_string(),
                    }),
                );
            }
            _ => {
                let restored = balance
                    .checked_add(amount.0)
                    .unwrap_or_else(|| env::panic_str(&fail(E_OVERFLOW, "earnings overflow")));
                self.earnings.insert(owner.clone(), restored);
                emit(
                    "earnings_withdrawal_failed",
                    json!({
                        "owner": owner,
                        "amount": amount.0.to_string(),
                        "balance": restored.to_string(),
                    }),
                );
            }
        }
    }

    // ── Read lifecycle ─────────────────────────────────────────────────────

    #[handle_result]
    pub fn request_read(
        &mut self,
        owner: AccountId,
        scope: String,
        q_hash: String,
    ) -> Result<u64, String> {
        if self.paused {
            return Err(fail(E_PAUSED, "contract is paused"));
        }
        if !is_valid_scope(&scope) {
            return Err(fail(E_INVALID_SCOPE, "scope must match [a-z0-9-]{1,32}"));
        }
        if !is_lower_hex_64(&q_hash) {
            return Err(fail(
                E_INVALID_HASH,
                "q_hash must be 64 lowercase hex characters",
            ));
        }
        let agent = env::predecessor_account_id();
        let key = GrantKey {
            owner: owner.clone(),
            agent: agent.clone(),
        };
        let mut grant = self
            .grants
            .get(&key)
            .cloned()
            .ok_or_else(|| fail(E_GRANT_NOT_FOUND, "no grant for this owner and agent"))?;
        if grant.revoked {
            return Err(fail(E_GRANT_REVOKED, "grant has been revoked"));
        }
        let now = env::block_timestamp();
        if now >= grant.expires_ns {
            return Err(fail(E_GRANT_EXPIRED, "grant has expired"));
        }
        if !grant.scopes.iter().any(|s| s == &scope) {
            return Err(fail(E_SCOPE_DENIED, "scope is not included in the grant"));
        }
        let day_index = now / DAY_NS;
        if grant.day_index != day_index {
            grant.day_index = day_index;
            grant.used_today = 0;
        }
        if grant.used_today >= grant.daily_cap {
            return Err(fail(E_CAP_REACHED, "daily cap has been reached"));
        }
        let credit = self.credits.get(&agent).copied().unwrap_or(0);
        if credit < grant.price {
            return Err(fail(
                E_INSUFFICIENT_CREDIT,
                "deposit credit before requesting a read",
            ));
        }
        let pending = self.pending_by_agent.get(&agent).copied().unwrap_or(0);
        if pending >= MAX_PENDING_PER_AGENT {
            return Err(fail(
                E_TOO_MANY_PENDING,
                &format!("at most {MAX_PENDING_PER_AGENT} pending reads per agent"),
            ));
        }

        self.credits.insert(agent.clone(), credit - grant.price);
        grant.used_today += 1;
        self.grants.insert(key, grant.clone());
        self.pending_by_agent.insert(agent.clone(), pending + 1);

        let req_id = self.next_request_id;
        self.next_request_id = req_id
            .checked_add(1)
            .ok_or_else(|| fail(E_OVERFLOW, "request id overflow"))?;
        self.requests.insert(
            req_id,
            ReadReq {
                id: req_id,
                owner: owner.clone(),
                agent: agent.clone(),
                scope: scope.clone(),
                price: grant.price,
                q_hash: q_hash.clone(),
                status: RequestStatus::Approved,
                created_ns: now,
                receipt_hash: None,
            },
        );
        emit(
            "read_requested",
            json!({
                "req_id": req_id,
                "owner": owner,
                "agent": agent,
                "scope": scope,
                "price": grant.price.to_string(),
                "q_hash": q_hash,
                "created_ns": now.to_string(),
            }),
        );
        Ok(req_id)
    }

    #[handle_result]
    pub fn record_receipt(&mut self, req_id: u64, receipt_hash: String) -> Result<(), String> {
        if !is_lower_hex_64(&receipt_hash) {
            return Err(fail(
                E_INVALID_HASH,
                "receipt_hash must be 64 lowercase hex characters",
            ));
        }
        let broker = env::predecessor_account_id();
        let request = match self.requests.get(&req_id).cloned() {
            Some(request) => request,
            None => {
                if self.recent_served.contains(&req_id) {
                    return Err(fail(
                        E_DUPLICATE_RECEIPT,
                        "a receipt was already recorded for this request",
                    ));
                }
                return Err(fail(E_REQUEST_NOT_FOUND, "request does not exist"));
            }
        };
        if request.status != RequestStatus::Approved {
            return Err(fail(E_REQUEST_NOT_APPROVED, "request is not approved"));
        }
        let broker_info = self
            .brokers
            .get(&request.owner)
            .cloned()
            .ok_or_else(|| fail(E_BROKER_NOT_SET, "owner has not registered a broker"))?;
        if broker != broker_info.broker_account {
            return Err(fail(E_NOT_BROKER, "caller is not the owner's broker"));
        }

        let earnings = self.earnings.get(&request.owner).copied().unwrap_or(0);
        let new_earnings = earnings
            .checked_add(request.price)
            .ok_or_else(|| fail(E_OVERFLOW, "earnings overflow"))?;
        self.earnings.insert(request.owner.clone(), new_earnings);
        self.requests.remove(&req_id);
        self.decrement_pending(&request.agent);
        let now = env::block_timestamp();
        self.push_receipt(
            ReceiptEntry {
                req_id,
                agent: request.agent.clone(),
                scope: request.scope.clone(),
                price: request.price,
                receipt_hash: receipt_hash.clone(),
                served_ns: now,
            },
            &request.owner,
        );
        if self.recent_served.len() >= RECENT_SERVED_CAP {
            self.recent_served.remove(0);
        }
        self.recent_served.push(req_id);
        emit(
            "read_served",
            json!({
                "req_id": req_id,
                "owner": request.owner,
                "agent": request.agent,
                "scope": request.scope,
                "price": request.price.to_string(),
                "receipt_hash": receipt_hash,
                "served_ns": now.to_string(),
            }),
        );
        Ok(())
    }

    #[handle_result]
    pub fn refund(&mut self, req_id: u64, reason: String) -> Result<(), String> {
        validate_reason(&reason)?;
        let broker = env::predecessor_account_id();
        let request = self
            .requests
            .get(&req_id)
            .cloned()
            .ok_or_else(|| fail(E_REQUEST_NOT_FOUND, "request does not exist"))?;
        if request.status != RequestStatus::Approved {
            return Err(fail(E_REQUEST_NOT_APPROVED, "request is not approved"));
        }
        let broker_info = self
            .brokers
            .get(&request.owner)
            .cloned()
            .ok_or_else(|| fail(E_BROKER_NOT_SET, "owner has not registered a broker"))?;
        if broker != broker_info.broker_account {
            return Err(fail(E_NOT_BROKER, "caller is not the owner's broker"));
        }

        let credit = self.credits.get(&request.agent).copied().unwrap_or(0);
        let restored = credit
            .checked_add(request.price)
            .ok_or_else(|| fail(E_OVERFLOW, "credit balance overflow"))?;
        self.credits.insert(request.agent.clone(), restored);
        self.requests.remove(&req_id);
        self.decrement_pending(&request.agent);
        self.release_cap(&request);
        let now = env::block_timestamp();
        emit(
            "read_refunded",
            json!({
                "req_id": req_id,
                "owner": request.owner,
                "agent": request.agent,
                "scope": request.scope,
                "price": request.price.to_string(),
                "reason": reason,
                "refunded_ns": now.to_string(),
            }),
        );
        Ok(())
    }

    #[handle_result]
    pub fn expire_request(&mut self, req_id: u64) -> Result<(), String> {
        let request = self
            .requests
            .get(&req_id)
            .cloned()
            .ok_or_else(|| fail(E_REQUEST_NOT_FOUND, "request does not exist"))?;
        if request.status != RequestStatus::Approved {
            return Err(fail(E_REQUEST_NOT_APPROVED, "request is not approved"));
        }
        let deadline = request
            .created_ns
            .checked_add(REQUEST_TTL_NS)
            .ok_or_else(|| fail(E_OVERFLOW, "request deadline overflow"))?;
        let now = env::block_timestamp();
        if now < deadline {
            return Err(fail(E_REQUEST_NOT_EXPIRED, "request TTL has not elapsed"));
        }

        let credit = self.credits.get(&request.agent).copied().unwrap_or(0);
        let restored = credit
            .checked_add(request.price)
            .ok_or_else(|| fail(E_OVERFLOW, "credit balance overflow"))?;
        self.credits.insert(request.agent.clone(), restored);
        self.requests.remove(&req_id);
        self.decrement_pending(&request.agent);
        self.release_cap(&request);
        emit(
            "request_expired",
            json!({
                "req_id": req_id,
                "owner": request.owner,
                "agent": request.agent,
                "scope": request.scope,
                "price": request.price.to_string(),
                "expired_ns": now.to_string(),
            }),
        );
        Ok(())
    }

    // ── Incident response ──────────────────────────────────────────────────

    #[handle_result]
    pub fn pause(&mut self) -> Result<(), String> {
        let caller = env::predecessor_account_id();
        if caller != self.owner {
            return Err(fail(
                E_NOT_CONTRACT_OWNER,
                "only the contract owner can pause",
            ));
        }
        if self.paused {
            return Ok(());
        }
        self.paused = true;
        emit(
            "paused",
            json!({"by": caller, "at_ns": env::block_timestamp().to_string()}),
        );
        Ok(())
    }

    #[handle_result]
    pub fn unpause(&mut self) -> Result<(), String> {
        let caller = env::predecessor_account_id();
        if caller != self.owner {
            return Err(fail(
                E_NOT_CONTRACT_OWNER,
                "only the contract owner can unpause",
            ));
        }
        if !self.paused {
            return Ok(());
        }
        self.paused = false;
        emit(
            "unpaused",
            json!({"by": caller, "at_ns": env::block_timestamp().to_string()}),
        );
        Ok(())
    }

    // ── Views ──────────────────────────────────────────────────────────────

    pub fn get_grant(&self, owner: AccountId, agent: AccountId) -> Option<GrantView> {
        let key = GrantKey { owner, agent };
        self.grants.get(&key).map(|grant| {
            let now = env::block_timestamp();
            grant_view(grant, now)
        })
    }

    /// Every grant an owner has given, newest first.
    ///
    /// The list is bounded by `MAX_GRANTS_PER_OWNER`, so the view cannot grow
    /// without limit and the owner can see their whole access surface.
    pub fn grants_by_owner(&self, owner: AccountId) -> Vec<GrantView> {
        let now = env::block_timestamp();
        let agents: Vec<AccountId> = match self.grants_by_owner.get(&owner) {
            Some(list) => list.to_vec(),
            None => Vec::new(),
        };
        let mut views: Vec<GrantView> = agents
            .iter()
            .filter_map(|agent| {
                let key = GrantKey {
                    owner: owner.clone(),
                    agent: agent.clone(),
                };
                self.grants.get(&key).map(|grant| grant_view(grant, now))
            })
            .collect();
        views.sort_by_key(|view| std::cmp::Reverse(view.expires_ns));
        views
    }

    pub fn get_request(&self, req_id: u64) -> Option<ReadReqView> {
        self.requests.get(&req_id).map(read_req_view)
    }

    pub fn credit_of(&self, agent: AccountId) -> U128 {
        U128(self.credits.get(&agent).copied().unwrap_or(0))
    }

    pub fn earnings_of(&self, owner: AccountId) -> U128 {
        U128(self.earnings.get(&owner).copied().unwrap_or(0))
    }

    pub fn get_broker(&self, owner: AccountId) -> Option<BrokerInfo> {
        self.brokers.get(&owner).cloned()
    }

    pub fn recent_receipts(&self, owner: AccountId, from: u32, limit: u32) -> Vec<ReceiptView> {
        let entries = self.receipts.get(&owner).cloned().unwrap_or_default();
        let start = (from as usize).min(entries.len());
        let cap = (limit as usize).min(RECEIVE_LIMIT);
        entries
            .iter()
            .rev()
            .skip(start)
            .take(cap)
            .map(|entry| ReceiptView {
                req_id: entry.req_id,
                agent: entry.agent.clone(),
                scope: entry.scope.clone(),
                price: U128(entry.price),
                receipt_hash: entry.receipt_hash.clone(),
                served_ns: U128(entry.served_ns.into()),
            })
            .collect()
    }

    pub fn get_config(&self) -> ConfigView {
        ConfigView {
            owner: self.owner.clone(),
            paused: self.paused,
            next_request_id: self.next_request_id,
            request_ttl_ns: U128(REQUEST_TTL_NS.into()),
            day_ns: U128(DAY_NS.into()),
        }
    }

    // ── Internal helpers ───────────────────────────────────────────────────

    fn decrement_pending(&mut self, agent: &AccountId) {
        let pending = self.pending_by_agent.get(agent).copied().unwrap_or(0);
        if pending <= 1 {
            self.pending_by_agent.remove(agent);
        } else {
            self.pending_by_agent.insert(agent.clone(), pending - 1);
        }
    }

    fn release_cap(&mut self, request: &ReadReq) {
        let key = GrantKey {
            owner: request.owner.clone(),
            agent: request.agent.clone(),
        };
        let Some(mut grant) = self.grants.get(&key).cloned() else {
            return;
        };
        let now = env::block_timestamp();
        let today = now / DAY_NS;
        if grant.day_index == today && grant.used_today > 0 {
            grant.used_today -= 1;
            self.grants.insert(key, grant);
        }
    }

    fn push_receipt(&mut self, entry: ReceiptEntry, owner: &AccountId) {
        let mut entries = self.receipts.get(owner).cloned().unwrap_or_default();
        if entries.len() >= RECENT_RECEIPTS_CAP {
            entries.remove(0);
        }
        entries.push(entry);
        self.receipts.insert(owner.clone(), entries);
    }
}

const RECEIVE_LIMIT: usize = 50;

fn grant_view(grant: &Grant, now: u64) -> GrantView {
    let today = now / DAY_NS;
    let remaining_today = if grant.day_index == today {
        grant.daily_cap.saturating_sub(grant.used_today)
    } else {
        grant.daily_cap
    };
    GrantView {
        owner: grant.owner.clone(),
        agent: grant.agent.clone(),
        scopes: grant.scopes.clone(),
        price: U128(grant.price),
        daily_cap: grant.daily_cap,
        expires_ns: U128(grant.expires_ns.into()),
        max_answer_tokens: grant.max_answer_tokens,
        revoked: grant.revoked,
        used_today: grant.used_today,
        remaining_today,
        day_index: grant.day_index,
    }
}

fn read_req_view(request: &ReadReq) -> ReadReqView {
    ReadReqView {
        id: request.id,
        owner: request.owner.clone(),
        agent: request.agent.clone(),
        scope: request.scope.clone(),
        price: U128(request.price),
        q_hash: request.q_hash.clone(),
        status: request.status.as_str().to_string(),
        created_ns: U128(request.created_ns.into()),
        receipt_hash: request.receipt_hash.clone(),
    }
}
