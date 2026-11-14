"use client";

import { useMutation, useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { Button } from "../Button";
import { ConfirmDialog } from "../ConfirmDialog";
import { EvidenceBlock } from "../EvidenceBlock";
import { Hash } from "../Hash";
import { Notice } from "../Notice";
import { StatusMark } from "../StatusMark";
import type { ActivityAttestation } from "@/lib/broker";

interface Payment {
  correlation_id: string; status: string;
  details: { intent_hash?: string; tx_hash?: string };
}
interface WalletStatus {
  network: "mainnet"; asset: string; buyer_id: string; seller_account: string;
  balances: { balances: { asset_id: string; available_raw: string }[] };
  policy: unknown;
  unfinished?: { read_id: string; status: string }[];
  reads: { read_id: string; status: string; payment: Payment | null; refund: Payment | null }[];
}
interface PaidAnswer {
  read_id: string; answer: string; network: "mainnet"; verified: boolean;
  answer_hash: string; payment: Payment; attestation_summary: ActivityAttestation;
}
interface Purchase { read_id: string; scope: "expertise"; question: string }

async function request<T>(body?: Purchase | { action: "refund"; read_id: string }): Promise<T> {
  let response: Response;
  try {
    response = await fetch("/api/demo/commerce", {
      method: body ? "POST" : "GET", headers: { "content-type": "application/json" },
      ...(body ? { body: JSON.stringify(body) } : {}), cache: "no-store",
    });
  } catch { throw new Error("Connection lost. Refresh wallet status, then retry the same purchase ID."); }
  const data = await response.json() as T & { code?: string; message?: string; details?: { refund_status?: string } };
  if (!response.ok) throw new Error(`${data.code ?? "E_PAYMENT"}: ${data.message ?? "Request failed."}${data.details?.refund_status ? ` Refund: ${data.details.refund_status}.` : ""}`);
  return data;
}

export function IntentsPurchase({ enabled, question, blocked = false }: { enabled: boolean; question: string; blocked?: boolean }): React.ReactNode {
  const [confirm, setConfirm] = useState(false);
  const [pending, setPending] = useState<Purchase | null>(null);
  const wallet = useQuery({ queryKey: ["commerce-wallet"], enabled,
    queryFn: async () => request<WalletStatus>(), retry: false });
  const purchase = useMutation({
    mutationFn: async (body: Purchase) => request<PaidAnswer>(body),
    onSuccess: () => { setPending(null); void wallet.refetch(); },
    onError: () => { void wallet.refetch(); },
  });
  const recovery = useMutation({
    mutationFn: async (readId: string) => request<{ status: string }>({ action: "refund", read_id: readId }),
    onSuccess: () => { setPending(null); purchase.reset(); void wallet.refetch(); },
    onError: () => { void wallet.refetch(); },
  });
  const balance = wallet.data?.balances.balances.find(item => item.asset_id === wallet.data.asset)?.available_raw ?? "0";
  const available = BigInt(balance);
  const funded = available >= 10000n;
  const pendingDone = !!pending && wallet.data?.reads.some(read => read.read_id === pending.read_id && ["served", "refunded"].includes(read.status));
  // Recover the server's unfinished ID after a reload. Never replace an
  // ambiguous purchase with a fresh charge, even if its payment emptied the wallet.
  const unfinished = wallet.data?.unfinished?.[0] ?? wallet.data?.reads.find(read => ["pending", "paying", "paid", "refund_pending"].includes(read.status));
  const retryBody = pending && !pendingDone ? pending : unfinished
    ? { read_id: unfinished.read_id, scope: "expertise" as const, question } : null;
  const retry = retryBody !== null;
  const start = () => {
    const body = retryBody ?? { read_id: crypto.randomUUID(), scope: "expertise" as const, question };
    setPending(body);
    setConfirm(false);
    purchase.mutate(body);
  };
  const result = purchase.data;
  return (
    <section aria-labelledby="intents-heading" className="card min-w-0 space-y-5 p-5 sm:p-7">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="max-w-[65ch]"><h2 id="intents-heading" className="text-title">Buy through NEAR Intents</h2><p className="mt-2 text-body text-muted">The buyer’s wallet follows owner-signed spending rules. A confirmed 0.01 USDC payment unlocks one expertise answer with fresh model verification.</p></div>
        <span className="rounded-full bg-accent-soft px-4 py-2 text-caption text-accent-ink">Mainnet · USDC</span>
      </div>
      <p className="max-w-[75ch] text-caption text-muted">This is a separate payment option. Its mainnet USDC balance and receipts are independent of the testnet NEAR demonstration above. It uses the question entered above and permits expertise only.</p>
      {!enabled ? <p className="text-body text-muted">Start the local owner session to inspect this wallet.</p> : wallet.isPending ? <p role="status" className="text-body text-muted">Reading the live agent wallet and policy…</p> : wallet.error ? <Notice tone="info" title="Agent wallet unavailable">{wallet.error.message} Run <code>make agent-api-setup</code>, restart the broker, then refresh this wallet.</Notice> : <>
        <dl className="grid gap-4 border-y border-rule py-4 sm:grid-cols-3">
          <div><dt className="field-label">Buyer available balance</dt><dd className="numeric mt-1">{(available / 1_000_000n).toString()}.{(available % 1_000_000n).toString().padStart(6, "0")} USDC</dd></div>
          <div><dt className="field-label">Price per answer</dt><dd className="numeric mt-1">0.01 USDC</dd></div>
          <div><dt className="field-label">Payment availability</dt><dd className="mt-1"><StatusMark kind={funded ? "verified" : "pending"} label={funded ? "Wallet funded" : "Funding needed"} /></dd></div>
        </dl>
        {!funded ? <p className="text-body text-muted">Fund this wallet through 1Click with <code>make agent-api-fund</code>, then refresh. An unfunded wallet cannot buy an answer.</p> : null}
        <details><summary className="min-h-11 cursor-pointer py-2 text-body">Inspect the live spending policy</summary><pre className="mt-3 max-h-72 overflow-auto rounded-xl bg-sunken p-4 text-caption">{JSON.stringify(wallet.data.policy, null, 2)}</pre></details>
        <div className="flex flex-wrap gap-3">
          <Button disabled={(!funded && !retry) || !question.trim() || blocked || recovery.isPending || purchase.isPending || wallet.isFetching}
            onClick={() => { if (retry) start(); else setConfirm(true); }}>{purchase.isPending ? "Waiting for payment and verified answer…" : retry ? "Retry the same purchase" : "Buy answer for 0.01 USDC"}</Button>
          {retryBody ? <Button tone="quiet" disabled={purchase.isPending || recovery.isPending || wallet.isFetching}
            onClick={() => { recovery.mutate(retryBody.read_id); }}>{recovery.isPending ? "Recovering payment…" : "Recover or refund by ID"}</Button> : null}
          <Button tone="quiet" disabled={purchase.isPending || recovery.isPending || wallet.isFetching} onClick={() => { void wallet.refetch(); }}>Refresh agent wallet</Button>
        </div>
      </>}
      {purchase.isPending ? <p role="status" className="text-body text-muted">Waiting for actual Intents settlement before decrypting expertise. Verification and settlement may take up to a few minutes.</p> : null}
      {recovery.error ? <Notice tone="error" title="Recovery did not finish">{recovery.error.message}</Notice> : null}
      {recovery.isSuccess ? <Notice tone="success" title="Refund confirmed">The purchase was refunded. No original question was needed and no new purchase was started.</Notice> : null}
      {purchase.error ? <Notice tone="error" title="Purchase did not finish">{purchase.error.message}</Notice> : null}
      {retry ? <p className="break-all text-caption text-muted">Purchase ID: <span className="hash">{retryBody.read_id}</span>. Retrying keeps this ID to prevent duplicate charges. After a reload, enter the original question above; a different question is refused without a new charge.</p> : null}
      {result ? <div className="space-y-4 border-t border-rule pt-5">
        <StatusMark kind="verified" label="Intents payment settled · answer verified" />
        <p className="max-w-[70ch] whitespace-pre-wrap text-lede">{result.answer}</p>
        <p className="break-all text-caption text-muted">Operation: <span className="hash">{result.payment.correlation_id}</span></p>
        <p className="field-label">Settled Intents hash</p><Hash value={result.payment.details.intent_hash ?? "Unavailable"} copyable />
        <details><summary className="min-h-11 cursor-pointer py-2 text-body">Inspect model evidence</summary><EvidenceBlock attestation={result.attestation_summary} chatId={typeof result.attestation_summary.chat_id === "string" ? result.attestation_summary.chat_id : null} receiptTxHash={null} servedAt={null} /></details>
      </div> : null}
      {wallet.data?.reads.length ? <details><summary className="min-h-11 cursor-pointer py-2 text-body">Recent Intents purchases and refunds</summary><ul className="divide-y divide-rule">{wallet.data.reads.map(read => <li key={read.read_id} className="space-y-1 py-3 text-caption"><p className="hash break-all">{read.read_id}</p><p>{read.status}{read.payment ? ` · payment ${read.payment.status}` : ""}{read.refund ? ` · refund ${read.refund.status}` : ""}</p></li>)}</ul></details> : null}
      <p className="max-w-[80ch] text-caption text-muted">Payment is confirmed through the Agent API’s execution status and matched to this purchase. Confidential Intents has an intent hash; it may have no public mainnet explorer transaction. The owner-run broker still sees the expertise it processes.</p>
      <ConfirmDialog open={confirm} title="Buy this expertise answer?" intent="purchase" busyLabel="Buying…"
        confirmLabel="Pay 0.01 USDC" cancelLabel="Keep funds" onCancel={() => { setConfirm(false); }} onConfirm={start}>
        <p>Spend 0.01 real mainnet USDC from the configured buyer wallet to buy an expertise answer. The broker attempts a refund if inference fails or the answer is withheld. A pending payment or refund must be checked before starting another purchase.</p>
      </ConfirmDialog>
    </section>
  );
}
