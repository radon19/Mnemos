import Link from "next/link";

import { Hash } from "@/components/Hash";
import { StatusMark } from "@/components/StatusMark";

const STEPS: { step: string; title: string; body: string }[] = [
  {
    step: "01",
    title: "The owner encrypts a note",
    body: "The browser seals it with a key derived from the owner's passphrase and wraps a copy for the broker's public key. Plaintext never leaves the device.",
  },
  {
    step: "02",
    title: "The owner grants a scope",
    body: "A grant names the agent, the scopes it may read, the price per read, a daily cap, an expiry and an answer-token budget. It can be revoked at any moment.",
  },
  {
    step: "03",
    title: "The agent asks, and pays first",
    body: "The contract charges the agent and creates the read request before anything is decrypted. A request that is not served is refunded.",
  },
  {
    step: "04",
    title: "The broker answers one scope",
    body: "It decrypts only the granted scope, asks a NEAR AI Cloud TEE model, and rejects any answer that reproduces twelve or more consecutive words of the memory.",
  },
  {
    step: "05",
    title: "A receipt lands on chain",
    body: "The receipt stores a hash of the request and answer, never the content. The owner can check what was read, when, by whom, and for how much.",
  },
];

const LIMITS: { title: string; body: string }[] = [
  {
    title: "The model host cannot read the prompt",
    body: "End-to-end encryption and a verified TEE attestation mean the answer was produced inside attested hardware. The broker still sees the plaintext it decrypts.",
  },
  {
    title: "Repeated narrow questions can still leak facts",
    body: "A lexical filter stops bulk reproduction, not a single fact asked in a hundred different ways. Daily caps and prices are the mitigation.",
  },
  {
    title: "The gateway signature does not chain to the model",
    body: "NEAR's gateway signs the response, but that signature is not yet a proof that the provider's own key produced the answer. The attestation is the evidence.",
  },
];

const EXAMPLE_RECEIPT = {
  receipt_hash: "9f2c41d7a0b83e5c6d1f4a2b7e9c3d58a1f6b0d4e7c2a9b5d8f1e3c6a0b2d4f7",
  price: "0.01",
  scope: "travel",
  agent: "mnemos-agent-76badc8e.testnet",
  signed_at: "2026-11-11 09:41:02Z",
  signer: "0x236f5a6b91dd47dc3b7b36e43d4eb531a042ffb8f8fbf3a1555b78cef4fdda4c",
  tcb: "UpToDate",
};

export default function LandingPage(): React.ReactNode {
  return (
    <div className="space-y-16 pb-16">
      <section className="rule pb-10">
        <h1 className="max-w-[18ch] text-display text-ink">
          Your notes stay encrypted. Reads are metered, scoped and receipted.
        </h1>
        <p className="mt-5 max-w-[64ch] text-lede text-muted">
          An AI agent can answer a question about your private notes, but only inside a
          scope you granted, only up to a cap you set, and only for a price you chose.
          Every served read leaves a hash-only receipt on NEAR that you can check.
        </p>
        <div className="mt-7 flex flex-wrap items-center gap-4">
          <Link
            href="/setup"
            className="inline-flex min-h-11 items-center border border-ink bg-ink px-4 text-body text-paper transition-colors hover:bg-transparent hover:text-ink"
          >
            Open the ledger
          </Link>
          <Link href="/redteam" className="text-body text-muted underline underline-offset-4 hover:text-ink">
            See what a red-team run reports
          </Link>
        </div>
      </section>

      <section aria-labelledby="how-a-read-happens" className="grid gap-8 lg:grid-cols-[minmax(0,18rem)_minmax(0,1fr)]">
        <div>
          <h2 id="how-a-read-happens" className="text-title">
            How a read happens
          </h2>
          <p className="mt-3 max-w-[42ch] text-body text-muted">
            Five steps, in this order, every time. Nothing is decrypted before the
            money has moved.
          </p>
        </div>
        <ol className="border-t border-rule">
          {STEPS.map((step) => (
            <li key={step.step} className="grid gap-2 border-b border-rule py-5 sm:grid-cols-[3rem_minmax(0,1fr)]">
              <span className="field-label pt-1">{step.step}</span>
              <div>
                <h3 className="text-lede text-ink">{step.title}</h3>
                <p className="mt-1 max-w-[68ch] text-body text-muted">{step.body}</p>
              </div>
            </li>
          ))}
        </ol>
      </section>

      <section aria-labelledby="a-receipt" className="grid gap-8 lg:grid-cols-[minmax(0,18rem)_minmax(0,1fr)]">
        <div>
          <h2 id="a-receipt" className="text-title">
            A receipt, not a transcript
          </h2>
          <p className="mt-3 max-w-[42ch] text-body text-muted">
            The chain stores a hash of what was sent and returned. It cannot show
            anybody the note.
          </p>
          <p className="field-label mt-4">Example record</p>
        </div>
        <div>
          <dl className="grid grid-cols-1 gap-x-8 border-t border-rule pt-2 sm:grid-cols-[minmax(9rem,14rem)_minmax(0,1fr)]">
            <div className="contents">
              <dt className="field-label border-b border-rule py-3">Status</dt>
              <dd className="border-b border-rule py-3">
                <StatusMark kind="verified" label="Served · verified" />
              </dd>
            </div>
            <div className="contents">
              <dt className="field-label border-b border-rule py-3">Receipt hash</dt>
              <dd className="border-b border-rule py-3">
                <Hash value={EXAMPLE_RECEIPT.receipt_hash} />
              </dd>
            </div>
            <div className="contents">
              <dt className="field-label border-b border-rule py-3">Scope</dt>
              <dd className="border-b border-rule py-3">
                <span className="hash">{EXAMPLE_RECEIPT.scope}</span>
              </dd>
            </div>
            <div className="contents">
              <dt className="field-label border-b border-rule py-3">Price</dt>
              <dd className="border-b border-rule py-3">
                <span className="numeric">{EXAMPLE_RECEIPT.price}</span> NEAR
              </dd>
            </div>
            <div className="contents">
              <dt className="field-label border-b border-rule py-3">Agent</dt>
              <dd className="border-b border-rule py-3">
                <span className="hash break-all">{EXAMPLE_RECEIPT.agent}</span>
              </dd>
            </div>
            <div className="contents">
              <dt className="field-label border-b border-rule py-3">Signed by</dt>
              <dd className="border-b border-rule py-3">
                <span className="hash break-all">{EXAMPLE_RECEIPT.signer}</span>
              </dd>
            </div>
            <div className="contents">
              <dt className="field-label border-b border-rule py-3">TCB status</dt>
              <dd className="border-b border-rule py-3">
                <span className="hash">{EXAMPLE_RECEIPT.tcb}</span>
              </dd>
            </div>
            <div className="contents">
              <dt className="field-label border-b border-rule py-3">Served at</dt>
              <dd className="border-b border-rule py-3">
                <span className="numeric">{EXAMPLE_RECEIPT.signed_at}</span>
              </dd>
            </div>
          </dl>
        </div>
      </section>

      <section aria-labelledby="honest-limits" className="grid gap-8 lg:grid-cols-[minmax(0,18rem)_minmax(0,1fr)]">
        <div>
          <h2 id="honest-limits" className="text-title">
            What it does not do
          </h2>
          <p className="mt-3 max-w-[42ch] text-body text-muted">
            The security claims are only worth what they cover.
          </p>
        </div>
        <ul className="border-t border-rule">
          {LIMITS.map((limit) => (
            <li key={limit.title} className="border-b border-rule py-5">
              <h3 className="text-lede text-ink">{limit.title}</h3>
              <p className="mt-1 max-w-[68ch] text-body text-muted">{limit.body}</p>
            </li>
          ))}
        </ul>
      </section>
    </div>
  );
}
