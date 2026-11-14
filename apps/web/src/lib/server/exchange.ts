import { EXCHANGE_TERMS, type ExchangeActionResult, type ExchangeAnswer, type ExchangeStatus } from "../exchange";
import type { GrantView } from "../near";
import { DemoError } from "./demo-guard";

export interface ExchangeDeps {
  owner: string;
  agent: string;
  contract: string;
  view: <T>(method: string, args: Record<string, unknown>) => Promise<T>;
  identity: () => Promise<{ fingerprint: string; keyFingerprint: string; account: string; contract_id: string; network: string }>;
  ownerCall: (method: "create_grant" | "revoke_grant", args: Record<string, unknown>) => Promise<string>;
  ask: (input: { owner: string; scope: string; question: string }) => Promise<ExchangeAnswer>;
}

export async function exchangeStatus(deps: ExchangeDeps): Promise<ExchangeStatus> {
  const config = await deps.view<{ owner: string; paused: boolean }>("get_config", {});
  if (config.owner !== deps.owner) throw new DemoError(403, "E_OWNER_MISMATCH", "The contract owner differs from the configured demo owner. Check make doctor.");
  const [grant, credit, earnings, broker, identity] = await Promise.all([
    deps.view<GrantView | null>("get_grant", { owner: deps.owner, agent: deps.agent }),
    deps.view<string>("credit_of", { agent: deps.agent }),
    deps.view<string>("earnings_of", { owner: deps.owner }),
    deps.view<{ broker_account: string; broker_pubkey_fingerprint: string } | null>("get_broker", { owner: deps.owner }),
    deps.identity(),
  ]);
  return {
    owner: deps.owner, agent: deps.agent, contract: deps.contract, network: "testnet",
    grant, credit, earnings, paused: config.paused,
    broker_verified: broker !== null && broker.broker_pubkey_fingerprint === identity.fingerprint &&
      identity.fingerprint === identity.keyFingerprint && broker.broker_account === identity.account &&
      identity.contract_id === deps.contract && identity.network === "testnet",
  };
}

type Action = { action: "grant" } | { action: "revoke"; confirm: true } | { action: "ask"; scope: "expertise" | "private"; question: string };

function parseAction(input: unknown): Action {
  const fail = (): never => { throw new DemoError(400, "E_INVALID_INPUT", "Choose grant, ask or revoke using the demo controls. Questions must contain 1–2000 characters."); };
  if (input === null || typeof input !== "object" || Array.isArray(input)) return fail();
  const body = input as Record<string, unknown>;
  if (body.action === "grant" && Object.keys(body).length === 1) return { action: "grant" };
  if (body.action === "revoke" && body.confirm === true && Object.keys(body).length === 2) return { action: "revoke", confirm: true };
  if (body.action === "ask" && Object.keys(body).length === 3 &&
      (body.scope === "expertise" || body.scope === "private") &&
      typeof body.question === "string" && body.question.trim().length > 0 && body.question.length <= 2000) {
    return { action: "ask", scope: body.scope, question: body.question.trim() };
  }
  return fail();
}

export async function executeExchange(input: unknown, deps: ExchangeDeps): Promise<ExchangeActionResult> {
  const body = parseAction(input);
  const status = await exchangeStatus(deps);
  if (!status.broker_verified) throw new DemoError(409, "E_BROKER_MISMATCH", "The broker identity does not match its on-chain registration. Nothing was signed.");
  if (body.action === "grant") {
    if (status.paused) throw new DemoError(403, "E_PAUSED", "The contract is paused. Unpause it from Setup before granting access.");
    const current = status.grant;
    if (current && !current.revoked && BigInt(current.expires_ns) > BigInt(Date.now()) * 1_000_000n &&
        current.price === EXCHANGE_TERMS.price && current.daily_cap === EXCHANGE_TERMS.dailyCap &&
        current.max_answer_tokens === EXCHANGE_TERMS.answerTokens && current.scopes.length === 1 && current.scopes[0] === "expertise") {
      return { action: "grant", tx_hash: null, already_active: true };
    }
    const tx = await deps.ownerCall("create_grant", {
      agent: deps.agent, scopes: [EXCHANGE_TERMS.scope], price: EXCHANGE_TERMS.price,
      daily_cap: EXCHANGE_TERMS.dailyCap, max_answer_tokens: EXCHANGE_TERMS.answerTokens,
      expires_ns: (BigInt(Date.now()) * 1_000_000n + 86_400_000_000_000n).toString(),
    });
    return { action: "grant", tx_hash: tx };
  }
  if (body.action === "revoke") {
    return { action: "revoke", tx_hash: await deps.ownerCall("revoke_grant", { agent: deps.agent }) };
  }
  if (status.grant && BigInt(status.grant.price) > BigInt(EXCHANGE_TERMS.price)) {
    throw new DemoError(409, "E_PRICE_CHANGED", "The grant price exceeds the demo's 0.001 NEAR limit. Review and renew the demo grant first.");
  }
  if (status.grant && (status.grant.scopes.length !== 1 || status.grant.scopes[0] !== EXCHANGE_TERMS.scope ||
      status.grant.price !== EXCHANGE_TERMS.price || status.grant.daily_cap !== EXCHANGE_TERMS.dailyCap ||
      status.grant.max_answer_tokens !== EXCHANGE_TERMS.answerTokens)) {
    throw new DemoError(409, "E_DEMO_TERMS", "This agent's existing grant differs from the displayed demo terms. Grant expertise access first; no read was purchased.");
  }
  // Do not pre-empt scope/revocation errors: the deployed contract must prove
  // those boundaries. The existing MCP implementation performs request_read.
  const result = await deps.ask({ owner: deps.owner, scope: body.scope, question: body.question });
  if (!result.verified || !result.attestation_summary || (result.status === "served" && (!result.receipt_hash || !result.tx_hash || !result.answer))) {
    throw new DemoError(502, "E_VERIFICATION_FAILED", "The response lacks verified answer evidence. Check Activity before repeating the read.");
  }
  if (result.status === "withheld" && !result.refund_tx_hash) {
    throw new DemoError(502, "E_REFUND_PENDING", `Answer #${result.req_id} was withheld, but its refund is not confirmed. Check Activity and credit; the expiry sweeper retries recovery after the 10-minute request window.`);
  }
  return { action: "ask", result };
}
