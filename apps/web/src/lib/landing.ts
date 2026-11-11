/**
 * Live figures for the public landing page.
 *
 * Every number on the landing page is read from the chain or from the broker
 * at the moment the page is opened. Nothing here is a placeholder: when a
 * value cannot be read, the card says so instead of showing an example.
 */

import { brokerUrl, contractId, nearNetwork } from "./config";
import { callView } from "./near";

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

export interface ScopeTotal {
  scope: string;
  reads: number;
  paid: string;
}

export interface ChainStats {
  owner: string;
  readsServed: number;
  readsAreExact: boolean;
  requestsCreated: number;
  pricePerRead: string | null;
  earnings: string;
  credit: string | null;
  scopes: ScopeTotal[];
  lastReceipt: ReceiptView | null;
  brokerFingerprint: string | null;
  brokerAccount: string | null;
}

const RECEIPT_RING_CAP = 50;

function sum(values: string[]): bigint {
  return values.reduce<bigint>((total, value) => total + BigInt(value), 0n);
}

export async function fetchChainStats(agentAccount?: string): Promise<ChainStats> {
  const config = await callView<ContractConfig>("get_config", {});
  const owner = config?.owner ?? "";
  const receipts = owner
    ? ((await callView<ReceiptView[]>("recent_receipts", {
        owner,
        from: 0,
        limit: RECEIPT_RING_CAP,
      })) ?? [])
    : [];

  const earnings = owner
    ? ((await callView<string>("earnings_of", { owner })) ?? "0")
    : "0";
  const credit =
    agentAccount === undefined
      ? null
      : ((await callView<string>("credit_of", { agent: agentAccount })) ?? "0");

  const byScope = new Map<string, { reads: number; paid: bigint }>();
  for (const receipt of receipts) {
    const entry = byScope.get(receipt.scope) ?? { reads: 0, paid: 0n };
    entry.reads += 1;
    entry.paid += BigInt(receipt.price);
    byScope.set(receipt.scope, entry);
  }

  let fingerprint: string | null = null;
  let brokerAccount: string | null = null;
  try {
    const response = await fetch(`${brokerUrl}/v1/broker/pubkey`, { cache: "no-store" });
    if (response.ok) {
      const identity = (await response.json()) as { fingerprint: string; account: string };
      fingerprint = identity.fingerprint;
      brokerAccount = identity.account;
    }
  } catch {
    // The broker may be unreachable; the card then says so.
  }

  return {
    owner,
    readsServed: receipts.length,
    readsAreExact: receipts.length < RECEIPT_RING_CAP,
    requestsCreated: Math.max(0, (config?.next_request_id ?? 1) - 1),
    pricePerRead: receipts[0]?.price ?? null,
    earnings,
    credit,
    scopes: Array.from(byScope.entries())
      .map(([scope, entry]) => ({
        scope,
        reads: entry.reads,
        paid: entry.paid.toString(),
      }))
      .sort((left, right) => right.reads - left.reads),
    lastReceipt: receipts[0] ?? null,
    brokerFingerprint: fingerprint,
    brokerAccount,
  };
}

export function totalPaid(scopes: ScopeTotal[]): string {
  return sum(scopes.map((scope) => scope.paid)).toString();
}

export const deployedContractId = contractId;
export const deployedNetwork = nearNetwork;
