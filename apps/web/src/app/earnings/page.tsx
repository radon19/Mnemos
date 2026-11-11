"use client";

import { useMutation, useQuery } from "@tanstack/react-query";
import { useState } from "react";

import { Button } from "@/components/Button";
import { EmptyState } from "@/components/EmptyState";
import { Hash } from "@/components/Hash";
import { Notice } from "@/components/Notice";
import { PageHeader } from "@/components/PageHeader";
import { StatusMark } from "@/components/StatusMark";
import { nearToYocto } from "@/lib/amount";
import { formatNear, formatTimestamp, truncateAccount } from "@/lib/format";
import { callView, connectWallet, sendContractCall, walletAccounts, type ReceiptView } from "@/lib/near";
import { describeError, useSession } from "@/lib/session";

export default function EarningsPage(): React.ReactNode {
  const { status, account } = useSession();
  const [amount, setAmount] = useState("");
  const [notice, setNotice] = useState<{ tone: "success" | "error"; text: string } | null>(null);

  const earnings = useQuery({
    queryKey: ["earnings", account],
    enabled: status === "signed-in" && account !== null,
    queryFn: async () => await callView<string>("earnings_of", { owner: account ?? "" }),
    retry: false,
  });

  const receipts = useQuery({
    queryKey: ["earnings-receipts", account],
    enabled: status === "signed-in" && account !== null,
    queryFn: async () => await callView<ReceiptView[]>("recent_receipts", {
      owner: account ?? "",
      from: 0,
      limit: 50,
    }),
    retry: false,
  });

  const withdraw = useMutation({
    mutationFn: async () => {
      const wallet = await connectWallet();
      const accounts = await walletAccounts(wallet);
      const signer = accounts[0];
      if (signer === undefined) {
        throw new Error("connect the owner wallet first");
      }
      const yocto = nearToYocto(amount);
      if (yocto === null) {
        throw new Error("enter an amount of NEAR to withdraw");
      }
      return await sendContractCall(wallet, {
        method: "withdraw_earnings",
        args: { amount: yocto },
        signerId: signer,
      });
    },
    onSuccess: async () => {
      setNotice({
        tone: "success",
        text: "Withdrawal submitted. The contract sends the NEAR to the owner account.",
      });
      setAmount("");
      await earnings.refetch();
    },
    onError: (error: unknown) => {
      setNotice({ tone: "error", text: describeError(error) });
    },
  });

  const balance = earnings.data ?? "0";

  return (
    <div className="space-y-10 pb-16">
      <PageHeader
        title="What the reads paid"
        lede="Every served read moves the price from the agent to the owner. The contract holds the balance until it is withdrawn."
      />

      {notice === null ? null : (
        <Notice tone={notice.tone} title={notice.tone === "success" ? "Done" : "The withdrawal failed"}>
          {notice.text}
        </Notice>
      )}

      <div className="grid gap-10 lg:grid-cols-[minmax(0,24rem)_minmax(0,1fr)]">
        <section aria-labelledby="balance" className="card space-y-6 px-5 py-5">
          <div>
            <h2 id="balance" className="field-label">
              Unwithdrawn balance
            </h2>
            <p className="numeric mt-2 text-display text-ink">{formatNear(balance)} NEAR</p>
            <p className="mt-1 text-caption text-muted">
              Read from the contract. It moves only when a read is served.
            </p>
          </div>

          <form
            className="space-y-3 border-t border-rule pt-6"
            onSubmit={(event) => {
              event.preventDefault();
              withdraw.mutate();
            }}
          >
            <label className="flex flex-col gap-1">
              <span className="field-label">Withdraw amount (NEAR)</span>
              <input
                value={amount}
                onChange={(event) => {
                  setAmount(event.target.value);
                }}
                placeholder="0.1"
                className="min-h-11 rounded-xl border border-rule bg-sunken px-3.5 text-body outline-none focus:border-accent"
              />
            </label>
            <Button
              type="submit"
              tone="quiet"
              disabled={status !== "signed-in" || withdraw.isPending || amount.trim() === ""}
            >
              {withdraw.isPending ? "Waiting for the wallet…" : "Withdraw"}
            </Button>
            <p className="text-caption text-muted">
              The withdrawal is a transaction from the owner account. It cannot be sent
              by the broker.
            </p>
          </form>
        </section>

        <section aria-labelledby="history" className="card min-w-0 px-5 py-5">
          <h2 id="history" className="text-title">
            Recent receipts
          </h2>
          {receipts.isError ? (
            <Notice tone="error" title="The receipt ring could not be read">
              {describeError(receipts.error)}
            </Notice>
          ) : null}
          {receipts.data?.length === 0 ? (
            <EmptyState
              title="No receipts yet"
              body="When an agent reads inside a granted scope, the receipt is written to the contract and listed here."
            />
          ) : null}
          {receipts.data !== undefined && receipts.data !== null && receipts.data.length > 0 ? (
            <div className="mt-2 overflow-hidden">
              <table className="w-full text-left">
                <caption className="sr-only">Recent receipts on chain</caption>
                <thead>
                  <tr>
                    <th scope="col" className="field-label border-b border-rule py-3">
                      Read
                    </th>
                    <th scope="col" className="field-label border-b border-rule py-3">
                      Agent
                    </th>
                    <th scope="col" className="field-label border-b border-rule py-3">
                      Scope
                    </th>
                    <th scope="col" className="field-label border-b border-rule py-3">
                      Paid
                    </th>
                    <th scope="col" className="field-label border-b border-rule py-3">
                      Receipt hash
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {receipts.data.map((receipt) => (
                    <tr key={receipt.req_id} className="align-top">
                      <td className="border-b border-rule px-4 py-3">
                        <span className="numeric text-caption">#{receipt.req_id}</span>
                        <p className="numeric text-caption text-muted">
                          {formatTimestamp(Number(BigInt(receipt.served_ns) / 1_000_000n))}
                        </p>
                      </td>
                      <td className="border-b border-rule px-4 py-3">
                        <span className="hash text-caption break-all">
                          {truncateAccount(receipt.agent, 8, 4)}
                        </span>
                      </td>
                      <td className="border-b border-rule px-4 py-3">
                        <span className="hash text-caption">{receipt.scope}</span>
                      </td>
                      <td className="border-b border-rule px-4 py-3">
                        <span className="numeric text-caption">
                          {formatNear(receipt.price)} NEAR
                        </span>
                      </td>
                      <td className="border-b border-rule py-3">
                        <Hash value={receipt.receipt_hash} label="Receipt hash" />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : null}

          <div className="mt-8 flex items-center gap-3 border-t border-rule pt-4">
            <StatusMark kind="verified" label="Hash only" />
            <p className="max-w-[54ch] text-caption text-muted">
              The chain stores the hash of the request and answer. It cannot reveal the
              note to anybody, including the owner.
            </p>
          </div>
        </section>
      </div>
    </div>
  );
}
