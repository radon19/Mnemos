import type { ActivityAttestation } from "@/lib/broker";
import { formatTimestamp } from "@/lib/format";

export interface EvidenceBlockProps {
  attestation: ActivityAttestation | null;
  chatId: string | null;
  receiptTxHash: string | null;
  servedAt: string | null;
}

function deploymentLabel(deployment: Record<string, unknown>): string {
  const compose = deployment.app_compose_sha256;
  if (typeof compose === "string") {
    return compose;
  }
  const hash = deployment.compose_hash;
  if (typeof hash === "string") {
    return hash;
  }
  return "recorded";
}

/**
 * The evidence block is the detail view of a read: which model answered, who
 * signed, what the TEE reported, and where the receipt landed on chain.
 */
export function EvidenceBlock({
  attestation,
  chatId,
  receiptTxHash,
  servedAt,
}: EvidenceBlockProps): React.ReactNode {
  const signer = attestation?.signer;
  const deployment = attestation?.deployment;

  const rows: { label: string; value: React.ReactNode }[] = [
    {
      label: "Signature kind",
      value: attestation?.signature_kind ?? "—",
    },
    {
      label: "Signing address",
      value: (
        <span className="hash break-all">
          {signer?.signing_address ?? "—"}
        </span>
      ),
    },
    {
      label: "Signing algorithm",
      value: signer?.signing_algo ?? "—",
    },
    {
      label: "TCB status",
      value: attestation?.tcb_status ?? "—",
    },
    {
      label: "GPU evidence",
      value: attestation?.gpu_evidence ?? "—",
    },
    {
      label: "Advisories",
      value:
        attestation?.advisory_ids !== undefined && attestation.advisory_ids.length > 0
          ? attestation.advisory_ids.join(", ")
          : "none reported",
    },
    {
      label: "Deployment",
      value:
        deployment === undefined ? (
          "—"
        ) : (
          <span className="hash break-all">{deploymentLabel(deployment)}</span>
        ),
    },
    {
      label: "Verified at",
      value: formatTimestamp(attestation?.verified_at ?? null),
    },
    { label: "Fresh preflight", value: attestation?.fresh_preflight === true ? "New nonce and verified evidence for this inference" : "Not recorded for this historical read" },
    { label: "Model reports", value: typeof attestation?.model_attestations === "number" ? attestation.model_attestations : "—" },
    { label: "Chat id", value: <span className="hash break-all">{chatId ?? "—"}</span> },
    { label: "Served at", value: formatTimestamp(servedAt) },
    {
      label: "Receipt transaction",
      value: receiptTxHash === null ? (
        "—"
      ) : (
        <span className="hash break-all">{receiptTxHash}</span>
      ),
    },
  ];

  return (
    <dl className="grid grid-cols-1 gap-x-8 sm:grid-cols-[minmax(9rem,14rem)_minmax(0,1fr)]">
      {rows.map((row) => (
        <div key={row.label} className="contents">
          <dt className="field-label border-t border-rule py-2">{row.label}</dt>
          <dd className="border-t border-rule py-2 text-body text-ink">{row.value}</dd>
        </div>
      ))}
    </dl>
  );
}
