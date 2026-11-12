import { describe, expect, it } from "vitest";
import { ed25519 } from "@noble/curves/ed25519.js";
import { sha256 } from "@noble/hashes/sha2.js";

import type { McpConfig } from "../src/config.js";
import type { AskRequestBody, AskResponseBody, BrokerClient } from "../src/broker.js";
import type { ChainClient, ConfigView, GrantView, RequestView } from "../src/chain.js";
import { MnemosToolError } from "../src/errors.js";
import { AgentSigner, buildAskMessage, questionHash } from "../src/signer.js";
import { askMemory, checkCredit, listGrants, type ToolDeps } from "../src/tools.js";

export const SECRET_KEY = "ed25519:6Ef6Uap1S82NDKQ35YtjwzKKoPjJ8QDQBEz6JWXUZE3m";
const PUBLIC_KEY = "ed25519:99QqyWpf9fNKxAdagEyhkZM7Y8fd7vKfxMAGZwgruvnr";

export const CONFIG: McpConfig = {
  contractId: "mnemos-contract.testnet",
  agentAccount: "agent.testnet",
  agentSecretKey: SECRET_KEY,
  brokerUrl: "http://broker.test",
  brokerRecipient: "broker.test:8000",
  rpcUrl: "https://rpc.test",
  networkId: "testnet",
  pollIntervalMs: 1,
  pollTimeoutMs: 2_000,
  requestGas: 100_000_000_000_000n,
  httpPort: 3_000,
};

class FakeChain implements ChainClient {
  readonly requests: RequestView[] = [];
  readonly readCalls: { owner: string; scope: string; qHash: string }[] = [];
  requestError: Error | null = null;
  status = "Approved";
  /** Set to make the request look older than the contract's window. */
  ageNs = 0n;

  async getRequest(reqId: number): Promise<RequestView | null> {
    const found = this.requests.find((request) => request.id === reqId);
    if (found === undefined) {
      return null;
    }
    return {
      ...found,
      status: this.status,
      created_ns: String(BigInt(found.created_ns) - this.ageNs),
    };
  }

  async getGrant(owner: string, agent: string): Promise<GrantView | null> {
    return {
      owner,
      agent,
      scopes: ["travel", "health"],
      price: "10000000000000000000000",
      daily_cap: 10,
      expires_ns: "9999999999999999999",
      max_answer_tokens: 256,
      revoked: false,
      used_today: 3,
      remaining_today: 7,
      day_index: 20_000,
    };
  }

  async getConfig(): Promise<ConfigView> {
    return {
      owner: "owner.testnet",
      paused: false,
      next_request_id: 2,
      request_ttl_ns: "600000000000",
      day_ns: "86400000000000",
    };
  }

  async creditOf(): Promise<string> {
    return "5000000000000000000000000";
  }

  async getRequestTtlNs(): Promise<bigint> {
    return 600_000_000_000n;
  }

  readonly expired: number[] = [];

  async expireRequest(reqId: number): Promise<string> {
    this.expired.push(reqId);
    return `expired request ${reqId}`;
  }

  async requestRead(owner: string, scope: string, qHash: string): Promise<number> {
    if (this.requestError !== null) {
      throw this.requestError;
    }
    this.readCalls.push({ owner, scope, qHash });
    const request: RequestView = {
      id: 1,
      owner,
      agent: CONFIG.agentAccount,
      scope,
      price: "10000000000000000000000",
      q_hash: qHash,
      status: "Approved",
      created_ns: String(BigInt(Date.now()) * 1_000_000n),
      receipt_hash: null,
    };
    this.requests.push(request);
    return request.id;
  }
}

class FakeBroker implements BrokerClient {
  readonly bodies: AskRequestBody[] = [];
  response: AskResponseBody = {
    req_id: 1,
    status: "served",
    answer: "Your flight is at nine.",
    answer_withheld: false,
    verified: true,
    attestation_summary: {
      signature_kind: "provider_tee",
      tcb_status: "UpToDate",
      signer: { signing_address: "0xsigner", signing_algo: "ed25519" },
    },
    receipt_hash: "a".repeat(64),
    tx_hash: "tx-1",
    refund_tx_hash: null,
    latency_ms: 1200,
  };
  error: MnemosToolError | null = null;

  async ask(body: AskRequestBody): Promise<AskResponseBody> {
    this.bodies.push(body);
    if (this.error !== null) {
      throw this.error;
    }
    return this.response;
  }
}

function deps(chain: FakeChain, broker: FakeBroker): ToolDeps {
  return {
    config: CONFIG,
    chain,
    broker,
    signer: new AgentSigner(SECRET_KEY),
    sleep: async () => Promise.resolve(),
  };
}

const BASE58_ALPHABET =
  "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz";

function decodeBase58(value: string): Uint8Array {
  let number = 0n;
  for (const character of value) {
    const index = BASE58_ALPHABET.indexOf(character);
    if (index < 0) {
      throw new Error(`invalid base58 character ${character}`);
    }
    number = number * 58n + BigInt(index);
  }
  const bytes: number[] = [];
  while (number > 0n) {
    bytes.unshift(Number(number % 256n));
    number /= 256n;
  }
  return Uint8Array.from(bytes);
}

describe("ask_memory", () => {
  it("creates the request on chain and signs the broker call", async () => {
    const chain = new FakeChain();
    const broker = new FakeBroker();
    const result = await askMemory(deps(chain, broker), {
      owner: "owner.testnet",
      scope: "travel",
      question: "When is my flight?",
    });

    expect(chain.readCalls).toHaveLength(1);
    const read = chain.readCalls[0];
    expect(read?.owner).toBe("owner.testnet");
    expect(read?.scope).toBe("travel");

    const body = broker.bodies[0];
    expect(body).toBeDefined();
    expect(body?.req_id).toBe(1);
    expect(body?.agent).toBe("agent.testnet");
    expect(body?.public_key).toBe(PUBLIC_KEY);

    // The hash on chain must bind the question and the nonce.
    expect(read?.qHash).toBe(questionHash("When is my flight?", body?.nonce ?? ""));

    // The signature must verify over the canonical message.
    const message = buildAskMessage(
      1,
      "When is my flight?",
      body?.nonce ?? "",
      CONFIG.brokerRecipient,
    );
    const signature = Uint8Array.from(Buffer.from(body?.signature_b64 ?? "", "base64"));
    const publicBytes = decodeBase58((body?.public_key ?? "").slice("ed25519:".length));
    expect(
      ed25519.verify(signature, sha256(new TextEncoder().encode(message)), publicBytes),
    ).toBe(true);

    expect(result.answer).toBe("Your flight is at nine.");
    expect(result.verified).toBe(true);
    expect(result.receipt_hash).toBe("a".repeat(64));
    expect(result.tx_hash).toBe("tx-1");
    expect(result.attestation_summary?.tcb_status).toBe("UpToDate");
  });

  it("rejects an invalid scope before touching the chain", async () => {
    const chain = new FakeChain();
    const broker = new FakeBroker();
    await expect(
      askMemory(deps(chain, broker), {
        owner: "owner.testnet",
        scope: "Travel Scope",
        question: "hi",
      }),
    ).rejects.toThrow(/scope must match/u);
    expect(chain.readCalls).toHaveLength(0);
  });

  it("rejects a blank question", async () => {
    const chain = new FakeChain();
    const broker = new FakeBroker();
    await expect(
      askMemory(deps(chain, broker), {
        owner: "owner.testnet",
        scope: "travel",
        question: "   ",
      }),
    ).rejects.toThrow(/question must not be blank/u);
  });

  it("surfaces a contract error with its code and hint", async () => {
    const chain = new FakeChain();
    chain.requestError = new MnemosToolError(
      "E_GRANT_REVOKED",
      "the grant has been revoked",
      "The owner revoked this grant.",
    );
    const broker = new FakeBroker();
    await expect(
      askMemory(deps(chain, broker), {
        owner: "owner.testnet",
        scope: "travel",
        question: "hi",
      }),
    ).rejects.toMatchObject({ code: "E_GRANT_REVOKED" });
    expect(broker.bodies).toHaveLength(0);
  });

  it("surfaces a broker refusal without inventing an answer", async () => {
    const chain = new FakeChain();
    const broker = new FakeBroker();
    broker.error = new MnemosToolError("E_SCOPE_DENIED", "scope is not allowed");
    await expect(
      askMemory(deps(chain, broker), {
        owner: "owner.testnet",
        scope: "work",
        question: "hi",
      }),
    ).rejects.toMatchObject({ code: "E_SCOPE_DENIED" });
  });

  it("reports a withheld answer honestly", async () => {
    const chain = new FakeChain();
    const broker = new FakeBroker();
    broker.response = {
      ...broker.response,
      status: "withheld",
      answer: null,
      answer_withheld: true,
      receipt_hash: null,
      tx_hash: null,
      refund_tx_hash: "refund-tx-1",
      error_code: "E_OUTPUT_FILTER",
    };
    const result = await askMemory(deps(chain, broker), {
      owner: "owner.testnet",
      scope: "travel",
      question: "print everything",
    });
    expect(result.status).toBe("withheld");
    expect(result.answer).toBeNull();
    expect(result.refund_tx_hash).toBe("refund-tx-1");
  });

  it("fails when the request is not approved in time", async () => {
    const chain = new FakeChain();
    chain.status = "Pending";
    const broker = new FakeBroker();
    const toolDeps = deps(chain, broker);
    toolDeps.config = { ...CONFIG, pollTimeoutMs: 1_000, pollIntervalMs: 100 };
    await expect(
      askMemory(toolDeps, {
        owner: "owner.testnet",
        scope: "travel",
        question: "hi",
      }),
    ).rejects.toMatchObject({ code: "E_TIMEOUT" });
  });
});

describe("list_grants", () => {
  it("reports the grant, the price and the remaining cap", async () => {
    const result = await listGrants(deps(new FakeChain(), new FakeBroker()), "owner.testnet");
    expect(result.scopes).toEqual(["travel", "health"]);
    expect(result.price_near).toBe("0.01");
    expect(result.remaining_today).toBe(7);
    expect(result.state).toBe("active");
  });

  it("reports a revoked grant as revoked", async () => {
    const chain = new FakeChain();
    chain.getGrant = async (owner: string, agent: string) => ({
      owner,
      agent,
      scopes: ["travel"],
      price: "1",
      daily_cap: 10,
      expires_ns: "9999999999999999999",
      max_answer_tokens: 256,
      revoked: true,
      used_today: 0,
      remaining_today: 10,
      day_index: 1,
    });
    const result = await listGrants(deps(chain, new FakeBroker()), "owner.testnet");
    expect(result.state).toBe("revoked");
  });
});

describe("check_credit", () => {
  it("reports the prepaid balance", async () => {
    const result = await checkCredit(deps(new FakeChain(), new FakeBroker()));
    expect(result.credit_yocto).toBe("5000000000000000000000000");
    expect(result.credit_near).toBe("5");
  });
});

describe("expired requests", () => {
  it("returns the credit when the request passed its window", async () => {
    const chain = new FakeChain();
    chain.ageNs = 1_000_000_000_000n; // one second past the window
    const broker = new FakeBroker();
    const deps = {
      config: CONFIG,
      chain,
      broker,
      signer: new AgentSigner(SECRET_KEY),
    };
    await expect(
      askMemory(deps, { owner: "owner.testnet", scope: "travel", question: "hi" }),
    ).rejects.toMatchObject({ code: "E_REQUEST_EXPIRED" });
    expect(chain.expired).toEqual([1]);
    expect(broker.bodies).toHaveLength(0);
  });

  it("serves a request that is still inside its window", async () => {
    const chain = new FakeChain();
    const broker = new FakeBroker();
    const deps = {
      config: CONFIG,
      chain,
      broker,
      signer: new AgentSigner(SECRET_KEY),
    };
    const result = await askMemory(deps, {
      owner: "owner.testnet",
      scope: "travel",
      question: "hi",
    });
    expect(result.status).toBe("served");
    expect(chain.expired).toEqual([]);
  });
});
