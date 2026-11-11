import { describe, expect, it } from "vitest";

import { HttpBrokerClient, type FetchLike } from "../src/broker.js";
import { MnemosToolError } from "../src/errors.js";

function respond(
  status: number,
  body: unknown,
): { ok: boolean; status: number; json: () => Promise<unknown>; text: () => Promise<string> } {
  const text = typeof body === "string" ? body : JSON.stringify(body);
  return {
    ok: status >= 200 && status < 300,
    status,
    json: async () => JSON.parse(text) as unknown,
    text: async () => text,
  };
}

describe("HttpBrokerClient", () => {
  it("posts the signed request to /v1/ask", async () => {
    const calls: { url: string; init: { method?: string; body?: string } | undefined }[] = [];
    const fetchImpl: FetchLike = async (url, init) => {
      calls.push({ url, init });
      return respond(200, {
        req_id: 1,
        status: "served",
        answer: "nine",
        answer_withheld: false,
        verified: true,
        attestation_summary: null,
        receipt_hash: "c".repeat(64),
        tx_hash: "tx-1",
        latency_ms: 10,
      });
    };
    const client = new HttpBrokerClient("http://broker.test", fetchImpl);
    const result = await client.ask({
      req_id: 1,
      question: "q",
      nonce: "00".repeat(32),
      signature_b64: "AA==",
      agent: "agent.testnet",
      public_key: "ed25519:abc",
    });
    expect(calls[0]?.url).toBe("http://broker.test/v1/ask");
    expect(calls[0]?.init?.method).toBe("POST");
    expect(result.answer).toBe("nine");
  });

  it("maps a broker error code to a tool error", async () => {
    const fetchImpl: FetchLike = async () =>
      respond(403, { code: "E_SCOPE_DENIED", message: "scope not allowed" });
    const client = new HttpBrokerClient("http://broker.test", fetchImpl);
    await expect(
      client.ask({
        req_id: 1,
        question: "q",
        nonce: "00".repeat(32),
        signature_b64: "AA==",
        agent: "agent.testnet",
        public_key: "ed25519:abc",
      }),
    ).rejects.toMatchObject({ code: "E_SCOPE_DENIED" });
  });

  it("reports an unreachable broker", async () => {
    const fetchImpl: FetchLike = async () => {
      throw new Error("ECONNREFUSED");
    };
    const client = new HttpBrokerClient("http://broker.test", fetchImpl);
    await expect(
      client.ask({
        req_id: 1,
        question: "q",
        nonce: "00".repeat(32),
        signature_b64: "AA==",
        agent: "agent.testnet",
        public_key: "ed25519:abc",
      }),
    ).rejects.toMatchObject({ code: "E_BROKER_UNREACHABLE" });
  });

  it("rejects a response that is not JSON", async () => {
    const fetchImpl: FetchLike = async () => respond(200, "not json at all");
    const client = new HttpBrokerClient("http://broker.test", fetchImpl);
    await expect(
      client.ask({
        req_id: 1,
        question: "q",
        nonce: "00".repeat(32),
        signature_b64: "AA==",
        agent: "agent.testnet",
        public_key: "ed25519:abc",
      }),
    ).rejects.toBeInstanceOf(MnemosToolError);
  });
});
