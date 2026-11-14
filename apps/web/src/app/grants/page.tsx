"use client";

import { useMutation, useQuery } from "@tanstack/react-query";
import { useState } from "react";

import { Button } from "@/components/Button";
import { EmptyState } from "@/components/EmptyState";
import { Notice } from "@/components/Notice";
import { PageHeader } from "@/components/PageHeader";
import { StatusMark } from "@/components/StatusMark";
import { nearToYocto } from "@/lib/amount";
import { formatNear, formatTimestamp, truncateAccount } from "@/lib/format";
import { callView, connectWallet, sendContractCall, walletAccounts, type GrantView } from "@/lib/near";
import { describeError, useSession } from "@/lib/session";

import { KNOWLEDGE_SCOPES as SCOPES } from "@/lib/scopes";


export default function GrantsPage(): React.ReactNode {
  const { status, account } = useSession();
  const [agent, setAgent] = useState("");
  const [scopes, setScopes] = useState<string[]>(["travel"]);
  const [price, setPrice] = useState("0.01");
  const [dailyCap, setDailyCap] = useState("10");
  const [days, setDays] = useState("1");
  const [tokens, setTokens] = useState("256");
  const [lookup, setLookup] = useState("");
  const [editing, setEditing] = useState<GrantView | null>(null);
  const [revokeTarget, setRevokeTarget] = useState<string | null>(null);
  const [revokeText, setRevokeText] = useState("");
  const [notice, setNotice] = useState<{ tone: "success" | "error"; text: string } | null>(null);

  // The contract lists every grant the owner gave, so the screen does not
  // depend on which browser created them.
  const grants = useQuery({
    queryKey: ["grants", account],
    enabled: status === "signed-in" && account !== null,
    queryFn: async () =>
      (await callView<GrantView[]>("grants_by_owner", { owner: account ?? "" })) ?? [],
    retry: false,
  });

  const looked = useQuery({
    queryKey: ["grant-lookup", lookup, account],
    enabled: status === "signed-in" && lookup.trim().length > 3,
    queryFn: async () =>
      await callView<GrantView>("get_grant", {
        owner: account ?? "",
        agent: lookup.trim(),
      }),
    retry: false,
  });

  /**
   * Load an existing grant into the form. The contract upserts on
   * `create_grant`, so submitting the form again is the edit.
   */
  const edit = (grant: GrantView): void => {
    setEditing(grant);
    setAgent(grant.agent);
    setScopes(grant.scopes);
    setPrice(formatNear(grant.price, 6));
    setDailyCap(String(grant.daily_cap));
    const remainingNs = BigInt(grant.expires_ns) - BigInt(Math.round(Date.now() / 1000)) * 1_000_000_000n;
    const remainingDays = Math.max(1, Math.ceil(Number(remainingNs) / 86_400_000_000_000));
    setDays(String(remainingDays));
    setTokens(String(grant.max_answer_tokens));
    setNotice(null);
  };

  const create = useMutation({
    mutationFn: async () => {
      const wallet = await connectWallet();
      const accounts = await walletAccounts(wallet);
      const signer = accounts[0];
      if (signer === undefined || account === null) {
        throw new Error("connect the owner wallet first");
      }
      const yocto = nearToYocto(price);
      if (yocto === null) {
        throw new Error("the price must be an amount of NEAR with at most 24 decimals");
      }
      const expiryNs = (
        BigInt(Math.round(Date.now() / 1000)) * 1_000_000_000n +
        BigInt(Math.round(Number(days) * 86_400)) * 1_000_000_000n
      ).toString();
      const result = await sendContractCall(wallet, {
        method: "create_grant",
        args: {
          agent: agent.trim(),
          scopes,
          price: yocto,
          daily_cap: Number(dailyCap),
          expires_ns: expiryNs,
          max_answer_tokens: Number(tokens),
        },
        signerId: signer,
      });
      return result;
    },
    onSuccess: async () => {
      setNotice({
        tone: "success",
        text: `Grant created for ${agent.trim()}. It is revocable from this page at any time.`,
      });
      await grants.refetch();
    },
    onError: (error: unknown) => {
      setNotice({ tone: "error", text: describeError(error) });
    },
  });

  const revoke = useMutation({
    mutationFn: async (target: string) => {
      const wallet = await connectWallet();
      const accounts = await walletAccounts(wallet);
      const signer = accounts[0];
      if (signer === undefined) {
        throw new Error("connect the owner wallet first");
      }
      return await sendContractCall(wallet, {
        method: "revoke_grant",
        args: { agent: target },
        signerId: signer,
      });
    },
    onSuccess: async () => {
      setNotice({ tone: "success", text: "Grant revoked. The next read fails on chain." });
      setRevokeTarget(null);
      setRevokeText("");
      await grants.refetch();
    },
    onError: (error: unknown) => {
      setNotice({ tone: "error", text: describeError(error) });
    },
  });

  const signedOut = status !== "signed-in";

  return (
    <div className="space-y-10 pb-16">
      <PageHeader
        title="Who may read, for how long, at what price"
        lede="A grant names one agent, the scopes it may read, the price per read, a daily cap, an expiry and an answer budget. Revoking it takes effect on the next read."
      />

      {signedOut ? (
        <Notice tone="info" title="Sign in to manage grants">
          Grants are created by the owner account, so the wallet that owns the vault has
          to sign the transaction.
        </Notice>
      ) : null}

      {notice === null ? null : (
        <Notice tone={notice.tone} title={notice.tone === "success" ? "Done" : "The call failed"}>
          {notice.text}
        </Notice>
      )}

      <div className="grid gap-10 lg:grid-cols-[minmax(0,26rem)_minmax(0,1fr)]">
        <section aria-labelledby="new-grant" className="card space-y-4 px-5 py-5">
          <h2 id="new-grant" className="text-title">
            New grant
          </h2>
          <form noValidate
            className="space-y-4"
            onSubmit={(event) => {
              event.preventDefault();
              create.mutate();
            }}
          >
            <label className="flex flex-col gap-1">
              <span className="field-label">Agent account</span>
              <input
                value={agent}
                readOnly={editing !== null}
                onChange={(event) => {
                  setAgent(event.target.value);
                }}
                placeholder="mnemos-agent-xxxxxxxx.testnet"
                className="min-h-11 rounded-xl border border-rule bg-sunken px-3.5 text-body outline-none focus:border-accent read-only:opacity-70"
              />
            </label>

            <fieldset className="space-y-2">
              <legend className="field-label">Scopes</legend>
              <div className="flex flex-wrap gap-2">
                {SCOPES.map((scope) => {
                  const active = scopes.includes(scope);
                  return (
                    <label
                      key={scope}
                      className={`inline-flex min-h-11 cursor-pointer items-center gap-2 border px-3 text-caption ${
                        active ? "border-ink bg-ink text-canvas" : "border-rule text-ink"
                      }`}
                    >
                      <input
                        type="checkbox"
                        className="sr-only"
                        checked={active}
                        onChange={() => {
                          setScopes(
                            active ? scopes.filter((item) => item !== scope) : [...scopes, scope],
                          );
                        }}
                      />
                      {scope}
                    </label>
                  );
                })}
              </div>
              <p className="text-caption text-muted">
                A grant with several scopes lets the agent read each of them. Scope
                isolation still applies: an item in another scope is never decrypted.
              </p>
            </fieldset>

            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
              <label className="flex flex-col gap-1">
                <span className="field-label">Price per read (NEAR)</span>
                <input
                  value={price}
                  onChange={(event) => {
                    setPrice(event.target.value);
                  }}
                  className="min-h-11 rounded-xl border border-rule bg-sunken px-3.5 text-body outline-none focus:border-accent"
                />
              </label>
              <label className="flex flex-col gap-1">
                <span className="field-label">Daily cap</span>
                <input
                  value={dailyCap}
                  inputMode="numeric"
                  onChange={(event) => {
                    setDailyCap(event.target.value);
                  }}
                  className="min-h-11 rounded-xl border border-rule bg-sunken px-3.5 text-body outline-none focus:border-accent"
                />
              </label>
              <label className="flex flex-col gap-1">
                <span className="field-label">Expires in (days)</span>
                <input
                  value={days}
                  inputMode="numeric"
                  onChange={(event) => {
                    setDays(event.target.value);
                  }}
                  className="min-h-11 rounded-xl border border-rule bg-sunken px-3.5 text-body outline-none focus:border-accent"
                />
              </label>
              <label className="flex flex-col gap-1">
                <span className="field-label">Answer tokens</span>
                <input
                  value={tokens}
                  inputMode="numeric"
                  onChange={(event) => {
                    setTokens(event.target.value);
                  }}
                  className="min-h-11 rounded-xl border border-rule bg-sunken px-3.5 text-body outline-none focus:border-accent"
                />
              </label>
            </div>

            <p className="numeric text-caption text-muted">
              {nearToYocto(price) === null
                ? "the price must be an amount of NEAR"
                : `charged per read: ${formatNear(nearToYocto(price) ?? "0")} NEAR · at most ${dailyCap} reads a day`}
            </p>

            <div className="flex flex-wrap items-center gap-3">
              <Button
                type="submit"
                disabled={
                  signedOut || create.isPending || agent.trim().length < 3 || scopes.length === 0
                }
              >
                {create.isPending
                  ? "Waiting for the wallet…"
                  : editing === null
                    ? "Create grant"
                    : "Update the grant"}
              </Button>
              {editing === null ? null : (
                <button
                  type="button"
                  className="field-label min-h-11 rounded-full border border-rule px-4 transition-colors hover:border-ink"
                  onClick={() => {
                    setEditing(null);
                    setAgent("");
                    setScopes(["travel"]);
                    setPrice("0.01");
                    setDailyCap("10");
                    setDays("1");
                    setTokens("256");
                  }}
                >
                  Cancel the edit
                </button>
              )}
            </div>
          </form>
        </section>

        <section aria-labelledby="active-grants" className="card min-w-0 px-5 py-5">
          <h2 id="active-grants" className="text-title">
            Grants
          </h2>

          {grants.data?.length === 0 ? (
            <EmptyState
              title="No grants yet"
              body="Create one on the left. The contract keeps the list, so it is the same in every browser."
            />
          ) : null}

          {grants.data?.map((grant) => (
            <GrantRow
              key={grant.agent}
              agent={grant.agent}
              grant={grant}
              onRevoke={(target) => {
                setRevokeTarget(target);
                setRevokeText("");
              }}
              onEdit={(grant) => {
                edit(grant);
              }}
            />
          ))}

          <div className="mt-8 border-t border-rule pt-6">
            <label className="flex flex-col gap-1">
              <span className="field-label">Look up a grant by agent</span>
              <input
                value={lookup}
                onChange={(event) => {
                  setLookup(event.target.value);
                }}
                placeholder="mnemos-agent-xxxxxxxx.testnet"
                className="min-h-11 rounded-xl border border-rule bg-sunken px-3.5 text-body outline-none focus:border-accent"
              />
            </label>
            {looked.data === null && lookup.trim().length > 3 ? (
              <p className="mt-3 text-caption text-muted">
                No grant exists for this agent and owner.
              </p>
            ) : null}
            {looked.data !== undefined && looked.data !== null ? (
              <div className="mt-4">
                <GrantRow
                  agent={looked.data.agent}
                  grant={looked.data}
                  onRevoke={(target) => {
                    setRevokeTarget(target);
                    setRevokeText("");
                  }}
                  onEdit={(grant) => {
                    edit(grant);
                  }}
                />
              </div>
            ) : null}
          </div>
        </section>
      </div>

      {revokeTarget === null ? null : (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-canvas/85 p-4 backdrop-blur-sm">
          <div
            role="dialog"
            aria-modal="true"
            aria-labelledby="revoke-title"
            className="card max-h-[88dvh] w-full max-w-[32rem] overflow-y-auto px-6 py-6"
          >
            <h2 id="revoke-title" className="text-title">
              Revoke this grant
            </h2>
            <p className="mt-2 text-body text-muted">
              Revoking stops every future read by{" "}
              <span className="hash">{truncateAccount(revokeTarget, 12, 6)}</span>. The next
              request fails on chain with <code className="hash">E_GRANT_REVOKED</code>.
              Reads already served keep their receipts.
            </p>
            <label className="mt-4 flex flex-col gap-1">
              <span className="field-label">Type REVOKE to confirm</span>
              <input
                value={revokeText}
                onChange={(event) => {
                  setRevokeText(event.target.value);
                }}
                className="min-h-11 rounded-xl border border-rule bg-sunken px-3.5 text-body outline-none focus:border-accent"
              />
            </label>
            <div className="mt-5 flex gap-3">
              <Button
                tone="destructive"
                disabled={revokeText.trim().toUpperCase() !== "REVOKE" || revoke.isPending}
                onClick={() => {
                  revoke.mutate(revokeTarget);
                }}
              >
                Revoke the grant
              </Button>
              <Button
                tone="quiet"
                onClick={() => {
                  setRevokeTarget(null);
                  setRevokeText("");
                }}
              >
                Keep the grant
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function GrantRow({
  agent,
  grant,
  onRevoke,
  onEdit,
}: {
  agent: string;
  grant: GrantView | null;
  onRevoke: (agent: string) => void;
  onEdit: (grant: GrantView) => void;
}): React.ReactNode {
  if (grant === null) {
    return (
      <div className="border-b border-rule py-4">
        <p className="hash text-body break-all">{agent}</p>
        <p className="mt-1 text-caption text-muted">
          No grant exists for this agent and owner.
        </p>
      </div>
    );
  }
  const expired = BigInt(Date.now()) * 1_000_000n >= BigInt(grant.expires_ns);
  const state = grant.revoked ? "revoked" : expired ? "expired" : "active";
  return (
    <div className="border-b border-rule py-4">
      <div className="flex flex-wrap items-baseline justify-between gap-3">
        <p className="hash text-body break-all">{grant.agent}</p>
        <StatusMark
          kind={state === "active" ? "verified" : "refused"}
          label={state === "active" ? "Active" : state === "revoked" ? "Revoked" : "Expired"}
        />
      </div>
      <dl className="mt-3 grid grid-cols-2 gap-x-6 gap-y-2 sm:grid-cols-4">
        <div>
          <dt className="field-label">Scopes</dt>
          <dd className="hash text-caption">{grant.scopes.join(", ")}</dd>
        </div>
        <div>
          <dt className="field-label">Price</dt>
          <dd className="numeric text-caption">{formatNear(grant.price)} NEAR</dd>
        </div>
        <div>
          <dt className="field-label">Reads left today</dt>
          <dd className="numeric text-caption">
            {grant.remaining_today} of {grant.daily_cap}
          </dd>
        </div>
        <div>
          <dt className="field-label">Expires</dt>
          <dd className="numeric text-caption">{formatTimestamp(Number(BigInt(grant.expires_ns) / 1_000_000n))}</dd>
        </div>
      </dl>
      <div className="mt-3 flex flex-wrap items-center gap-4">
        <button
          type="button"
          className="field-label inline-flex min-h-11 items-center underline decoration-rule underline-offset-4 hover:text-ink"
          onClick={() => {
            onEdit(grant);
          }}
        >
          Edit
        </button>
        {state === "active" ? (
          <button
            type="button"
            className="field-label inline-flex min-h-11 items-center text-destructive underline decoration-rule underline-offset-4 hover:text-destructive"
            onClick={() => {
              onRevoke(grant.agent);
            }}
          >
            Revoke
          </button>
        ) : null}
      </div>
    </div>
  );
}
