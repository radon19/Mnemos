"use client";

import Link from "next/link";
import { EvidenceBlock } from "../EvidenceBlock";
import { Hash } from "../Hash";
import { StatusMark } from "../StatusMark";
import { explorerBase } from "@/lib/config";
import { EXCHANGE_TERMS, type ExchangeAnswer } from "@/lib/exchange";

export function AnswerEvidence({ result }: { result: ExchangeAnswer }): React.ReactNode {
  const attestation = result.attestation_summary;
  return (
    <section aria-labelledby="answer-heading" className="card receipt-arrival space-y-5 p-5 sm:p-7">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 id="answer-heading" className="text-title">The answer, with evidence</h2>
        <StatusMark kind={result.status === "served" && result.verified ? "verified" : "refused"}
          label={result.status === "served" && result.verified ? "Response verified" : "Answer withheld · refunded"} />
      </div>
      <p className="max-w-[68ch] whitespace-pre-wrap text-lede leading-relaxed">{result.answer ?? "The output filter withheld this answer. The read fee was refunded; no answer was released."}</p>
      <dl className="grid gap-x-6 gap-y-4 border-y border-rule py-4 sm:grid-cols-3">
        <div><dt className="field-label">Read</dt><dd className="numeric mt-1">#{result.req_id} · expertise</dd></div>
        <div><dt className="field-label">Read fee</dt><dd className="numeric mt-1">{result.status === "served" ? EXCHANGE_TERMS.priceNear : "0"} NEAR</dd></div>
        <div><dt className="field-label">Inference latency</dt><dd className="numeric mt-1">{(result.latency_ms / 1000).toFixed(1)} seconds</dd></div>
      </dl>
      {result.receipt_hash ? <div className="min-w-0 space-y-2"><p className="field-label">On-chain receipt hash</p><Hash value={result.receipt_hash} copyable /></div> : null}
      <div className="flex flex-wrap gap-x-6 gap-y-3 text-body">
        {result.tx_hash ? <a className="min-h-11 inline-flex items-center text-accent-ink underline underline-offset-4" href={`${explorerBase}/txns/${result.tx_hash}`} target="_blank" rel="noreferrer">View settlement transaction</a> : null}
        {result.refund_tx_hash ? <a className="min-h-11 inline-flex items-center text-accent-ink underline underline-offset-4" href={`${explorerBase}/txns/${result.refund_tx_hash}`} target="_blank" rel="noreferrer">View refund transaction</a> : null}
        <Link href="/activity" className="min-h-11 inline-flex items-center underline underline-offset-4">Open activity ledger</Link>
      </div>
      <details className="border-t border-rule pt-4">
        <summary className="min-h-11 cursor-pointer py-2 text-body">Inspect TEE and signature evidence</summary>
        <p className="my-3 text-caption text-muted">Requested model: <span className="hash break-all">{typeof attestation?.model === "string" ? attestation.model : "recorded by the broker"}</span>. Verification is performed by the owner-run broker using the NEAR AI SDK. The chain receipt records settlement; it does not independently verify the model.</p>
        <EvidenceBlock attestation={attestation} chatId={typeof attestation?.chat_id === "string" ? attestation.chat_id : null} receiptTxHash={result.tx_hash} servedAt={typeof attestation?.verified_at === "string" ? attestation.verified_at : null} />
      </details>
    </section>
  );
}
