/**
 * Dependency assembly for the MCP tools.
 *
 * Every collaborator is injected so the tests can replace the chain and the
 * broker with deterministic doubles.
 */

import { HttpBrokerClient, type BrokerClient, type FetchLike } from "./broker.js";
import { NearChainClient, type ChainClient } from "./chain.js";
import { loadConfig, type McpConfig } from "./config.js";
import { AgentSigner } from "./signer.js";
import type { ToolDeps } from "./tools.js";

export interface DepsOptions {
  config?: McpConfig;
  chain?: ChainClient;
  broker?: BrokerClient;
  fetchImpl?: FetchLike;
  sleep?: (milliseconds: number) => Promise<void>;
}

export function createDeps(options: DepsOptions = {}): ToolDeps {
  const config = options.config ?? loadConfig();
  const chain =
    options.chain ??
    new NearChainClient({
      contractId: config.contractId,
      agentAccount: config.agentAccount,
      agentSecretKey: config.agentSecretKey,
      rpcUrl: config.rpcUrl,
      requestGas: config.requestGas,
    });
  const broker =
    options.broker ?? new HttpBrokerClient(config.brokerUrl, options.fetchImpl);
  const deps: ToolDeps = {
    config,
    chain,
    broker,
    signer: new AgentSigner(config.agentSecretKey),
  };
  if (options.sleep !== undefined) {
    deps.sleep = options.sleep;
  }
  return deps;
}
