import { describe, expect, it } from "vitest";
import { Client } from "@modelcontextprotocol/sdk/client/index.js";
import { InMemoryTransport } from "@modelcontextprotocol/sdk/inMemory.js";

import { createMcpServer } from "../src/server.js";
import { AgentSigner } from "../src/signer.js";
import type { AskRequestBody, AskResponseBody, BrokerClient } from "../src/broker.js";
import type { ChainClient, ConfigView, GrantView, RequestView } from "../src/chain.js";
import { MnemosToolError } from "../src/errors.js";
import type { ToolDeps } from "../src/tools.js";

const CONFIG = {
  contractId: "mnemos-contract.testnet",
  agentAccount: "agent.testnet",
  agentSecretKey: "ed25519:6Ef6Uap1S82NDKQ35YtjwzKKoPjJ8QDQBEz6JWXUZE3m",
  brokerUrl: "http://broker.test",
  brokerRecipient: "broker.test:8000",
  rpcUrl: "https://rpc.test",
  networkId: "testnet",
  pollIntervalMs: 1,
  pollTimeoutMs: 2_000,
  requestGas: 100_000_000_000_000n,
  httpPort: 3_000,
};

class StubChain implements ChainClient {
  async getRequest(reqId: number): Promise<RequestView | null> {
    return {
      id: reqId,
      owner: "owner.testnet",
      agent: "agent.testnet",
      scope: "travel",
      price: "1",
      q_hash: "a".repeat(64),
      status: "Approved",
      created_ns: "1",
      receipt_hash: null,
    };
  }

  async getGrant(owner: string, agent: string): Promise<GrantView | null> {
    return {
      owner,
      agent,
      scopes: ["travel"],
      price: "10000000000000000000000",
      daily_cap: 5,
      expires_ns: "9999999999999999999",
      max_answer_tokens: 256,
      revoked: false,
      used_today: 1,
      remaining_today: 4,
      day_index: 1,
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
    return "1000000000000000000000000";
  }

  async requestRead(): Promise<number> {
    return 1;
  }
}

class StubBroker implements BrokerClient {
  error: MnemosToolError | null = null;
  body: AskRequestBody | null = null;

  async ask(body: AskRequestBody): Promise<AskResponseBody> {
    this.body = body;
    if (this.error !== null) {
      throw this.error;
    }
    return {
      req_id: 1,
      status: "served",
      answer: "Your flight is at nine.",
      answer_withheld: false,
      verified: true,
      attestation_summary: { signature_kind: "provider_tee" },
      receipt_hash: "b".repeat(64),
      tx_hash: "tx-1",
      latency_ms: 900,
    };
  }
}

function buildDeps(broker: StubBroker): ToolDeps {
  return {
    config: CONFIG,
    chain: new StubChain(),
    broker,
    signer: new AgentSigner(CONFIG.agentSecretKey),
    sleep: async () => Promise.resolve(),
  };
}

async function connect(broker: StubBroker): Promise<Client> {
  const server = createMcpServer(buildDeps(broker));
  const client = new Client({ name: "test-client", version: "1.0.0" });
  const [clientTransport, serverTransport] = InMemoryTransport.createLinkedPair();
  await Promise.all([server.connect(serverTransport), client.connect(clientTransport)]);
  return client;
}

describe("MCP server", () => {
  it("exposes exactly the three documented tools", async () => {
    const client = await connect(new StubBroker());
    const tools = await client.listTools();
    expect(tools.tools.map((tool) => tool.name).sort()).toEqual([
      "ask_memory",
      "check_credit",
      "list_grants",
    ]);
    await client.close();
  });

  it("answers ask_memory with the answer and the receipt", async () => {
    const broker = new StubBroker();
    const client = await connect(broker);
    const result = await client.callTool({
      name: "ask_memory",
      arguments: { owner: "owner.testnet", scope: "travel", question: "When is my flight?" },
    });
    expect(result.isError).toBeFalsy();
    const text = (result.content as { type: string; text: string }[])[0]?.text ?? "";
    const payload = JSON.parse(text) as { answer: string; receipt_hash: string };
    expect(payload.answer).toBe("Your flight is at nine.");
    expect(payload.receipt_hash).toBe("b".repeat(64));
    expect(broker.body?.req_id).toBe(1);
    await client.close();
  });

  it("reports a contract error as a readable tool error", async () => {
    const broker = new StubBroker();
    broker.error = new MnemosToolError(
      "E_CAP_REACHED",
      "the daily cap has been reached",
      "The daily read cap for this grant is used up.",
    );
    const client = await connect(broker);
    const result = await client.callTool({
      name: "ask_memory",
      arguments: { owner: "owner.testnet", scope: "travel", question: "hi" },
    });
    expect(result.isError).toBe(true);
    const text = (result.content as { type: string; text: string }[])[0]?.text ?? "";
    expect(text).toContain("E_CAP_REACHED");
    expect(text).toContain("daily read cap");
    await client.close();
  });

  it("rejects invalid arguments before calling anything", async () => {
    const broker = new StubBroker();
    const client = await connect(broker);
    const result = await client.callTool({
      name: "ask_memory",
      arguments: { owner: "owner.testnet", scope: "travel" },
    });
    expect(result.isError).toBe(true);
    expect(broker.body).toBeNull();
    await client.close();
  });

  it("lists the grant and the credit", async () => {
    const client = await connect(new StubBroker());
    const grants = await client.callTool({
      name: "list_grants",
      arguments: { owner: "owner.testnet" },
    });
    const grantsText = (grants.content as { type: string; text: string }[])[0]?.text ?? "";
    const grantPayload = JSON.parse(grantsText) as { remaining_today: number };
    expect(grantPayload.remaining_today).toBe(4);

    const credit = await client.callTool({ name: "check_credit", arguments: {} });
    const creditText = (credit.content as { type: string; text: string }[])[0]?.text ?? "";
    const creditPayload = JSON.parse(creditText) as { credit_near: string };
    expect(creditPayload.credit_near).toBe("1");
    await client.close();
  });
});
