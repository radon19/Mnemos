"use client";

import Link from "next/link";

import { StatusMark } from "@/components/StatusMark";
import { contractId, nearNetwork } from "@/lib/config";

const SECTIONS = [
  { id: "what", label: "What it is" },
  { id: "read", label: "How a read works" },
  { id: "trust", label: "The trust model" },
  { id: "contract", label: "The contract" },
  { id: "broker", label: "The broker" },
  { id: "mcp", label: "The MCP server" },
  { id: "web", label: "The web app" },
  { id: "run", label: "Running it" },
  { id: "limits", label: "The honest limits" },
];

function Section({
  id,
  title,
  children,
}: {
  id: string;
  title: string;
  children: React.ReactNode;
}): React.ReactNode {
  return (
    <section id={id} className="scroll-mt-28 border-t border-rule pt-8">
      <h2 className="text-title">{title}</h2>
      <div className="mt-3 space-y-3 text-body text-muted [&_code]:break-all [&_code]:text-ink">{children}</div>
    </section>
  );
}

function Row({ label, value }: { label: string; value: React.ReactNode }): React.ReactNode {
  return (
    <div className="grid gap-x-6 sm:grid-cols-[minmax(9rem,15rem)_minmax(0,1fr)]">
      <dt className="field-label border-b border-rule py-2.5">{label}</dt>
      <dd className="border-b border-rule py-2.5 text-ink">{value}</dd>
    </div>
  );
}

export default function DocsPage(): React.ReactNode {
  return (
    <div className="space-y-8 pb-16">
      <header className="rule pb-6">
        <p className="field-label">Documentation</p>
        <h1 className="mt-2 max-w-[20ch] text-display text-ink">
          How Mnemos works, and what it does not promise
        </h1>
        <p className="mt-4 max-w-[62ch] text-lede text-muted">
          Everything here is true of the running deployment: the contract on{" "}
          <span className="numeric">{nearNetwork}</span> at{" "}
          <span className="numeric">{contractId}</span>, the broker, the MCP server
          and this interface.
        </p>
      </header>

      <div className="grid gap-10 lg:grid-cols-[minmax(0,14rem)_minmax(0,1fr)]">
        <nav aria-label="Contents" className="lg:sticky lg:top-28 lg:self-start">
          <p className="field-label">Contents</p>
          <ul className="mt-3 space-y-1.5">
            {SECTIONS.map((section) => (
              <li key={section.id}>
                <a
                  href={`#${section.id}`}
                  className="inline-flex min-h-9 items-center text-caption text-muted underline decoration-transparent underline-offset-4 transition-colors hover:text-ink hover:decoration-rule"
                >
                  {section.label}
                </a>
              </li>
            ))}
          </ul>
          <Link
            href="/"
            className="mt-6 inline-flex min-h-11 items-center rounded-full border border-rule px-4 text-caption text-ink transition-colors hover:border-ink"
          >
            Back to the landing page
          </Link>
        </nav>

        <div className="min-w-0 space-y-8">
          <Section id="what" title="What it is">
            <p>
              Mnemos is user-owned AI memory with metered, revocable access on NEAR. You
              keep notes in scopes. An agent can ask questions about them, but only
              through a grant you made on chain that names the scopes, the price per
              read, a daily cap and an expiry.
            </p>
            <p>
              The answer is produced inside a NEAR AI Cloud TEE with end-to-end
              encryption, and the agent receives the answer and never your notes. Every
              served read leaves a hash-only receipt on chain and pays you.
            </p>
            <p>
              The contract holds the money and the access boundary. The broker holds
              the keys and enforces the scope. You own both.
            </p>
          </Section>

          <Section id="read" title="How a read works">
            <ol className="space-y-3">
              <li>
                <strong className="text-ink">The agent asks.</strong> It creates a read
                request on chain with a hash of the question and a nonce. The contract
                charges the price, checks the grant, the scope, the cap and the expiry,
                and creates the request.
              </li>
              <li>
                <strong className="text-ink">The agent signs.</strong> It signs
                <code>mnemos:v1:ask|{"{req_id}"}|{"{sha256(question)}"}|{"{nonce}"}|{"{recipient}"}</code>{" "}
                with its key and posts it to <code>/v1/ask</code>. The broker checks
                that the signing key belongs to the agent account.
              </li>
              <li>
                <strong className="text-ink">The broker decrypts one scope.</strong> Only
                the items in the requested scope are opened, ranked and capped to a
                token budget. Plaintext is never logged.
              </li>
              <li>
                <strong className="text-ink">The model answers.</strong> The completion
                runs with <code>e2ee=true</code>. The broker calls{" "}
                <code>verify_response</code> and discards any answer whose attestation
                does not verify. There is no unverified fallback.
              </li>
              <li>
                <strong className="text-ink">The filter runs.</strong> An answer that
                shares twelve or more consecutive words with a decrypted item is
                rejected, including runs hidden in base64 or hex. The broker retries
                once with a stricter prompt and refunds if it still leaks.
              </li>
              <li>
                <strong className="text-ink">The receipt is settled.</strong>{" "}
                <code>
                  sha256(req_id|chat_id|sha256(request_bytes)|sha256(response_bytes)|
                  signing_address)
                </code>{" "}
                is written with <code>record_receipt</code>. Any failure path refunds.
              </li>
            </ol>
          </Section>

          <Section id="trust" title="The trust model">
            <p className="text-ink">What is guaranteed:</p>
            <ul className="list-disc space-y-2 pl-5">
              <li>
                The model host cannot read the prompt or the answer: the completion is
                end to end encrypted and produced inside an attested TEE.
              </li>
              <li>
                The agent cannot read anything you did not grant, and cannot read a
                request twice.
              </li>
              <li>
                The contract charges before the broker decrypts, so a failed read is
                refunded rather than paid for.
              </li>
              <li>
                You can check every read: the receipt holds the scope, the price, the
                time and a hash.
              </li>
            </ul>
            <p className="text-ink">What is not:</p>
            <ul className="list-disc space-y-2 pl-5">
              <li>
                The broker sees the plaintext it decrypts. It is owner-run for that
                reason.
              </li>
              <li>
                Repeated narrow questions can still extract facts one at a time. Caps
                and prices are the mitigation, not the filter.
              </li>
              <li>
                NEAR&apos;s gateway signature does not yet chain to the model
                provider&apos;s signature, so the attestation is the evidence rather
                than a single end-to-end proof.
              </li>
            </ul>
          </Section>

          <Section id="contract" title="The contract">
            <dl>
              <Row
                label="Address"
                value={<span className="numeric break-all">{contractId}</span>}
              />
              <Row
                label="Language"
                value={<span className="numeric">Rust, near-sdk 5.30</span>}
              />
              <Row
                label="Calls"
                value={
                  <span className="hash break-all">
                    create_grant · revoke_grant · request_read · record_receipt · refund ·
                    expire_request · deposit_credit · withdraw_credit · withdraw_earnings ·
                    pause · unpause
                  </span>
                }
              />
              <Row
                label="Views"
                value={
                  <span className="hash break-all">
                    get_grant · grants_by_owner · get_request · credit_of · earnings_of ·
                    get_broker · recent_receipts · get_config
                  </span>
                }
              />
              <Row
                label="Events"
                value={
                  <span className="hash break-all">
                    grant_created · grant_revoked · read_requested · read_served ·
                    read_refunded · request_expired · credit_deposited · earnings_withdrawn
                  </span>
                }
              />
            </dl>
          </Section>

          <Section id="broker" title="The broker">
            <p>
              A FastAPI service that decrypts one scope, calls the model and settles the
              receipt. It stores ciphertext and evidence only: there is no column that
              can hold a note, a question or an answer.
            </p>
            <dl>
              <Row
                label="Sign in"
                value={
                  <span className="hash break-all">
                    POST /v1/auth/challenge · POST /v1/auth/verify
                  </span>
                }
              />
              <Row
                label="Vault"
                value={
                  <span className="hash break-all">
                    POST /v1/vault/items · GET /v1/vault/items · GET /v1/vault/salt ·
                    DELETE /v1/vault/items/{"{id}"}
                  </span>
                }
              />
              <Row
                label="Reads"
                value={
                  <span className="hash break-all">
                    POST /v1/ask · GET /v1/activity · GET /v1/activity/stream
                  </span>
                }
              />
              <Row
                label="Red team"
                value={
                  <span className="hash break-all">
                    POST /v1/redteam/run · GET /v1/redteam/run/{"{job_id}"}
                  </span>
                }
              />
              <Row
                label="Key"
                value={
                  <span className="hash break-all">
                    GET /v1/broker/pubkey
                  </span>
                }
              />
            </dl>
            <p>
              Every error carries a stable code and a request id:{" "}
              <code>E_GRANT_REVOKED</code>, <code>E_SCOPE_DENIED</code>,{" "}
              <code>E_CAP_REACHED</code>, <code>E_OUTPUT_FILTER</code> and the rest.
            </p>
          </Section>

          <Section id="mcp" title="The MCP server">
            <p>
              Any MCP client can read the vault. The server signs the request with the
              agent key and never holds a key that can read the vault directly.
            </p>
            <dl>
              <Row
                label="ask_memory"
                value="owner, scope, question — answers from the granted scope and returns the receipt."
              />
              <Row
                label="list_grants"
                value="owner — the grant this agent holds, with price, cap and expiry."
              />
              <Row
                label="check_credit"
                value="the agent's prepaid balance."
              />
              <Row
                label="Configuration"
                value={
                  <span className="hash break-all">
                    MNEMOS_CONTRACT_ID · MNEMOS_AGENT_ACCOUNT · MNEMOS_AGENT_KEY ·
                    MNEMOS_BROKER_URL · NEAR_RPC_URL
                  </span>
                }
              />
              <Row
                label="Examples"
                value={
                  <span className="hash break-all">
                    examples/claude-code.mcp.json · examples/cursor.mcp.json
                  </span>
                }
              />
            </dl>
          </Section>

          <Section id="web" title="The web app">
            <p>
              The owner interface. Every note is encrypted in the browser before it is
              sent, and the owner can read their own notes again with the passphrase.
            </p>
            <ul className="list-disc space-y-2 pl-5">
              <li>
                <strong className="text-ink">Setup</strong> — wallet, contract and
                network, the broker key compared with the one on chain, and the vault
                passphrase. It also holds the pause switch.
              </li>
              <li>
                <strong className="text-ink">Vault</strong> — notes by scope, sealed
                in the browser, with inline delete.
              </li>
              <li>
                <strong className="text-ink">Grants</strong> — create, edit and revoke
                access, with the price, the cap, the remaining reads and the expiry.
              </li>
              <li>
                <strong className="text-ink">Activity</strong> — the live receipt
                ledger, with the attestation behind every read.
              </li>
              <li>
                <strong className="text-ink">Earnings</strong> — the balance, the
                withdrawal and the receipt history.
              </li>
              <li>
                <strong className="text-ink">Red-team</strong> — the attack set run
                against your own vault, with the reason for every result.
              </li>
            </ul>
          </Section>

          <Section id="run" title="Running it">
            <pre
              tabIndex={0}
              className="overflow-x-auto rounded-2xl bg-sunken p-4 font-mono text-caption focus-visible:outline-none"
            >
              {`cp .env.example .env      # NEARAI_API_KEY and the account ids
make install              # Node, Python and Rust dependencies
docker compose up -d --build
make check                # static checks and unit tests
make test-e2e             # sandbox, broker integration, Playwright
make demo                 # the whole flow against testnet`}
            </pre>
            <p>
              The demo signs in, stores an encrypted note, grants one scope, asks a
              question through the MCP server, prints the verified attestation and the
              receipt, runs the attack set, revokes the grant and shows the same read
              denied with <code>E_GRANT_REVOKED</code>.
            </p>
          </Section>

          <Section id="limits" title="The honest limits">
            <ul className="list-disc space-y-2 pl-5">
              <li>
                The output filter is lexical. It stops a bulk reproduction and a
                verbatim quote; it does not stop a paraphrase, and it reports that
                honestly rather than claiming coverage.
              </li>
              <li>
                The rate limiter and the activity stream are local by default,
                because the compose file runs one broker. A multi-replica
                deployment sets <code>RATE_LIMIT_BACKEND=postgres</code> and
                <code>ACTIVITY_BUS_ENABLED=true</code> to share both.
              </li>
              <li>
                The model host cannot read the prompt, but the broker can, because it
                has to decrypt in order to answer.
              </li>
              <li>
                A read that is never asked for holds the agent&apos;s credit until
                the request expires; the MCP server returns it when it notices.
              </li>
            </ul>
            <p className="flex flex-wrap items-center gap-3">
              <StatusMark kind="verified" label="Every claim here is checked by a test" />
            </p>
          </Section>
        </div>
      </div>
    </div>
  );
}
