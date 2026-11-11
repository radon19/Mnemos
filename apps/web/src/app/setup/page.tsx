"use client";

import { useMutation, useQuery } from "@tanstack/react-query";
import { useState } from "react";

import { Button } from "@/components/Button";
import { Hash } from "@/components/Hash";
import { Notice } from "@/components/Notice";
import { PageHeader } from "@/components/PageHeader";
import { StatusMark } from "@/components/StatusMark";
import { brokerApi } from "@/lib/broker";
import { contractId, demoMode, explorerBase, nearNetwork } from "@/lib/config";
import { callView, type BrokerInfo, type ContractConfig } from "@/lib/near";
import { describeError, useSession } from "@/lib/session";
interface StepProps {
  index: string;
  title: string;
  status: "pending" | "done" | "failed" | "active";
  children: React.ReactNode;
}

function Step({ index, title, status, children }: StepProps): React.ReactNode {
  const label =
    status === "done" ? "Ready" : status === "failed" ? "Failed" : status === "active" ? "In progress" : "Pending";
  const kind = status === "done" ? "verified" : status === "failed" ? "refused" : "pending";
  return (
    <section className="card grid gap-3 px-5 py-5 sm:grid-cols-[3rem_minmax(0,1fr)] sm:gap-5 lg:grid-cols-[3rem_minmax(0,18rem)_minmax(0,1fr)]">
      <p className="field-label pt-1">{index}</p>
      <div>
        <h2 className="text-lede text-ink">{title}</h2>
        <div className="mt-2">
          <StatusMark kind={kind} label={label} />
        </div>
      </div>
      <div className="min-w-0 max-w-[54ch]">{children}</div>
    </section>
  );
}

export default function SetupPage(): React.ReactNode {
  const { status, account, demo, signIn, signInDemo, unlocked, unlock, lock, error, clearError } =
    useSession();
  const [passphrase, setPassphrase] = useState("");

  const identity = useQuery({
    queryKey: ["broker-identity"],
    queryFn: async () => brokerApi.identity(),
    retry: false,
  });

  const config = useQuery({
    queryKey: ["contract-config"],
    queryFn: async () => callView<ContractConfig>("get_config", {}),
    retry: false,
  });

  const onChainBroker = useQuery({
    queryKey: ["broker-on-chain", config.data?.owner],
    enabled: config.data?.owner !== undefined,
    queryFn: async () =>
      await callView<BrokerInfo>("get_broker", { owner: config.data?.owner ?? "" }),
    retry: false,
  });

  const demoSignIn = useMutation({
    mutationFn: async () => {
      await signInDemo();
    },
  });

  const servedFingerprint = identity.data?.fingerprint;
  const registeredFingerprint = onChainBroker.data?.broker_pubkey_fingerprint;
  const fingerprintMatches =
    servedFingerprint !== undefined &&
    registeredFingerprint !== undefined &&
    servedFingerprint === registeredFingerprint;

  return (
    <div className="space-y-10 pb-16">
      <PageHeader
        title="Connect, verify, unlock"
        lede="Three checks stand between the browser and your notes: the wallet that owns them, the contract that meters the reads, and the passphrase that opens the vault."
      />

      {error === null ? null : (
        <Notice tone="error" title="Sign-in failed">
          {error}
        </Notice>
      )}

      <div className="space-y-3">
        <Step
          index="01"
          title="Wallet"
          status={status === "signed-in" ? "done" : "active"}
        >
          {status === "signed-in" && account !== null ? (
            <div className="space-y-3">
              <p className="hash break-all text-body">{account}</p>
              <p className="text-caption text-muted">
                {demo
                  ? "Signed in with the local demo signer. It exists so the flow can be shown without a browser wallet; it is not a production path."
                  : "Signed in with a NEAR wallet and a NEP-413 signature over the broker challenge."}
              </p>
            </div>
          ) : (
            <div className="space-y-3">
              <p className="text-body text-muted">
                Connect the wallet that owns the vault, then sign the broker challenge. The
                signature proves the account without sending a key to the server.
              </p>
              <div className="flex flex-wrap gap-3">
                <Button
                  onClick={() => {
                    clearError();
                    void signIn();
                  }}
                >
                  Connect wallet
                </Button>
                {demoMode ? (
                  <Button
                    tone="quiet"
                    onClick={() => {
                      demoSignIn.mutate();
                    }}
                  >
                    Use local demo signer
                  </Button>
                ) : null}
              </div>
            </div>
          )}
        </Step>

        <Step
          index="02"
          title="Contract and network"
          status={contractId === "" ? "failed" : "done"}
        >
          {contractId === "" ? (
            <Notice tone="error" title="No contract configured">
              Set <code className="hash">NEXT_PUBLIC_CONTRACT_ID</code> in the environment and
              rebuild the app.
            </Notice>
          ) : (
            <dl className="grid grid-cols-1 gap-x-8 rounded-2xl bg-sunken px-5 sm:grid-cols-[10rem_minmax(0,1fr)]">
              <dt className="field-label border-b border-rule py-3 first:border-t">Contract</dt>
              <dd className="border-b border-rule py-3">
                <a
                  className="hash break-all underline decoration-rule underline-offset-4 hover:text-ink"
                  href={`${explorerBase}/address/${contractId}`}
                  target="_blank"
                  rel="noreferrer"
                >
                  {contractId}
                </a>
              </dd>
              <dt className="field-label border-b border-rule py-3 first:border-t">Network</dt>
              <dd className="border-b border-rule py-3">
                <span className="hash">{nearNetwork}</span>
              </dd>
              <dt className="field-label border-b border-rule py-3 first:border-t">Contract owner</dt>
              <dd className="border-b border-rule py-3">
                {config.data === undefined || config.data === null ? (
                  <span className="text-muted">reading…</span>
                ) : (
                  <span className="hash break-all">{config.data.owner}</span>
                )}
              </dd>
              <dt className="field-label border-b border-rule py-3 first:border-t">Paused</dt>
              <dd className="border-b border-rule py-3">
                {config.data === undefined || config.data === null ? (
                  <span className="text-muted">reading…</span>
                ) : config.data.paused ? (
                  <StatusMark kind="refused" label="Paused" />
                ) : (
                  <StatusMark kind="verified" label="Accepting reads" />
                )}
              </dd>
            </dl>
          )}
        </Step>

        <Step
          index="03"
          title="Broker key fingerprint"
          status={
            identity.isError || onChainBroker.isError
              ? "failed"
              : fingerprintMatches
                ? "done"
                : "pending"
          }
        >
          <div className="space-y-3">
            <p className="text-body text-muted">
              The broker publishes the fingerprint of its X25519 public key. The contract
              stores the same value. If they differ, the browser refuses to encrypt
              anything for this broker.
            </p>
            <dl className="grid grid-cols-1 gap-x-8 rounded-2xl bg-sunken px-5 sm:grid-cols-[10rem_minmax(0,1fr)]">
              <dt className="field-label border-b border-rule py-3 first:border-t">Served by the broker</dt>
              <dd className="border-b border-rule py-3">
                {identity.isError ? (
                  <span className="text-destructive">
                    the broker could not be reached: {describeError(identity.error)}
                  </span>
                ) : identity.data === undefined ? (
                  <span className="text-muted">reading…</span>
                ) : (
                  <Hash value={identity.data.fingerprint} head={12} tail={8} label="Broker fingerprint" />
                )}
              </dd>
              <dt className="field-label border-b border-rule py-3 first:border-t">Registered on chain</dt>
              <dd className="border-b border-rule py-3">
                {onChainBroker.data === undefined || onChainBroker.data === null ? (
                  <span className="text-muted">
                    {onChainBroker.isError ? "could not read the contract" : "reading…"}
                  </span>
                ) : (
                  <Hash
                    value={onChainBroker.data.broker_pubkey_fingerprint}
                    head={12}
                    tail={8}
                    label="Registered fingerprint"
                  />
                )}
              </dd>
              <dt className="field-label border-b border-rule py-3 first:border-t">Result</dt>
              <dd className="border-b border-rule py-3">
                {fingerprintMatches ? (
                  <StatusMark kind="verified" label="Fingerprints match" />
                ) : onChainBroker.isError ? (
                  <StatusMark kind="refused" label="Could not read the contract" />
                ) : identity.isError ? (
                  <StatusMark kind="refused" label="Broker unreachable" />
                ) : (
                  <StatusMark kind="pending" label="Not verified yet" />
                )}
              </dd>
            </dl>
          </div>
        </Step>

        <Step index="04" title="Vault passphrase" status={unlocked ? "done" : "active"}>
          <div className="space-y-3">
            <p className="text-body text-muted">
              The passphrase derives the key that wraps every item for you. It is held in
              memory for this tab only, never stored and never sent to the broker.
            </p>
            {unlocked ? (
              <div className="flex flex-wrap items-center gap-3">
                <StatusMark kind="verified" label="Vault unlocked" />
                <Button tone="quiet" onClick={lock}>
                  Lock the vault
                </Button>
              </div>
            ) : (
              <form
                className="flex flex-wrap items-end gap-3"
                onSubmit={(event) => {
                  event.preventDefault();
                  if (passphrase.length > 0) {
                    unlock(passphrase);
                    setPassphrase("");
                  }
                }}
              >
                <label className="flex flex-col gap-1">
                  <span className="field-label">Passphrase</span>
                  <input
                    type="password"
                    autoComplete="off"
                    value={passphrase}
                    onChange={(event) => {
                      setPassphrase(event.target.value);
                    }}
                    className="min-h-11 rounded-xl border border-rule bg-sunken px-3.5 text-body outline-none focus:border-accent"
                  />
                </label>
                <Button type="submit" disabled={passphrase.length === 0}>
                  Unlock
                </Button>
              </form>
            )}
          </div>
        </Step>
      </div>

    </div>
  );
}
