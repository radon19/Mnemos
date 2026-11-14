"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";

import { QuoteCards, type QuoteCard } from "@/components/QuoteCards";
import { type StatCard } from "@/components/StatCards";
import { LandingHero } from "@/components/LandingHero";
import { StatusMark } from "@/components/StatusMark";
import { formatNear, formatTimestamp, truncateHash } from "@/lib/format";
import { fetchChainStats } from "@/lib/landing";

const PROMISES = [
  {
    title: "Encrypted before upload",
    body: "Your browser encrypts every note. The database stores ciphertext. Your owner-run broker decrypts the granted scope when answering an authorized question.",
  },
  {
    title: "Access is scoped, priced and revocable",
    body: "A grant names one agent, the scopes it may read, the price per read, a daily cap and an expiry. Revoke it and the next read fails on chain with E_GRANT_REVOKED.",
  },
  {
    title: "Every read leaves a receipt",
    body: "The contract records a receipt hash, the scope and the price. You can check which scope was used, by whom and for how much. The receipt contains no transcript.",
  },
];

const STEPS = [
  {
    title: "You encrypt a note",
    body: "The browser seals it with a key derived from your passphrase and wraps a copy for the broker's public key. Only ciphertext is uploaded to the vault.",
  },
  {
    title: "You grant one agent a scope",
    body: "A grant names the agent, the scopes it may read, the price per read, a daily cap, an expiry and an answer budget. It can be revoked at any moment.",
  },
  {
    title: "The agent asks, and pays first",
    body: "The contract charges the agent and creates the read request before anything is decrypted. A request that is not served is refunded.",
  },
  {
    title: "The broker answers one scope",
    body: "It decrypts only the granted scope, asks a NEAR AI Cloud TEE model, and rejects any answer that reproduces twelve or more consecutive words of the memory.",
  },
  {
    title: "A receipt lands on chain",
    body: "The receipt stores a hash of the request and answer, never the content. You can check what was read, when, by whom, and for how much.",
  },
];

const LIMITS = [
  {
    title: "The model host cannot read the prompt",
    body: "End-to-end encryption and a verified TEE attestation mean the answer was produced inside attested hardware. The broker still sees the plaintext it decrypts.",
  },
  {
    title: "Repeated narrow questions can still leak facts",
    body: "A lexical filter stops bulk reproduction, not a single fact asked in a hundred different ways. Daily caps and prices are the mitigation.",
  },
  {
    title: "A receipt is evidence of settlement",
    body: "The registered broker verifies model evidence and records settlement. The chain does not independently verify inference or prove that the broker followed its policy.",
  },
];

export default function LandingPage(): React.ReactNode {
  const stats = useQuery({
    queryKey: ["landing-stats"],
    queryFn: async () => await fetchChainStats(),
    retry: false,
    staleTime: 30_000,
  });

  const data = stats.data;

  const cards: StatCard[] = [
    {
      label: "Reads served",
      value: data === undefined ? "—" : String(data.readsServed),
      note:
        data === undefined
          ? "reading the contract"
          : data.readsAreExact
            ? "receipts on chain"
            : "50 most recent receipts",
      accent: true,
    },
    {
      label: "Earned by the owner",
      value: data === undefined ? "—" : formatNear(data.earnings),
      unit: "NEAR",
      note: data === undefined ? "reading the contract" : "balance, not yet withdrawn",
    },
    {
      label: "Price per read",
      value:
        data === undefined || data.pricePerRead === null ? "—" : formatNear(data.pricePerRead),
      unit: "NEAR",
      note: "set by the grant",
    },
    {
      label: "Requests created",
      value: data === undefined ? "—" : String(data.requestsCreated),
      note: data === undefined ? "reading the contract" : "served or refunded",
    },
  ];

  const quotes: QuoteCard[] = [];
  if (data !== undefined && data.lastReceipt !== null) {
    quotes.push({
      source: "Latest receipt on chain",
      quote: `Read #${data.lastReceipt.req_id} · scope ${data.lastReceipt.scope} · ${formatNear(
        data.lastReceipt.price,
      )} NEAR paid by the agent`,
      detail: truncateHash(data.lastReceipt.receipt_hash, 12, 10),
    });
  }
  quotes.push({
    source: "Expected contract refusal after revocation",
    quote: "Smart contract panicked: E_GRANT_REVOKED: grant has been revoked",
    detail: "the next read fails on chain, by design",
  });
  quotes.push({
    source: "The broker's public key",
    quote:
      data === undefined || data.brokerFingerprint === null
        ? "the broker is unreachable right now"
        : `fingerprint ${data.brokerFingerprint.slice(0, 16)}…`,
    detail:
      data === undefined || data.brokerAccount === null
        ? "registered on chain, checked in the app"
        : data.brokerAccount,
  });

  return (
    <div className="space-y-20 pb-16">
      <LandingHero cards={cards} ready={data !== undefined} failed={stats.isError} />

      <section aria-label="What it does" className="grid gap-8 border-b border-rule px-2 pb-10 md:grid-cols-3">
        {PROMISES.map((promise) => (
          <article key={promise.title}>
            <h2 className="text-lede text-ink">{promise.title}</h2>
            <p className="mt-3 max-w-[42ch] text-body text-muted">{promise.body}</p>
          </article>
        ))}
      </section>

      <section aria-labelledby="how-a-read-happens" className="space-y-5">
        <h2 id="how-a-read-happens" className="text-title">
          How a read happens
        </h2>
        <p className="max-w-[56ch] text-body text-muted">
          Five steps, in this order, every time. Nothing is decrypted before the money
          has moved.
        </p>
        <ol className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
          {STEPS.map((step, index) => (
            <li key={step.title} className="card px-5 py-4">
              <p className="field-label">Step {index + 1}</p>
              <h3 className="mt-1.5 text-lede text-ink">{step.title}</h3>
              <p className="mt-1.5 text-body text-muted">{step.body}</p>
            </li>
          ))}
        </ol>
      </section>

      <section aria-labelledby="a-receipt" className="grid gap-6 lg:grid-cols-[minmax(0,22rem)_minmax(0,1fr)]">
        <div>
          <h2 id="a-receipt" className="text-title">
            A receipt, not a transcript
          </h2>
          <p className="mt-3 max-w-[40ch] text-body text-muted">
            The chain stores a hash of what was sent and returned. It cannot show anybody
            the note.
          </p>
        </div>
        <div className="card px-5 py-2">
          <dl className="grid grid-cols-1 gap-x-8 sm:grid-cols-[minmax(9rem,14rem)_minmax(0,1fr)]">
            {data === undefined || data.lastReceipt === null ? (
              <div className="contents">
                <dt className="field-label border-b border-rule py-3">Status</dt>
                <dd className="border-b border-rule py-3">
                  <StatusMark kind="pending" label={stats.isError ? "Contract unavailable" : data ? "No receipts recorded yet" : "Reading the contract"} />
                </dd>
              </div>
            ) : (
              <>
                <div className="contents">
                  <dt className="field-label border-b border-rule py-3">Status</dt>
                  <dd className="border-b border-rule py-3">
                    <StatusMark kind="verified" label="Served · recorded on chain" />
                  </dd>
                </div>
                <div className="contents">
                  <dt className="field-label border-b border-rule py-3">Read</dt>
                  <dd className="border-b border-rule py-3">
                    <span className="numeric">#{data.lastReceipt.req_id}</span>
                  </dd>
                </div>
                <div className="contents">
                  <dt className="field-label border-b border-rule py-3">Scope</dt>
                  <dd className="border-b border-rule py-3">
                    <span className="hash">{data.lastReceipt.scope}</span>
                  </dd>
                </div>
                <div className="contents">
                  <dt className="field-label border-b border-rule py-3">Paid</dt>
                  <dd className="border-b border-rule py-3">
                    <span className="numeric">{formatNear(data.lastReceipt.price)}</span> NEAR
                  </dd>
                </div>
                <div className="contents">
                  <dt className="field-label border-b border-rule py-3">Receipt hash</dt>
                  <dd className="border-b border-rule py-3">
                    <span className="hash break-all">{data.lastReceipt.receipt_hash}</span>
                  </dd>
                </div>
                <div className="contents">
                  <dt className="field-label border-b border-rule py-3">Served at</dt>
                  <dd className="border-b border-rule py-3">
                    <span className="numeric">
                      {formatTimestamp(Number(BigInt(data.lastReceipt.served_ns) / 1_000_000n))}
                    </span>
                  </dd>
                </div>
              </>
            )}
          </dl>
        </div>
      </section>

      <section aria-labelledby="what-it-returns" className="space-y-5">
        <div className="flex flex-wrap items-baseline justify-between gap-3">
          <h2 id="what-it-returns" className="text-title">
            What the system actually returns
          </h2>
          <span className="text-caption text-muted">Live receipt and expected contract behavior</span>
        </div>
        <QuoteCards quotes={quotes} />
      </section>

      <section aria-labelledby="honest-limits" className="space-y-5">
        <h2 id="honest-limits" className="text-title">
          What it does not do
        </h2>
        <p className="max-w-[56ch] text-body text-muted">
          The security claims are only worth what they cover.
        </p>
        <ul className="grid gap-3 md:grid-cols-3">
          {LIMITS.map((limit) => (
            <li key={limit.title} className="card px-5 py-4">
              <h3 className="text-lede text-ink">{limit.title}</h3>
              <p className="mt-1.5 text-body text-muted">{limit.body}</p>
            </li>
          ))}
        </ul>
      </section>

      <section className="card px-6 py-10 text-center">
        <h2 className="text-title">Put a note behind a grant</h2>
        <p className="mx-auto mt-3 max-w-[46ch] text-body text-muted">
          Unlock the vault, add a note, and create a grant an agent can use. The demo
          script does the whole thing against testnet in one command.
        </p>
        <div className="mt-6 flex flex-wrap items-center justify-center gap-3">
          <Link
            href="/setup"
            className="inline-flex min-h-11 items-center rounded-full bg-ink px-6 text-body text-canvas transition-opacity hover:opacity-90"
          >
            Open the ledger
          </Link>
          <Link
            href="/docs"
            className="inline-flex min-h-11 items-center rounded-full border border-rule bg-canvas px-6 text-body text-ink transition-colors hover:border-ink"
          >
            Read the documentation
          </Link>
        </div>
      </section>
    </div>
  );
}
