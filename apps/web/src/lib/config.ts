/**
 * Public runtime configuration.
 *
 * Only `NEXT_PUBLIC_*` values reach the browser. Anything secret belongs to
 * the server routes, never to this module.
 */

export const brokerUrl = (process.env.NEXT_PUBLIC_BROKER_URL ?? "http://localhost:8000").replace(
  /\/+$/u,
  "",
);

export const contractId = process.env.NEXT_PUBLIC_CONTRACT_ID ?? "";

export const nearNetwork = process.env.NEXT_PUBLIC_NEAR_NETWORK ?? "testnet";

export const nearRpcUrl =
  process.env.NEXT_PUBLIC_NEAR_RPC_URL ?? "https://test.rpc.fastnear.com";

export const brokerRecipient = process.env.NEXT_PUBLIC_BROKER_RECIPIENT ?? "localhost:8000";

export const demoMode = process.env.NEXT_PUBLIC_DEMO_MODE === "true";

export const explorerBase =
  nearNetwork === "mainnet" ? "https://nearblocks.io" : "https://testnet.nearblocks.io";

export const isConfigured = contractId !== "";
