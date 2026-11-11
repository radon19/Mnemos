import { describe, expect, it } from "vitest";

import { ConfigError, loadConfig } from "../src/config.js";

const VALID: NodeJS.ProcessEnv = {
  MNEMOS_CONTRACT_ID: "mnemos-contract.testnet",
  MNEMOS_AGENT_ACCOUNT: "mnemos-agent.testnet",
  MNEMOS_AGENT_KEY: "ed25519:6Ef6Uap1S82NDKQ35YtjwzKKoPjJ8QDQBEz6JWXUZE3m",
  MNEMOS_BROKER_URL: "http://localhost:8000",
};

function env(overrides: NodeJS.ProcessEnv = {}): NodeJS.ProcessEnv {
  return { ...VALID, ...overrides };
}

describe("loadConfig", () => {
  it("reads the documented environment variables", () => {
    const config = loadConfig(env());
    expect(config.contractId).toBe("mnemos-contract.testnet");
    expect(config.agentAccount).toBe("mnemos-agent.testnet");
    expect(config.rpcUrl).toBe("https://test.rpc.fastnear.com");
    expect(config.networkId).toBe("testnet");
  });

  it("derives the broker recipient from the broker url", () => {
    const config = loadConfig(env());
    expect(config.brokerRecipient).toBe("localhost:8000");
  });

  it("prefers an explicit recipient", () => {
    const config = loadConfig(
      env({ MNEMOS_BROKER_RECIPIENT: "broker.internal:9000" }),
    );
    expect(config.brokerRecipient).toBe("broker.internal:9000");
  });

  it("strips a trailing slash from the broker url", () => {
    const config = loadConfig(env({ MNEMOS_BROKER_URL: "http://localhost:8000/" }));
    expect(config.brokerUrl).toBe("http://localhost:8000");
  });

  it("refuses a configuration without a contract", () => {
    const incomplete = env();
    delete incomplete.MNEMOS_CONTRACT_ID;
    expect(() => loadConfig(incomplete)).toThrow(ConfigError);
  });

  it("refuses a key that is not an ed25519 secret key", () => {
    expect(() => loadConfig(env({ MNEMOS_AGENT_KEY: "secp256k1:abc" }))).toThrow(
      /ed25519/u,
    );
  });

  it("refuses an account id that is not lowercase", () => {
    expect(() => loadConfig(env({ MNEMOS_AGENT_ACCOUNT: "Agent.Testnet" }))).toThrow(
      /NEAR account id/u,
    );
  });
});
