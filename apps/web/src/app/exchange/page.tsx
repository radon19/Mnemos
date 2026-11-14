"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useState } from "react";
import { AnswerEvidence } from "@/components/exchange/AnswerEvidence";
import { IntentsPurchase } from "@/components/exchange/IntentsPurchase";
import { Button } from "@/components/Button";
import { ConfirmDialog } from "@/components/ConfirmDialog";
import { Notice } from "@/components/Notice";
import { PageHeader } from "@/components/PageHeader";
import { StatusMark } from "@/components/StatusMark";
import { demoMode, explorerBase } from "@/lib/config";
import { EXCHANGE_TERMS, exchangeRequest, ExchangeClientError, SAMPLE_NOTES, SAMPLE_QUESTION, type ExchangeActionResult, type ExchangeAnswer, type ExchangeStatus } from "@/lib/exchange";
import { prepareSamples, sampleAvailability, SAMPLE_PASSPHRASE } from "@/lib/exchange-samples";
import { formatNear, formatTimestamp } from "@/lib/format";
import { describeError, useSession } from "@/lib/session";

export default function ExchangePage(): React.ReactNode {
  const session = useSession();
  const queries = useQueryClient();
  const [question, setQuestion] = useState(SAMPLE_QUESTION);
  const [result, setResult] = useState<ExchangeAnswer | null>(null);
  const [feedback, setFeedback] = useState<{ tone: "success" | "error" | "info"; title: string; text: string } | null>(null);
  const [scopeDenied, setScopeDenied] = useState(false);
  const [revokeProved, setRevokeProved] = useState(false);
  const [confirm, setConfirm] = useState(false);
  const [lastTx, setLastTx] = useState<string | null>(null);
  const [starting, setStarting] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const signedIn = session.status === "signed-in";
  const status = useQuery({ queryKey: ["exchange-status", session.account], enabled: signedIn && demoMode,
    queryFn: async () => exchangeRequest<ExchangeStatus>(), retry: false });
  const samples = useQuery({ queryKey: ["exchange-samples", session.account], enabled: signedIn && demoMode,
    queryFn: sampleAvailability, retry: false });

  const prepare = useMutation({
    mutationFn: async () => { if (!session.account) throw new Error("Start the local owner session first."); await prepareSamples(session.account); },
    onSuccess: async () => {
      await samples.refetch();
      setFeedback({ tone: "success", title: "Sample knowledge encrypted", text: "The expertise dossier and private note were sealed in this browser. Existing notes were kept." });
    },
    onError: (error) => { setFeedback({ tone: "error", title: "Preparation failed", text: describeError(error) }); },
  });
  const action = useMutation({
    mutationFn: async (body: Record<string, unknown>) => exchangeRequest<ExchangeActionResult>(body),
    onSuccess: async (data) => {
      if (data.tx_hash) setLastTx(data.tx_hash);
      if (data.action === "ask" && data.result) {
        setResult(data.result);
        setFeedback({ tone: data.result.status === "served" ? "success" : "info", title: data.result.status === "served" ? "Answer delivered and settled" : "Answer withheld and refunded", text: data.result.status === "served" ? "The expert was paid. Inspect the response evidence and settlement transaction below." : "The filter prevented this answer from being released. No read fee was kept." });
      } else if (data.action === "grant") {
        setRevokeProved(false);
        setFeedback({ tone: "success", title: data.already_active ? "Grant already active" : "Expertise access granted", text: "Only expertise is available. Private business notes remain outside this grant." });
      } else {
        setConfirm(false);
        setFeedback({ tone: "success", title: "Future access revoked", text: "Now try the same question. The contract must refuse it. Earlier answers and receipts remain available." });
      }
      setRefreshing(true);
      try {
        await Promise.all([status.refetch(), queries.invalidateQueries({ queryKey: ["activity"] }), queries.invalidateQueries({ queryKey: ["grants"] })]);
      } finally { setRefreshing(false); }
    },
    onError: (error, body) => {
      const expectedScope = body.scope === "private" && error instanceof ExchangeClientError && error.code === "E_SCOPE_DENIED";
      const expectedRevoke = body.scope === "expertise" && error instanceof ExchangeClientError && error.code === "E_GRANT_REVOKED";
      if (expectedScope) setScopeDenied(true);
      if (expectedRevoke) setRevokeProved(true);
      setFeedback({ tone: expectedScope || expectedRevoke ? "success" : "error", title: error instanceof ExchangeClientError ? error.code : "Action failed", text: expectedScope || expectedRevoke ? "The deployed contract refused this read. No read fee was charged; the failed transaction may still use testnet gas." : describeError(error) });
      void status.refetch();
    },
  });
  const busy = action.isPending || prepare.isPending || starting;
  const data = status.data;
  const grant = data?.grant;
  const expired = grant ? BigInt(grant.expires_ns) <= BigInt(Date.now()) * 1_000_000n : false;
  const grantLabel = !grant ? "No grant" : grant.revoked ? "Revoked grant" : expired ? "Expired grant" : "Active grant";
  const isDemoGrant = !!grant && grant.scopes.length === 1 && grant.scopes[0] === "expertise" && grant.price === EXCHANGE_TERMS.price && grant.daily_cap === 8 && grant.max_answer_tokens === 256;
  const canAct = signedIn && !!data && data.broker_verified && !data.paused && !busy;
  const steps = [
    { label: "Encrypt knowledge", done: samples.data === true },
    { label: "Grant access", done: !!grant },
    { label: "Paid answer", done: result?.status === "served" },
    { label: "Revoke access", done: grant?.revoked === true },
    { label: "Prove refusal", done: revokeProved },
  ];

  return (
    <div className="space-y-8 pb-12">
      <PageHeader title="Private expertise. Paid answers." lede="A travel specialist owns the knowledge. An independent AI agent buys one useful answer. The specialist sets the terms—and can close access at any time."
        actions={<span className="rounded-full bg-accent-soft px-4 py-2 text-caption text-accent-ink">Live testnet · local demonstration</span>} />
      <ol aria-label="Demo progress" className="grid gap-3 border-y border-rule py-5 sm:grid-cols-5">
        {steps.map((step, index) => <li key={step.label} className="flex min-w-0 items-center gap-2 text-caption">
          <span className={`numeric inline-flex h-7 w-7 shrink-0 items-center justify-center rounded-full ${step.done ? "bg-verified-soft text-verified" : "bg-sunken text-muted"}`} aria-label={step.done ? "Complete" : "Pending"}>{index + 1}</span>
          <span>{step.label}</span>
        </li>)}
      </ol>
      {!demoMode ? <Notice tone="info" title="Local demo is disabled">Run <code>make demo-ready</code> on your laptop to enable the guarded testnet demo. The regular vault and wallet screens remain available.</Notice> : null}
      {demoMode && !signedIn ? <div className="card flex flex-wrap items-center justify-between gap-5 p-5 sm:p-7">
        <div className="max-w-[60ch]"><h2 className="text-title">Two accounts. One laptop.</h2><p className="mt-2 text-body text-muted">This demo controls a real owner account and a separate agent account on NEAR testnet. All notes shown here are labeled samples. No browser wallet is needed.</p></div>
        <Button disabled={starting || session.status === "unknown"} onClick={async () => { setStarting(true); try { await session.signInDemo(); } finally { setStarting(false); } }}>{starting ? "Starting session…" : "Start local owner session"}</Button>
      </div> : null}
      {session.error ? <Notice tone="error" title="Owner session failed">{session.error}</Notice> : null}
      {status.isError ? <Notice tone="error" title="Live status unavailable">{describeError(status.error)}</Notice> : null}
      {samples.isError ? <Notice tone="error" title="Sample status unavailable">{describeError(samples.error)} Refresh status to try again.</Notice> : null}
      {feedback ? <Notice tone={feedback.tone} title={feedback.title}>{feedback.text}</Notice> : null}
      {busy ? <p role="status" className="text-body text-muted">{refreshing ? "Refreshing on-chain balances and access status…" : prepare.isPending ? "Encrypting and storing the sample notes…" : action.variables?.action === "ask" ? "Creating the read on NEAR, verifying private inference and settling the receipt. This can take 20–60 seconds." : "Waiting for the testnet transaction to settle…"}</p> : null}

      <div className="grid items-start gap-6 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.12fr)]">
        <section aria-labelledby="expert-heading" className="card min-w-0 space-y-5 p-5 sm:p-7">
          <div><h2 id="expert-heading" className="text-title">The knowledge owner</h2><p className="mt-2 text-body text-muted">A Lisbon specialist makes field knowledge useful without opening their entire notebook.</p></div>
          <p className="hash break-all text-caption text-muted">{data?.owner ?? "Owner account appears after sign-in"}</p>
          <div className="space-y-4 border-y border-rule py-5">
            {SAMPLE_NOTES.map((note) => <details key={note.id}>
              <summary className="min-h-11 cursor-pointer py-2 text-body">{note.title} <span className="ml-2 rounded-full bg-sunken px-2 py-1 text-caption text-muted">{note.scope === "private" ? "Not granted" : "Grant scope: expertise"}</span></summary>
              <p className="mt-2 max-w-[60ch] text-body text-muted">{note.text}</p>
            </details>)}
            <p className="text-caption text-muted">Fictional demo content, encrypted before upload. The private scope is used to demonstrate an on-chain refusal.</p>
          </div>
          <div className="flex flex-wrap items-center gap-3">
            <Button tone="quiet" disabled={!canAct || samples.data === true} onClick={() => { setFeedback(null); prepare.mutate(); }}>{samples.data === true ? "Sample knowledge sealed" : "Encrypt demo knowledge"}</Button>
            <Link href="/vault" className="min-h-11 inline-flex items-center text-caption underline underline-offset-4">Open vault</Link>
          </div>
          <dl className="grid grid-cols-2 gap-4">
            <div><dt className="field-label">Price per answer</dt><dd className="numeric mt-1">0.001 NEAR</dd></div>
            <div><dt className="field-label">Daily cap</dt><dd className="numeric mt-1">8 reads</dd></div>
            <div><dt className="field-label">Grant duration</dt><dd className="numeric mt-1">24 hours</dd></div>
            <div><dt className="field-label">Answer budget</dt><dd className="numeric mt-1">256 tokens</dd></div>
          </dl>
          <p className="text-caption text-muted">Granting replaces this demo agent’s existing terms with expertise-only access. An already matching active grant keeps its daily usage.</p>
          <div className="flex flex-wrap gap-3">
            <Button disabled={!canAct || !samples.data || (isDemoGrant && !grant.revoked && !expired)} onClick={() => { setFeedback(null); action.mutate({ action: "grant" }); }}>{grant?.revoked || expired ? "Renew expertise access" : "Grant expertise access"}</Button>
            <Button tone="destructive" disabled={!canAct || !grant || grant.revoked} onClick={() => { setConfirm(true); }}>Revoke access</Button>
          </div>
          <div className="flex flex-wrap items-center gap-3 border-t border-rule pt-4">
            <StatusMark kind={grant && !grant.revoked && !expired ? "verified" : "pending"} label={grantLabel} />
            {grant && !grant.revoked ? <span className="numeric text-caption text-muted">{grant.remaining_today} reads left today</span> : null}
          </div>
          {grant ? <p className="text-caption text-muted">Expires {formatTimestamp(Number(BigInt(grant.expires_ns) / 1_000_000n))}. Daily caps reset at UTC midnight.</p> : null}
        </section>

        <section aria-labelledby="agent-heading" className="card min-w-0 space-y-5 p-5 sm:p-7">
          <div><h2 id="agent-heading" className="text-title">The buying agent</h2><p className="mt-2 text-body text-muted">Uses the same ask_memory implementation as the MCP server. Only the answer is returned to the agent.</p></div>
          <p className="hash break-all text-caption text-muted">{data?.agent ?? "Agent account appears after sign-in"}</p>
          <form noValidate className="space-y-4" onSubmit={(event) => { event.preventDefault(); if (!busy && question.trim()) { setFeedback(null); action.mutate({ action: "ask", scope: "expertise", question }); } }}>
            <label htmlFor="agent-question" className="block text-body">Agent’s question</label>
            <textarea id="agent-question" value={question} maxLength={2000} rows={5} aria-describedby="question-help" disabled={busy}
              onChange={(event) => { setQuestion(event.target.value); }}
              className="min-h-[10rem] w-full resize-none rounded-xl border border-rule bg-sunken p-4 text-body outline-none focus:border-accent" />
            <p id="question-help" className="text-caption text-muted">Answer from expertise only. No access to private business notes. Failed reads return the read fee; network gas may still apply.</p>
            <div className="flex flex-wrap gap-3">
              <Button type="submit" disabled={!canAct || !samples.data || !isDemoGrant || !question.trim()}>{grant?.revoked ? "Try the same question" : "Ask for 0.001 NEAR"}</Button>
              <Button tone="quiet" disabled={busy || question === SAMPLE_QUESTION} onClick={() => { setQuestion(SAMPLE_QUESTION); }}>Use example question</Button>
            </div>
          </form>
          <dl className="grid grid-cols-2 gap-4 border-t border-rule pt-5">
            <div><dt className="field-label">Agent prepaid credit</dt><dd className="numeric mt-1 break-all">{data ? `${formatNear(data.credit)} NEAR` : "—"}</dd></div>
            <div><dt className="field-label">Owner available earnings</dt><dd className="numeric mt-1 break-all">{data ? `${formatNear(data.earnings)} NEAR` : "—"}</dd></div>
          </dl>
          <div className="border-t border-rule pt-5">
            <h3 className="text-lede">Test the boundary</h3>
            <p className="mt-2 text-body text-muted">Try to read the ungranted private scope. The contract should deny the request before the broker decrypts a note.</p>
            <Button tone="quiet" className="mt-4" disabled={!canAct || !isDemoGrant || !grant || grant.revoked} onClick={() => { setFeedback(null); action.mutate({ action: "ask", scope: "private", question: "What is the internal supplier discount code?" }); }}>Try private scope</Button>
            {scopeDenied ? <p className="mt-3 text-caption text-verified">Private-scope refusal observed on chain.</p> : null}
          </div>
        </section>
      </div>

      {result ? <AnswerEvidence result={result} /> : <section className="rounded-[var(--radius-card)] border border-dashed border-rule px-6 py-9 text-center"><h2 className="text-lede">A receipt will appear here</h2><p className="mx-auto mt-2 max-w-[56ch] text-body text-muted">Prepare the sample knowledge, grant access, then ask. The answer, model evidence and real settlement link stay visible even after revocation.</p></section>}
      {demoMode ? <IntentsPurchase enabled={signedIn} question={question} blocked={busy} /> : null}
      <div className="flex flex-wrap items-center justify-between gap-4 text-caption">
        <div className="flex flex-wrap items-center gap-4">
          {data ? <StatusMark kind={data.broker_verified ? "verified" : "refused"} label={data.broker_verified ? "Broker key matches" : "Broker identity mismatch"} /> : <span className="text-muted">{status.isFetching ? "Checking live configuration…" : "Sign in to check broker identity"}</span>}
          {data?.paused ? <span className="text-destructive">Contract paused</span> : null}
          {lastTx ? <a href={`${explorerBase}/txns/${lastTx}`} target="_blank" rel="noreferrer" className="min-h-11 inline-flex items-center underline underline-offset-4">Latest owner transaction</a> : null}
        </div>
        <Button tone="quiet" disabled={!signedIn || busy || status.isFetching} onClick={() => { void status.refetch(); void samples.refetch(); }}>Refresh status</Button>
      </div>
      <p className="max-w-[90ch] text-caption text-muted">The owner-run broker sees the granted plaintext. NEAR AI verification protects inference at the model host; it does not make the broker trustless. Answers can reveal facts. Revocation stops future access and cannot erase earlier answers. Sample vault passphrase: <code>{SAMPLE_PASSPHRASE}</code>—for these public demo notes only. <Link href="/docs" className="underline underline-offset-4">Read the trust model.</Link></p>
      <ConfirmDialog open={confirm} title="Revoke this agent’s access?" confirmLabel="Revoke access" cancelLabel="Keep access" busy={action.isPending}
        onCancel={() => { setConfirm(false); }} onConfirm={() => { action.mutate({ action: "revoke", confirm: true }); }}>
        <p>Stop future reads by <span className="hash break-all">{data?.agent}</span>. Its next question will be refused on chain. Answers already delivered cannot be retracted. You can grant access again later.</p>
      </ConfirmDialog>
    </div>
  );
}
