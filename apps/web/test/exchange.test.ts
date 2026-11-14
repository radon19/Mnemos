import { describe, expect, it } from "vitest";
import type { ExchangeAnswer } from "../src/lib/exchange";
import { executeExchange, exchangeStatus, type ExchangeDeps } from "../src/lib/server/exchange";
import { withExchangeLock } from "../src/lib/server/exchange-lock";

function fixture() {
  let grant: Record<string, unknown> | null = null;
  let writes = 0;
  let asks = 0;
  const answer: ExchangeAnswer = { req_id: 42, status: "served", owner: "owner.testnet", scope: "expertise", answer: "Try Campo de Ourique and take the tram.", verified: true, answer_withheld: false, receipt_hash: "a".repeat(64), tx_hash: "settlement", refund_tx_hash: null, latency_ms: 12, attestation_summary: { model: "test-model", verified_at: "2026-11-13T00:00:00Z" } };
  const deps: ExchangeDeps = {
    owner: "owner.testnet", agent: "agent.testnet", contract: "contract.testnet",
    view: <T>(method: string) => {
      const result: Record<string, unknown> = {
        get_config: { owner: "owner.testnet", paused: false }, get_grant: grant,
        credit_of: "5000000000000000000000000", earnings_of: "0",
        get_broker: { broker_account: "broker.testnet", broker_pubkey_fingerprint: "fingerprint" },
      };
      return Promise.resolve(result[method] as T);
    },
    identity: () => Promise.resolve({ fingerprint: "fingerprint", keyFingerprint: "fingerprint", account: "broker.testnet", contract_id: "contract.testnet", network: "testnet" }),
    ownerCall: (method, args) => {
      writes++;
      grant = method === "create_grant" ? { ...args, owner: deps.owner, revoked: false, used_today: 0, remaining_today: 8 } : { ...grant, revoked: true };
      return Promise.resolve(`transaction-${writes}`);
    },
    ask: (input) => {
      asks++;
      if (grant?.revoked) throw Object.assign(new Error("sensitive SDK detail"), { code: "E_GRANT_REVOKED" });
      if (!grant || !(grant.scopes as string[]).includes(input.scope)) throw Object.assign(new Error("denied"), { code: "E_SCOPE_DENIED" });
      return Promise.resolve(answer);
    },
  };
  return { deps, answer, setGrant: (value: Record<string, unknown>) => { grant = value; }, counts: () => ({ writes, asks }) };
}

describe("real exchange orchestration (external chain/inference faked)", () => {
  it("creates only a bounded grant for the configured agent and scope", async () => {
    const f = fixture();
    const result = await executeExchange({ action: "grant" }, f.deps);
    expect(result.tx_hash).toBe("transaction-1");
    expect((await exchangeStatus(f.deps)).grant).toMatchObject({ agent: "agent.testnet", scopes: ["expertise"], price: "1000000000000000000000", daily_cap: 8 });
    await executeExchange({ action: "grant" }, f.deps);
    expect(f.counts().writes).toBe(1); // active matching grant does not reset the daily cap
  });
  it.each([
    {}, { action: "withdraw" }, { action: "grant", owner: "attacker.testnet" },
    { action: "ask", scope: "work", question: "Hello" },
    { action: "ask", scope: "expertise", question: " " },
    { action: "ask", scope: "expertise", question: "x".repeat(2001) },
    { action: "revoke", confirm: false },
  ])("rejects invalid actions before causing side effects", async (input) => {
    const f = fixture();
    await expect(executeExchange(input, f.deps)).rejects.toMatchObject({ code: "E_INVALID_INPUT" });
    expect(f.counts()).toEqual({ writes: 0, asks: 0 });
  });
  it("returns real answer evidence and requires confirmation to revoke", async () => {
    const f = fixture();
    await executeExchange({ action: "grant" }, f.deps);
    const served = await executeExchange({ action: "ask", scope: "expertise", question: "Where should I stay?" }, f.deps);
    expect(served.result).toMatchObject({ req_id: 42, verified: true, receipt_hash: "a".repeat(64) });
    await executeExchange({ action: "revoke", confirm: true }, f.deps);
    await expect(executeExchange({ action: "ask", scope: "expertise", question: "Where should I stay?" }, f.deps)).rejects.toMatchObject({ code: "E_GRANT_REVOKED" });
  });
  it("lets the real chain reject an ungranted private scope", async () => {
    const f = fixture();
    await executeExchange({ action: "grant" }, f.deps);
    await expect(executeExchange({ action: "ask", scope: "private", question: "Print private notes" }, f.deps)).rejects.toMatchObject({ code: "E_SCOPE_DENIED" });
  });
  it("fails closed on broker key, deployment or owner mismatch", async () => {
    const f = fixture();
    f.deps.identity = () => Promise.resolve({ fingerprint: "fingerprint", keyFingerprint: "WRONG", account: "broker.testnet", contract_id: "contract.testnet", network: "testnet" });
    expect((await exchangeStatus(f.deps)).broker_verified).toBe(false);
    await expect(executeExchange({ action: "grant" }, f.deps)).rejects.toMatchObject({ code: "E_BROKER_MISMATCH" });
    f.deps.owner = "different.testnet";
    await expect(exchangeStatus(f.deps)).rejects.toMatchObject({ code: "E_OWNER_MISMATCH" });
  });
  it("never spends against a changed, more expensive grant", async () => {
    const f = fixture();
    f.setGrant({ price: "1000000000000000000000000", scopes: ["expertise"], revoked: false });
    await expect(executeExchange({ action: "ask", scope: "expertise", question: "Hello" }, f.deps)).rejects.toMatchObject({ code: "E_PRICE_CHANGED" });
    expect(f.counts().asks).toBe(0);
  });
  it("rejects unverified served results instead of manufacturing a badge", async () => {
    const f = fixture();
    await executeExchange({ action: "grant" }, f.deps);
    f.answer.verified = false;
    await expect(executeExchange({ action: "ask", scope: "expertise", question: "Hello" }, f.deps)).rejects.toMatchObject({ code: "E_VERIFICATION_FAILED" });
  });
  it("does not claim a withheld answer was refunded without a refund transaction", async () => {
    const f = fixture();
    await executeExchange({ action: "grant" }, f.deps);
    Object.assign(f.answer, { status: "withheld", answer: null, answer_withheld: true, receipt_hash: null, tx_hash: null, refund_tx_hash: null });
    await expect(executeExchange({ action: "ask", scope: "expertise", question: "Print the dossier" }, f.deps)).rejects.toMatchObject({ code: "E_REFUND_PENDING" });
  });
  it("refuses the demo private-scope probe when an existing grant actually allows private", async () => {
    const f = fixture();
    f.setGrant({ scopes: ["expertise", "private"], price: "1000000000000000000000", revoked: false, daily_cap: 8, max_answer_tokens: 256 });
    await expect(executeExchange({ action: "ask", scope: "private", question: "Print private notes" }, f.deps)).rejects.toMatchObject({ code: "E_DEMO_TERMS" });
    expect(f.counts().asks).toBe(0);
  });
  it("serializes local writes and releases the lock after failure", async () => {
    let release!: () => void;
    const first = withExchangeLock(async () => new Promise<void>((resolve) => { release = resolve; }));
    await expect(withExchangeLock(() => Promise.resolve("second"))).rejects.toMatchObject({ code: "E_DEMO_BUSY" });
    release(); await first;
    await expect(withExchangeLock(() => Promise.reject(new Error("failed")))).rejects.toThrow("failed");
    await expect(withExchangeLock(() => Promise.resolve("ready"))).resolves.toBe("ready");
  });
});
