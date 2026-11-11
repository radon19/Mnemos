/**
 * NEAR access from the browser.
 *
 * The owner signs in with a NEAR wallet through `@hot-labs/near-connect`, the
 * wallet connection recommended by the NEAR documentation. The wallet signs
 * two things for Mnemos: the NEP-413 sign-in message and the contract
 * transactions that create or revoke a grant and withdraw earnings.
 */

import {
  NearConnector,
  nearActionsToConnectorActions,
  type NearWalletBase,
} from "@hot-labs/near-connect";
import { JsonRpcProvider, actions, type SerializedReturnValue } from "near-api-js";

import { contractId, nearNetwork, nearRpcUrl } from "./config";

type Network = "mainnet" | "testnet";

const connector = new NearConnector({});
const network: Network = nearNetwork === "mainnet" ? "mainnet" : "testnet";

export function walletConnector(): NearConnector {
  return connector;
}

export async function connectWallet(): Promise<NearWalletBase> {
  return await connector.connect({});
}

export async function connectedWallet(): Promise<NearWalletBase | undefined> {
  try {
    return await connector.wallet();
  } catch {
    return undefined;
  }
}

export async function walletAccounts(wallet: NearWalletBase): Promise<string[]> {
  const accounts = await wallet.getAccounts({ network });
  return accounts.map((account) => account.accountId);
}

export interface SignedLogin {
  publicKey: string;
  signatureB64: string;
}

/** Sign the broker's NEP-413 challenge message with the wallet. */
export async function signLoginMessage(
  wallet: NearWalletBase,
  input: { message: string; recipient: string; nonce: Uint8Array },
): Promise<SignedLogin> {
  const signed = await wallet.signMessage({
    message: input.message,
    recipient: input.recipient,
    nonce: input.nonce,
    network,
  });
  return {
    publicKey: signed.publicKey,
    signatureB64: signed.signature,
  };
}

const provider = new JsonRpcProvider({ url: nearRpcUrl });

/** Read a view function from the Mnemos contract. */
export async function callView<T extends SerializedReturnValue>(
  methodName: string,
  args: Record<string, unknown>,
): Promise<T | null> {
  const result = await provider.callFunction<T>({
    contractId,
    method: methodName,
    args,
  });
  return result ?? null;
}

export interface GrantView {
  owner: string;
  agent: string;
  scopes: string[];
  price: string;
  daily_cap: number;
  expires_ns: string;
  max_answer_tokens: number;
  revoked: boolean;
  used_today: number;
  remaining_today: number;
  day_index: number;
}

export interface ReceiptView {
  req_id: number;
  agent: string;
  scope: string;
  price: string;
  receipt_hash: string;
  served_ns: string;
}

export interface ContractConfig {
  owner: string;
  paused: boolean;
  next_request_id: number;
  request_ttl_ns: string;
  day_ns: string;
}

export interface BrokerInfo {
  broker_account: string;
  broker_pubkey_fingerprint: string;
}

/**
 * Send one contract call through the wallet.
 *
 * The wallet owns the key; this app never sees it. The action is built with
 * near-api-js and translated into the shape the connector expects.
 */
export async function sendContractCall(
  wallet: NearWalletBase,
  input: {
    method: string;
    args: Record<string, unknown>;
    deposit?: string;
    gas?: string;
    signerId?: string;
  },
): Promise<{ txHash: string }> {
  const action = actions.functionCall(
    input.method,
    input.args,
    BigInt(input.gas ?? "100000000000000"),
    BigInt(input.deposit ?? "0"),
  );
  const converted = nearActionsToConnectorActions([action]);
  const outcome = (await wallet.signAndSendTransactions({
    network,
    transactions: [
      {
        receiverId: contractId,
        actions: converted,
      },
    ],
  })) as unknown as { transaction?: { hash?: string } }[];
  const hash = outcome[0]?.transaction?.hash;
  return { txHash: typeof hash === "string" ? hash : "" };
}
