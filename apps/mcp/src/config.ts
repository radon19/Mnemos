/**
 * Environment configuration for the Mnemos MCP server.
 *
 * Every value comes from the environment. Nothing is hard coded and nothing is
 * read from a file, so a caller can never smuggle a key past the process
 * boundary.
 */

import { z } from "zod";

const ACCOUNT_ID = /^[a-z0-9][a-z0-9._-]{0,62}[a-z0-9]$/u;

const envSchema = z.object({
  MNEMOS_CONTRACT_ID: z.string().regex(ACCOUNT_ID, "must be a NEAR account id"),
  MNEMOS_AGENT_ACCOUNT: z.string().regex(ACCOUNT_ID, "must be a NEAR account id"),
  MNEMOS_AGENT_KEY: z
    .string()
    .min(16, "must be an ed25519 secret key")
    .refine((value) => value.startsWith("ed25519:"), "must start with 'ed25519:'"),
  MNEMOS_BROKER_URL: z.url(),
  NEAR_RPC_URL: z.url().default("https://test.rpc.fastnear.com"),
  MNEMOS_NETWORK_ID: z.string().default("testnet"),
  MNEMOS_BROKER_RECIPIENT: z.string().min(3).optional(),
  MNEMOS_POLL_INTERVAL_MS: z.coerce.number().int().min(100).max(10_000).default(500),
  MNEMOS_POLL_TIMEOUT_MS: z.coerce.number().int().min(1_000).max(120_000).default(30_000),
  // These pure-state calls fit within 30 Tgas. A 100 Tgas reservation exceeds
  // the restricted runtime key's 0.05 NEAR allowance at the purchase-price floor.
  MNEMOS_REQUEST_GAS: z.coerce.bigint().min(30_000_000_000_000n).default(30_000_000_000_000n),
  MNEMOS_HTTP_PORT: z.coerce.number().int().min(1).max(65_535).default(3_000),
});

export interface McpConfig {
  contractId: string;
  agentAccount: string;
  agentSecretKey: string;
  brokerUrl: string;
  brokerRecipient: string;
  rpcUrl: string;
  networkId: string;
  pollIntervalMs: number;
  pollTimeoutMs: number;
  requestGas: bigint;
  httpPort: number;
}

export class ConfigError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "ConfigError";
  }
}

function recipientFromUrl(url: string): string {
  // `URL.host` already contains the port when one is present.
  return new URL(url).host;
}

export function loadConfig(env: NodeJS.ProcessEnv = process.env): McpConfig {
  const parsed = envSchema.safeParse(env);
  if (!parsed.success) {
    const problems = parsed.error.issues
      .map((issue) => `${issue.path.join(".") || "environment"}: ${issue.message}`)
      .join("; ");
    throw new ConfigError(`invalid Mnemos configuration (${problems})`);
  }
  const value = parsed.data;
  return {
    contractId: value.MNEMOS_CONTRACT_ID,
    agentAccount: value.MNEMOS_AGENT_ACCOUNT,
    agentSecretKey: value.MNEMOS_AGENT_KEY,
    brokerUrl: value.MNEMOS_BROKER_URL.replace(/\/+$/u, ""),
    brokerRecipient: value.MNEMOS_BROKER_RECIPIENT ?? recipientFromUrl(value.MNEMOS_BROKER_URL),
    rpcUrl: value.NEAR_RPC_URL,
    networkId: value.MNEMOS_NETWORK_ID,
    pollIntervalMs: value.MNEMOS_POLL_INTERVAL_MS,
    pollTimeoutMs: value.MNEMOS_POLL_TIMEOUT_MS,
    requestGas: value.MNEMOS_REQUEST_GAS,
    httpPort: value.MNEMOS_HTTP_PORT,
  };
}
