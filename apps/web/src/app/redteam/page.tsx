"use client";

import { useMutation } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";

import { Button } from "@/components/Button";
import { EmptyState } from "@/components/EmptyState";
import { Notice } from "@/components/Notice";
import { PageHeader } from "@/components/PageHeader";
import { StatusMark, type StatusKind } from "@/components/StatusMark";
import { brokerApi, type RedteamAttack, type RedteamReport } from "@/lib/broker";
import { describeError, useSession } from "@/lib/session";

const SCOPES = ["travel", "health", "work", "preferences"];

const OUTCOME: Record<RedteamAttack["outcome"], { kind: StatusKind; label: string }> = {
  blocked: { kind: "verified", label: "Blocked" },
  withheld: { kind: "verified", label: "Withheld" },
  refused: { kind: "verified", label: "Refused" },
  residual: { kind: "pending", label: "Residual risk" },
  passed: { kind: "verified", label: "No leak found" },
};

export default function RedteamPage(): React.ReactNode {
  const { status } = useSession();
  const [scope, setScope] = useState(SCOPES[0] ?? "travel");

  const run = useMutation({
    mutationFn: async () => await brokerApi.startRedteam(scope),
  });

  const [report, setReport] = useState<RedteamReport | null>(null);
  const [runError, setRunError] = useState<string | null>(null);
  const jobId = useRef<string | null>(null);

  /**
   * The run takes about forty seconds, so it happens in the broker and the
   * browser polls for the result instead of holding one request open.
   */
  useEffect(() => {
    const id = jobId.current;
    if (id === null) {
      return;
    }
    let cancelled = false;
    const timer = setInterval(() => {
      void (async () => {
        try {
          const status = await brokerApi.redteamStatus(id);
          if (cancelled) {
            return;
          }
          if (status.status === "done" && status.result !== null) {
            setReport(status.result);
            setRunError(null);
            jobId.current = null;
            clearInterval(timer);
          } else if (status.status === "failed") {
            setRunError(status.error ?? "the run failed");
            jobId.current = null;
            clearInterval(timer);
          }
        } catch (error) {
          if (!cancelled) {
            setRunError(describeError(error));
            jobId.current = null;
            clearInterval(timer);
          }
        }
      })();
    }, 2_000);
    return () => {
      cancelled = true;
      clearInterval(timer);
    };
  }, [run.isPending, report]);

  const start = (): void => {
    setReport(null);
    setRunError(null);
    run.mutate(undefined, {
      onSuccess: (started) => {
        jobId.current = started.job_id;
      },
    });
  };

  return (
    <div className="space-y-10 pb-16">
      <PageHeader
        title="Try to take the memory apart"
        lede="A fixed set of extraction prompts runs through the production pipeline: the same decryption, the same prompt, the same output filter. Nothing is sent to the chain and nothing is charged."
      />

      <Notice tone="info" title="This is a simulation">
        The attacks run against your own vault through the broker, using the same filter
        as a live read. They never create an on-chain request, never move credit and
        never leave a receipt. A result of &quot;residual risk&quot; means the filter did
        not catch it, not that it passed.
      </Notice>

      <div className="grid gap-10 lg:grid-cols-[minmax(0,22rem)_minmax(0,1fr)]">
        <section aria-labelledby="run" className="card space-y-4 px-5 py-5">
          <h2 id="run" className="text-title">
            Run the attack set
          </h2>
          <label className="flex flex-col gap-1">
            <span className="field-label">Scope</span>
            <select
              value={scope}
              onChange={(event) => {
                setScope(event.target.value);
              }}
              className="min-h-11 rounded-xl border border-rule bg-sunken px-3.5 text-body outline-none focus:border-accent"
            >
              {SCOPES.map((name) => (
                <option key={name} value={name}>
                  {name}
                </option>
              ))}
            </select>
          </label>
          <Button
            onClick={start}
            disabled={status !== "signed-in" || run.isPending || jobId.current !== null}
          >
            {run.isPending || jobId.current !== null
              ? "Running the attacks…"
              : "Run the attack set"}
          </Button>
          {run.isPending || jobId.current !== null ? (
            <p className="text-caption text-muted" aria-live="polite">
              Six attacks, six model calls. This takes about forty seconds; the result
              appears here when it is ready.
            </p>
          ) : null}
          {status !== "signed-in" ? (
            <p className="text-caption text-muted">
              Sign in first: the run reads your own vault through the broker.
            </p>
          ) : null}
          {run.isError ? (
            <Notice tone="error" title="The run did not start">
              {describeError(run.error)}
            </Notice>
          ) : null}
          {runError === null ? null : (
            <Notice tone="error" title="The run did not finish">
              {runError}
            </Notice>
          )}
        </section>

        <section aria-labelledby="results" className="card min-w-0 px-5 py-5">
          <h2 id="results" className="text-title">
            Results
          </h2>

          {report === null ? (
            <EmptyState
              title="No run yet"
              body="Run the attack set to see which extraction attempts the filter stops and which remain a residual risk."
            />
          ) : (
            <>
              <p className="mt-2 text-caption text-muted">
                {report.attacks.length} attacks against {report.items_considered} items in
                scope {report.scope} using {report.model}.
              </p>
              <div className="mt-4 space-y-3">
                {report.attacks.map((attack) => {
                  const outcome = OUTCOME[attack.outcome];
                  return (
                    <div key={attack.id} className="card-flat px-4 py-4">
                      <div className="flex flex-wrap items-baseline justify-between gap-3">
                        <p className="text-lede text-ink">{attack.label}</p>
                        <StatusMark kind={outcome.kind} label={outcome.label} />
                      </div>
                      <p className="mt-2 font-mono text-caption text-muted">
                        {attack.question}
                      </p>
                      <p className="mt-2 max-w-[68ch] text-body text-muted">{attack.reason}</p>
                      {attack.answer_preview === null ? null : (
                        <p className="mt-2 border-l border-rule pl-3 font-mono text-caption text-muted">
                          {attack.answer_preview}
                        </p>
                      )}
                    </div>
                  );
                })}
              </div>
              <p className="mt-5 max-w-[68ch] text-caption text-muted">{report.note}</p>
            </>
          )}
        </section>
      </div>
    </div>
  );
}
