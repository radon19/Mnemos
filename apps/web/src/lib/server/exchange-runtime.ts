import { createHash } from "node:crypto";
import { Account, actions, JsonRpcProvider, KeyPairSigner, type KeyPairString, type SerializedReturnValue } from "near-api-js";
import { askMemory, createDeps, extractContractCode, hintFor, loadConfig } from "@mnemos/mcp";
import { DemoError, demoBrokerUrl } from "./demo-guard";
import type { ExchangeDeps } from "./exchange";

export function realExchangeDeps(): ExchangeDeps {
  const owner = process.env.MNEMOS_OWNER_ACCOUNT ?? "";
  const agent = process.env.MNEMOS_AGENT_ACCOUNT ?? "";
  const contract = process.env.MNEMOS_CONTRACT_ID ?? "";
  const ownerKey = process.env.DEMO_OWNER_SECRET_KEY ?? "";
  if (!owner || !agent || !contract || !ownerKey || !process.env.MNEMOS_AGENT_KEY) {
    throw new DemoError(503, "E_DEMO_CONFIG", "Demo accounts are not configured. Run make demo-ready on your laptop.");
  }
  const provider = new JsonRpcProvider({ url: process.env.NEAR_RPC_URL ?? "https://test.rpc.fastnear.com" });
  const account = new Account(owner, provider, KeyPairSigner.fromSecretKey(ownerKey as KeyPairString));
  const config = loadConfig({ ...process.env, MNEMOS_BROKER_URL: demoBrokerUrl(), MNEMOS_BROKER_RECIPIENT: process.env.BROKER_RECIPIENT ?? process.env.NEXT_PUBLIC_BROKER_RECIPIENT ?? "localhost:8000" });
  return {
    owner, agent, contract,
    view: async <T>(method: string, args: Record<string, unknown>): Promise<T> => {
      return await provider.callFunction<SerializedReturnValue>({ contractId: contract, method, args }) as T;
    },
    identity: async () => {
      const response = await fetch(`${demoBrokerUrl()}/v1/broker/pubkey`, { cache: "no-store", signal: AbortSignal.timeout(10_000) });
      if (!response.ok) throw new DemoError(502, "E_BROKER_UNREACHABLE", "The broker identity could not be read. Run make doctor.");
      const identity = await response.json() as { fingerprint: string; public_key_b64: string; account: string; contract_id: string; network: string };
      const key = Buffer.from(identity.public_key_b64, "base64");
      if (key.length !== 32) throw new DemoError(502, "E_BROKER_MISMATCH", "The broker encryption key is invalid.");
      return { ...identity, keyFingerprint: createHash("sha256").update(key).digest("hex") };
    },
    ownerCall: async (method, args) => {
      const response = await account.signAndSendTransaction({
        receiverId: contract, actions: [actions.functionCall(method, args, 100_000_000_000_000n)],
        waitUntil: "FINAL", throwOnFailure: false,
      });
      if (typeof response.status === "object" && "Failure" in response.status) {
        const code = extractContractCode(JSON.stringify(response.status.Failure)) ?? "E_RPC_ERROR";
        throw new DemoError(409, code, hintFor(code));
      }
      return response.transaction.hash;
    },
    ask: async (input) => {
      try { return await askMemory(createDeps({ config }), input); }
      catch (error) {
        const code = error instanceof Error && "code" in error && typeof error.code === "string" ? error.code : "E_RPC_ERROR";
        throw new DemoError(409, code, hintFor(code));
      }
    },
  };
}
