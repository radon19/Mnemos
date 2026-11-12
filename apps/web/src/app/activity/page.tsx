"use client";

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";
import { Button } from "@/components/Button";
import { EmptyState } from "@/components/EmptyState";
import { EvidenceBlock } from "@/components/EvidenceBlock";
import { LedgerTable } from "@/components/LedgerTable";
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
          <span className="rounded-full bg-sunken px-3 py-1.5 text-caption text-muted" aria-live="polite">
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
        <section aria-labelledby="reads" className="card min-w-0 px-5 py-5">
          <h2 id="reads" className="sr-only">
            Reads
          </h2>
          {items.length === 0 ? (
            <EmptyState
              title="No reads yet"
              body="When an agent asks a question inside a granted scope, the receipt appears here within a second."
            />
          ) : (
            <div className="mt-3">
              <LedgerTable<ActivityItem>
                caption="Reads served by the broker"
                rows={items}
                rowKey={(item) => String(item.req_id)}
                rowClassName={(item) =>
                  arriving.has(item.req_id) ? "receipt-arrival" : undefined
                }
                onRowClick={(item) => {
                  setSelected(item);
                }}
                columns={[
                  {
                    key: "scope",
                    header: "Scope",
                    primary: true,
                    render: (item) => {
                      const state = stateOf(item);
                      return (
                        <span className="flex flex-wrap items-center gap-2">
                          <span className="hash text-body">{item.scope}</span>
                          <StatusMark kind={state.kind} label={state.label} />
                          {item.error_code === null ? null : (
                            <span className="field-label text-destructive">{item.error_code}</span>
                          )}
                        </span>
                      );
                    },
                  },
                  {
                    key: "time",
                    header: "Time",
                    render: (item) => (
                      <span className="numeric text-caption text-muted">
                        {formatTimestamp(item.served_at ?? item.created_at)}
                      </span>
                    ),
                  },
                  {
                    key: "agent",
                    header: "Agent",
                    secondary: true,
                    render: (item) => (
                      <span className="hash text-caption break-all">
                        {truncateAccount(item.agent, 8, 4)}
                      </span>
                    ),
                  },
                  {
                    key: "price",
                    header: "Price",
                    render: (item) => (
                      <span className="numeric text-caption">{formatNear(item.price)} NEAR</span>
                    ),
                  },
                  {
                    key: "receipt",
                    header: "Receipt",
                    render: (item) => (
                      <Hash
                        value={item.receipt_hash ?? ""}
                        label="Receipt hash"
                        copyable
                      />
                    ),
                  },
                ]}
              />
            </div>
          )}
        </section>

        <aside aria-labelledby="evidence" className="card min-w-0 px-5 py-5">
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
