/**
 * The three MCP tools.
 *
 * `ask_memory` is the whole product in one call: it creates a metered read
 * request on chain, waits for it to be approved, signs it with the agent key
 * and asks the broker for the answer. The agent never holds a key that can
 * read the vault directly, and the broker never serves a read that was not
 * paid for on chain.
 */

import { yoctoToNear } from "near-api-js";

import type { McpConfig } from "./config.js";
import type { AskResponseBody, BrokerClient } from "./broker.js";
import type { ChainClient } from "./chain.js";
import { MnemosToolError, hintFor } from "./errors.js";
import { AgentSigner, buildAskMessage, newNonceHex, questionHash } from "./signer.js";

const ACCOUNT_ID = /^[a-z0-9][a-z0-9._-]{0,62}[a-z0-9]$/u;
const SCOPE = /^[a-z0-9-]{1,32}$/u;
const MAX_QUESTION_CHARS = 2_000;

export interface ToolDeps {
  config: McpConfig;
  chain: ChainClient;
  broker: BrokerClient;
  signer: AgentSigner;
  sleep?: (milliseconds: number) => Promise<void>;
}

export interface AskMemoryInput {
  owner: string;
  scope: string;
  question: string;
}

export interface AskMemoryOutput {
  req_id: number;
  owner: string;
  scope: string;
  status: "served" | "withheld";
  answer: string | null;
  answer_withheld: boolean;
  verified: boolean;
  receipt_hash: string | null;
  tx_hash: string | null;
  refund_tx_hash: string | null;
  latency_ms: number;
  attestation_summary: AskResponseBody["attestation_summary"];
}

export interface GrantOutput {
  owner: string;
  agent: string;
  state: "active" | "revoked" | "expired";
  scopes: string[];
  price_yocto: string;
  price_near: string;
  daily_cap: number;
  used_today: number;
  remaining_today: number;
  expires_ns: string;
  expires_at: string;
  max_answer_tokens: number;
}

export interface CreditOutput {
  agent: string;
  credit_yocto: string;
  credit_near: string;
}

const defaultSleep = async (milliseconds: number): Promise<void> => {
  await new Promise<void>((resolve) => {
    setTimeout(resolve, milliseconds);
  });
};

function validate(input: AskMemoryInput): void {
  if (!ACCOUNT_ID.test(input.owner)) {
    throw new MnemosToolError(
      "E_INVALID_INPUT",
      "owner must be a lowercase NEAR account id",
      hintFor("E_INVALID_INPUT"),
    );
  }
  if (!SCOPE.test(input.scope)) {
    throw new MnemosToolError(
      "E_INVALID_INPUT",
      "scope must match [a-z0-9-]{1,32}",
      hintFor("E_INVALID_INPUT"),
    );
  }
  const question = input.question.trim();
  if (question.length === 0) {
    throw new MnemosToolError(
      "E_INVALID_INPUT",
      "question must not be blank",
      hintFor("E_INVALID_INPUT"),
    );
  }
  if (question.length > MAX_QUESTION_CHARS) {
    throw new MnemosToolError(
      "E_INVALID_INPUT",
      `question must be at most ${MAX_QUESTION_CHARS} characters`,
      hintFor("E_INVALID_INPUT"),
    );
  }
}

async function waitForApproved(
  deps: ToolDeps,
  reqId: number,
): Promise<void> {
  const sleep = deps.sleep ?? defaultSleep;
  const deadline = Date.now() + deps.config.pollTimeoutMs;
  for (;;) {
    const request = await deps.chain.getRequest(reqId);
    if (request === null) {
      throw new MnemosToolError(
        "E_REQUEST_NOT_FOUND",
        `read request ${reqId} does not exist on chain`,
        hintFor("E_REQUEST_NOT_FOUND"),
      );
    }
    if (request.status === "Approved") {
      return;
    }
    if (request.status !== "Pending") {
      throw new MnemosToolError(
        "E_REQUEST_NOT_APPROVED",
        `read request ${reqId} is ${request.status}`,
        hintFor("E_REQUEST_NOT_APPROVED"),
      );
    }
    if (Date.now() >= deadline) {
      throw new MnemosToolError(
        "E_TIMEOUT",
        `read request ${reqId} was not approved within ${deps.config.pollTimeoutMs} ms`,
        hintFor("E_TIMEOUT"),
      );
    }
    await sleep(deps.config.pollIntervalMs);
  }
}

export async function askMemory(
  deps: ToolDeps,
  input: AskMemoryInput,
): Promise<AskMemoryOutput> {
  validate(input);
  const nonce = newNonceHex();
  const qHash = questionHash(input.question, nonce);
  const reqId = await deps.chain.requestRead(input.owner, input.scope, qHash);
  await waitForApproved(deps, reqId);

  const message = buildAskMessage(
    reqId,
    input.question,
    nonce,
    deps.config.brokerRecipient,
  );
  const response = await deps.broker.ask({
    req_id: reqId,
    question: input.question,
    nonce,
    signature_b64: deps.signer.sign(message),
    agent: deps.config.agentAccount,
    public_key: deps.signer.publicKey,
  });

  return {
    req_id: response.req_id,
    owner: input.owner,
    scope: input.scope,
    status: response.status,
    answer: response.answer,
    answer_withheld: response.answer_withheld,
    verified: response.verified,
    receipt_hash: response.receipt_hash,
    tx_hash: response.tx_hash,
    refund_tx_hash: response.refund_tx_hash ?? null,
    latency_ms: response.latency_ms,
    attestation_summary: response.attestation_summary,
  };
}

export async function listGrants(
  deps: ToolDeps,
  owner: string,
): Promise<GrantOutput> {
  if (!ACCOUNT_ID.test(owner)) {
    throw new MnemosToolError(
      "E_INVALID_INPUT",
      "owner must be a lowercase NEAR account id",
      hintFor("E_INVALID_INPUT"),
    );
  }
  const grant = await deps.chain.getGrant(owner, deps.config.agentAccount);
  if (grant === null) {
    throw new MnemosToolError(
      "E_GRANT_NOT_FOUND",
      `${owner} has no grant for ${deps.config.agentAccount}`,
      hintFor("E_GRANT_NOT_FOUND"),
    );
  }
  const expiresNs = BigInt(grant.expires_ns);
  const expired = BigInt(Date.now()) * 1_000_000n >= expiresNs;
  const state: GrantOutput["state"] = grant.revoked
    ? "revoked"
    : expired
      ? "expired"
      : "active";
  return {
    owner: grant.owner,
    agent: grant.agent,
    state,
    scopes: grant.scopes,
    price_yocto: grant.price,
    price_near: yoctoToNear(BigInt(grant.price)),
    daily_cap: grant.daily_cap,
    used_today: grant.used_today,
    remaining_today: grant.remaining_today,
    expires_ns: grant.expires_ns,
    expires_at: new Date(Number(expiresNs / 1_000_000n)).toISOString(),
    max_answer_tokens: grant.max_answer_tokens,
  };
}

export async function checkCredit(deps: ToolDeps): Promise<CreditOutput> {
  const credit = await deps.chain.creditOf(deps.config.agentAccount);
  return {
    agent: deps.config.agentAccount,
    credit_yocto: credit,
    credit_near: yoctoToNear(BigInt(credit)),
  };
}
