"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { base64ToBytes } from "@mnemos/crypto";
import { useState } from "react";

import { Button } from "@/components/Button";
import { EmptyState } from "@/components/EmptyState";
import { Hash } from "@/components/Hash";
import { Notice } from "@/components/Notice";
import { PageHeader } from "@/components/PageHeader";
import { BrokerError, brokerApi } from "@/lib/broker";
import { formatTimestamp } from "@/lib/format";
import { describeError, useSession } from "@/lib/session";
import {
  MAX_ITEM_CHARS,
  createOwnerSalt,
  ownerSaltFromBase64,
  randomItemId,
  readStoredSalt,
  sealVaultItem,
  storeSalt,
} from "@/lib/vault";

const SCOPES = ["travel", "health", "work", "preferences"];

export default function VaultPage(): React.ReactNode {
  const queryClient = useQueryClient();
  const { status, account, unlocked, passphrase, unlock } = useSession();
  const [scope, setScope] = useState(SCOPES[0] ?? "travel");
  const [text, setText] = useState("");
  const [passphraseInput, setPassphraseInput] = useState("");
  const [message, setMessage] = useState<string | null>(null);
  const [failure, setFailure] = useState<string | null>(null);

  const identity = useQuery({
    queryKey: ["broker-identity"],
    queryFn: async () => brokerApi.identity(),
    retry: false,
  });

  const items = useQuery({
    queryKey: ["vault", scope],
    queryFn: async () => brokerApi.vaultItems({ scope, limit: 50 }),
    retry: false,
    enabled: status === "signed-in",
  });

  const addItem = useMutation({
    mutationFn: async () => {
      const secret = passphrase();
      if (secret === null) {
        throw new Error("unlock the vault before adding a note");
      }
      if (account === null) {
        throw new Error("sign in before adding a note");
      }
      const brokerKey = base64ToBytes(identity.data?.public_key_b64 ?? "");
      const salt = await resolveSalt();
      const payload = sealVaultItem({
        owner: account,
        scope,
        itemId: randomItemId(),
        plaintext: text,
        passphrase: secret,
        ownerSalt: salt,
        brokerPublicKey: brokerKey,
      });
      return await brokerApi.createVaultItem(payload);
    },
    onSuccess: async () => {
      setText("");
      setMessage("Note encrypted on this device and stored.");
      setFailure(null);
      await queryClient.invalidateQueries({ queryKey: ["vault"] });
    },
    onError: (error: unknown) => {
      setFailure(describeError(error));
      setMessage(null);
    },
  });

  const removeItem = useMutation({
    mutationFn: async (id: string) => {
      await brokerApi.deleteVaultItem(id);
    },
    onSuccess: async () => {
      setMessage("Note deleted.");
      setFailure(null);
      await queryClient.invalidateQueries({ queryKey: ["vault"] });
    },
    onError: (error: unknown) => {
      setFailure(describeError(error));
      setMessage(null);
    },
  });

  const remaining = MAX_ITEM_CHARS - text.length;
  const tooLong = remaining < 0;
  const canAdd = unlocked && text.trim().length > 0 && !tooLong && account !== null;

  const signedOut = status !== "signed-in";

  return (
    <div className="space-y-10 pb-16">
      <PageHeader
        title="Notes, encrypted before they move"
        lede="Every note is sealed in the browser with a key derived from your passphrase. The broker stores ciphertext it can open only inside a scope a paid grant allows."
      />

      {signedOut ? (
        <Notice tone="info" title="Sign in to work on the vault">
          The vault belongs to an account, so the browser needs the session cookie the
          broker issued after the NEP-413 sign-in.
        </Notice>
      ) : null}

      <div className="grid gap-10 lg:grid-cols-[minmax(0,26rem)_minmax(0,1fr)]">
        <section aria-labelledby="add-note" className="card space-y-4 px-5 py-5">
          <h2 id="add-note" className="text-title">
            Add a note
          </h2>

          {unlocked ? null : (
            <form
              className="space-y-3 rounded-2xl bg-sunken p-4"
              onSubmit={(event) => {
                event.preventDefault();
                if (passphraseInput.length > 0) {
                  unlock(passphraseInput);
                  setPassphraseInput("");
                }
              }}
            >
              <p className="text-caption text-muted">
                The vault is locked. Enter the passphrase to derive the key that wraps a
                new note for you.
              </p>
              <label className="flex flex-col gap-1">
                <span className="field-label">Passphrase</span>
                <input
                  type="password"
                  autoComplete="off"
                  value={passphraseInput}
                  onChange={(event) => {
                    setPassphraseInput(event.target.value);
                  }}
                  className="min-h-11 rounded-xl border border-rule bg-sunken px-3.5 text-body outline-none focus:border-accent"
                />
              </label>
              <Button type="submit" tone="quiet" disabled={passphraseInput.length === 0}>
                Unlock the vault
              </Button>
            </form>
          )}

          <form
            className="space-y-4"
            onSubmit={(event) => {
              event.preventDefault();
              addItem.mutate();
            }}
          >
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

            <label className="flex flex-col gap-1">
              <span className="field-label">Note</span>
              <textarea
                value={text}
                rows={6}
                onChange={(event) => {
                  setText(event.target.value);
                }}
                placeholder="My flight to Lisbon is on 14 March at 09:15."
                className="rounded-xl border border-rule bg-sunken p-3.5 text-body outline-none focus:border-accent"
              />
            </label>

            <p
              className={`numeric text-caption ${tooLong ? "text-destructive" : "text-muted"}`}
              aria-live="polite"
            >
              {text.length} / {MAX_ITEM_CHARS} characters
              {tooLong ? " — over the limit" : ""}
            </p>

            <Button type="submit" disabled={!canAdd || addItem.isPending}>
              {addItem.isPending ? "Encrypting…" : "Encrypt and store"}
            </Button>
            {signedOut ? (
              <p className="text-caption text-muted">Sign in to store a note.</p>
            ) : null}
          </form>

          {message === null ? null : (
            <Notice tone="success" title="Stored">
              {message}
            </Notice>
          )}
          {failure === null ? null : (
            <Notice tone="error" title="The note was not stored">
              {failure}
            </Notice>
          )}
        </section>

        <section aria-labelledby="notes" className="card min-w-0 px-5 py-5">
          <div className="flex flex-wrap items-baseline justify-between gap-3">
            <h2 id="notes" className="text-title">
              Notes in {scope}
            </h2>
            <p className="field-label">
              {items.data === undefined ? "reading…" : `${items.data.items.length} stored`}
            </p>
          </div>

          {items.isError ? (
            <Notice tone="error" title="The vault could not be read">
              {items.error instanceof BrokerError
                ? `${items.error.code}: ${items.error.message}`
                : describeError(items.error)}
            </Notice>
          ) : null}

          {items.data?.items.length === 0 ? (
            <EmptyState
              title="No notes in this scope"
              body="Add the first note on the left. It is encrypted in this browser before it is sent."
            />
          ) : null}

          {items.data !== undefined && items.data.items.length > 0 ? (
            <div className="mt-2 overflow-hidden">
              <table className="w-full text-left">
                <caption className="sr-only">Encrypted notes in the {scope} scope</caption>
                <thead>
                  <tr>
                    <th scope="col" className="field-label border-b border-rule py-3">
                      Item
                    </th>
                    <th scope="col" className="field-label border-b border-rule py-3">
                      Content hash
                    </th>
                    <th scope="col" className="field-label border-b border-rule py-3">
                      Stored
                    </th>
                    <th scope="col" className="field-label border-b border-rule py-3">
                      <span className="sr-only">Actions</span>
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {items.data.items.map((item) => (
                    <tr key={item.id} className="align-top">
                      <td className="border-b border-rule px-4 py-3">
                        <span className="hash text-caption break-all">{item.id}</span>
                      </td>
                      <td className="border-b border-rule px-4 py-3">
                        <Hash value={item.content_hash} label="Content hash" />
                      </td>
                      <td className="border-b border-rule px-4 py-3">
                        <span className="numeric text-caption text-muted">
                          {formatTimestamp(item.created_at)}
                        </span>
                      </td>
                      <td className="border-b border-rule py-3 text-right">
                        <button
                          type="button"
                          className="field-label text-destructive underline decoration-rule underline-offset-4 hover:text-destructive"
                          onClick={() => {
                            removeItem.mutate(item.id);
                          }}
                        >
                          Delete
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : null}

          <p className="mt-6 max-w-[56ch] text-caption text-muted">
            The broker never receives the note in the clear. It receives ciphertext, a
            nonce, two wrapped keys and a hash it can check without decrypting.
          </p>
        </section>
      </div>
    </div>
  );
}

async function resolveSalt(): Promise<Uint8Array> {
  try {
    const stored = await brokerApi.vaultSalt();
    const salt = ownerSaltFromBase64(stored.owner_salt_b64);
    storeSalt(salt);
    return salt;
  } catch (error) {
    if (!(error instanceof BrokerError) || error.status !== 404) {
      throw error;
    }
    const local = readStoredSalt();
    if (local !== null) {
      const salt = ownerSaltFromBase64(local);
      storeSalt(salt);
      return salt;
    }
    const salt = createOwnerSalt();
    storeSalt(salt);
    return salt;
  }
}

export { resolveSalt };
