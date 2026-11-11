"use client";

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";
import { Button } from "@/components/Button";
import { EmptyState } from "@/components/EmptyState";
import { EvidenceBlock } from "@/components/EvidenceBlock";
import { Hash } from "@/components/Hash";
import { Notice } from "@/components/Notice";
import { PageHeader } from "@/components/PageHeader";
import { StatusMark } from "@/components/StatusMark";
import { brokerApi, type ActivityItem } from "@/lib/broker";
import { explorerBase } from "@/lib/config";
import { formatNear, formatTimestamp, truncateAccount } from "@/lib/format";
import { describeError, useSession } from "@/lib/session";

function stateOf(item: ActivityItem): { kind: "verified" | "pending" | "refused"; label: string } {
  if (item.status === "served") {
    return { kind: "verified", label: "Served" };
  }
  if (item.status === "refunded" || item.status === "withheld") {
    return { kind: "refused", label: item.status === "withheld" ? "Withheld" : "Refunded" };
  }
  return { kind: "pending", label: item.status };
}

export default function ActivityPage(): React.ReactNode {
  const queryClient = useQueryClient();
  const { status } = useSession();
  const [selected, setSelected] = useState<ActivityItem | null>(null);
  const [live, setLive] = useState<"connecting" | "live" | "off">("connecting");
  const sourceRef = useRef<EventSource | null>(null);

  const activity = useQuery({
    queryKey: ["activity"],
    queryFn: async () => brokerApi.activity({ limit: 50 }),
    enabled: status === "signed-in",
    retry: false,
  });

  useEffect(() => {
    if (status !== "signed-in") {
      return;
    }
    const url = `${process.env.NEXT_PUBLIC_BROKER_URL ?? "http://localhost:8000"}/v1/activity/stream`;
    const source = new EventSource(url, { withCredentials: true });
    sourceRef.current = source;
    source.onopen = () => {
      setLive("live");
    };
    source.onerror = () => {
      setLive("off");
    };
    source.onmessage = () => {
      void queryClient.invalidateQueries({ queryKey: ["activity"] });
    };
    return () => {
      source.close();
      sourceRef.current = null;
    };
  }, [status, queryClient]);

  const items = activity.data?.items ?? [];

  /**
   * The one authored moment: a receipt arriving in the ledger. Rows that were
   * already known stay still.
   */
  const known = useRef<Set<number>>(new Set());
  const [arriving, setArriving] = useState<Set<number>>(new Set());
  useEffect(() => {
    if (items.length === 0) {
      return;
    }
    const fresh = items.filter((item) => !known.current.has(item.req_id)).map((item) => item.req_id);
    known.current = new Set(items.map((item) => item.req_id));
    if (fresh.length === 0) {
      return;
    }
    setArriving(new Set(fresh));
    const timer = setTimeout(() => {
      setArriving(new Set());
    }, 400);
    return () => {
      clearTimeout(timer);
    };
  }, [items]);

  return (
    <div className="space-y-10 pb-16">
      <PageHeader
        title="Every read, with its receipt"
        lede="A read leaves a hash-only receipt: the agent, the scope, the price, the time and a hash. The note itself is never on chain and never in the broker's logs."
        actions={
          <span className="field-label" aria-live="polite">
            {status !== "signed-in" ? "signed out" : live === "live" ? "live" : live === "off" ? "stream offline" : "connecting"}
          </span>
        }
      />

      {status !== "signed-in" ? (
        <Notice tone="info" title="Sign in to read the ledger">
          The activity feed belongs to the owner account, so the broker needs the session
          cookie before it will list reads.
        </Notice>
      ) : null}

      {activity.isError ? (
        <Notice tone="error" title="The activity feed could not be read">
          {describeError(activity.error)}
        </Notice>
      ) : null}

      {live === "off" && status === "signed-in" ? (
        <Notice tone="info" title="The live stream is not connected">
          The list below is still accurate; it refreshes when the page reloads. The
          stream needs the broker reachable from the browser with the session cookie.
        </Notice>
      ) : null}

      <div className="grid gap-10 lg:grid-cols-[minmax(0,1fr)_minmax(0,26rem)]">
        <section aria-labelledby="reads" className="min-w-0">
          <h2 id="reads" className="sr-only">
            Reads
          </h2>
          {items.length === 0 ? (
            <EmptyState
              title="No reads yet"
              body="When an agent asks a question inside a granted scope, the receipt appears here within a second."
            />
          ) : (
            <div className="border-t border-rule">
              <table className="w-full text-left">
                <caption className="sr-only">Reads served by the broker</caption>
                <thead>
                  <tr>
                    <th scope="col" className="field-label border-b border-rule py-2">
                      Time
                    </th>
                    <th scope="col" className="field-label border-b border-rule py-2">
                      Agent
                    </th>
                    <th scope="col" className="field-label border-b border-rule py-2">
                      Scope
                    </th>
                    <th scope="col" className="field-label border-b border-rule py-2">
                      Price
                    </th>
                    <th scope="col" className="field-label border-b border-rule py-2">
                      Receipt
                    </th>
                    <th scope="col" className="field-label border-b border-rule py-2">
                      State
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {items.map((item) => {
                    const state = stateOf(item);
                    return (
                      <tr
                        key={item.req_id}
                        className={`align-top hover:bg-surface ${
                          arriving.has(item.req_id) ? "receipt-arrival" : ""
                        }`}
                        onClick={() => {
                          setSelected(item);
                        }}
                      >
                        <td className="border-b border-rule py-3 pr-4">
                          <button
                            type="button"
                            className="numeric text-caption text-muted underline decoration-transparent underline-offset-4 hover:text-ink hover:decoration-rule"
                            onClick={() => {
                              setSelected(item);
                            }}
                            aria-label={`Open the evidence for read ${item.req_id}`}
                          >
                            {formatTimestamp(item.served_at ?? item.created_at)}
                          </button>
                        </td>
                        <td className="border-b border-rule py-3 pr-4">
                          <span className="hash text-caption break-all">
                            {truncateAccount(item.agent, 8, 4)}
                          </span>
                        </td>
                        <td className="border-b border-rule py-3 pr-4">
                          <span className="hash text-caption">{item.scope}</span>
                        </td>
                        <td className="border-b border-rule py-3 pr-4">
                          <span className="numeric text-caption">{formatNear(item.price)} NEAR</span>
                        </td>
                        <td className="border-b border-rule py-3 pr-4">
                          <Hash value={item.receipt_hash ?? ""} label="Receipt hash" />
                        </td>
                        <td className="border-b border-rule py-3">
                          <StatusMark kind={state.kind} label={state.label} />
                          {item.error_code === null ? null : (
                            <p className="field-label mt-1 text-destructive">{item.error_code}</p>
                          )}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </section>

        <aside aria-labelledby="evidence" className="min-w-0">
          <h2 id="evidence" className="text-title">
            Evidence
          </h2>
          {selected === null ? (
            <p className="mt-3 text-body text-muted">
              Choose a read to see the attestation: which model answered, who signed, what
              the TEE reported and where the receipt landed.
            </p>
          ) : (
            <div className="mt-3 space-y-4">
              <div className="flex items-baseline justify-between gap-3">
                <p className="field-label">Read {selected.req_id}</p>
                <Button
                  tone="quiet"
                  onClick={() => {
                    setSelected(null);
                  }}
                >
                  Close
                </Button>
              </div>
              <EvidenceBlock
                attestation={selected.attestation}
                chatId={selected.chat_id}
                receiptTxHash={selected.receipt_tx_hash}
                servedAt={selected.served_at}
              />
              {selected.receipt_tx_hash === null ? null : (
                <a
                  className="text-caption underline decoration-rule underline-offset-4 hover:text-ink"
                  href={`${explorerBase}/tx/${selected.receipt_tx_hash}`}
                  target="_blank"
                  rel="noreferrer"
                >
                  Open the transaction in the explorer
                </a>
              )}
              {selected.refund_tx_hash === null ? null : (
                <p className="text-caption text-muted">
                  Refunded in transaction{" "}
                  <span className="hash break-all">{selected.refund_tx_hash}</span>. The
                  agent was not charged.
                </p>
              )}
            </div>
          )}
        </aside>
      </div>
    </div>
  );
}
