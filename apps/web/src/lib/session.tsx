"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from "react";

import { BrokerError, brokerApi } from "./broker";
import { connectWallet, signLoginMessage, walletAccounts } from "./near";

export type SessionStatus = "unknown" | "signed-out" | "signed-in";

export interface SessionContextValue {
  status: SessionStatus;
  account: string | null;
  demo: boolean;
  unlocked: boolean;
  error: string | null;
  signIn: () => Promise<void>;
  signInDemo: () => Promise<void>;
  signOut: () => Promise<void>;
  unlock: (passphrase: string) => void;
  lock: () => void;
  passphrase: () => string | null;
  clearError: () => void;
}

const SessionContext = createContext<SessionContextValue | null>(null);

export function SessionProvider({ children }: { children: React.ReactNode }): React.ReactNode {
  const [status, setStatus] = useState<SessionStatus>("unknown");
  const [account, setAccount] = useState<string | null>(null);
  const [demo, setDemo] = useState(false);
  const [unlocked, setUnlocked] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const passphraseRef = useRef<string | null>(null);

  useEffect(() => {
    // A hydration marker, so an automated client can wait until the app
    // answers clicks instead of guessing.
    document.body.dataset.hydrated = "true";
    const cancelled = { current: false };
    void (async () => {
      try {
        const session = await brokerApi.optionalSession();
        if (cancelled.current) {
          return;
        }
        if (session.authenticated && session.account !== null) {
          setAccount(session.account);
          setDemo(false);
          setStatus("signed-in");
        } else {
          setStatus("signed-out");
        }
      } catch {
        if (!cancelled.current) {
          setStatus("signed-out");
        }
      }
    })();
    return () => {
      cancelled.current = true;
    };
  }, []);

  const signIn = useCallback(async () => {
    setError(null);
    try {
      const wallet = await connectWallet();
      const accounts = await walletAccounts(wallet);
      const owner = accounts[0];
      if (owner === undefined) {
        throw new Error("the wallet returned no account");
      }
      const challenge = await brokerApi.challenge(owner);
      const signed = await signLoginMessage(wallet, {
        message: challenge.message,
        recipient: challenge.recipient,
        nonce: Uint8Array.from(
          challenge.nonce_hex.match(/../gu)?.map((byte) => Number.parseInt(byte, 16)) ?? [],
        ),
      });
      const session = await brokerApi.verify({
        account: owner,
        nonce_hex: challenge.nonce_hex,
        public_key: signed.publicKey,
        signature_b64: signed.signatureB64,
      });
      setAccount(session.account);
      setDemo(false);
      setStatus("signed-in");
    } catch (cause) {
      setError(describeError(cause));
      setStatus("signed-out");
    }
  }, []);

  const signInDemo = useCallback(async () => {
    setError(null);
    try {
      const response = await fetch("/api/auth/demo", { method: "POST" });
      const payload = (await response.json()) as { account?: string; error?: string };
      if (!response.ok || payload.account === undefined) {
        throw new Error(payload.error ?? "the demo signer is not available");
      }
      setAccount(payload.account);
      setDemo(true);
      setStatus("signed-in");
    } catch (cause) {
      setError(describeError(cause));
      setStatus("signed-out");
    }
  }, []);

  const signOut = useCallback(async () => {
    try {
      await brokerApi.logout();
    } catch {
      // The cookie is cleared either way; the local state is what matters.
    }
    passphraseRef.current = null;
    setUnlocked(false);
    setAccount(null);
    setDemo(false);
    setStatus("signed-out");
  }, []);

  const unlock = useCallback((passphrase: string) => {
    passphraseRef.current = passphrase;
    setUnlocked(true);
  }, []);

  const lock = useCallback(() => {
    passphraseRef.current = null;
    setUnlocked(false);
  }, []);

  const value = useMemo<SessionContextValue>(
    () => ({
      status,
      account,
      demo,
      unlocked,
      error,
      signIn,
      signInDemo,
      signOut,
      unlock,
      lock,
      passphrase: () => passphraseRef.current,
      clearError: () => {
        setError(null);
      },
    }),
    [status, account, demo, unlocked, error, signIn, signInDemo, signOut, unlock, lock],
  );

  return <SessionContext.Provider value={value}>{children}</SessionContext.Provider>;
}

export function useSession(): SessionContextValue {
  const value = useContext(SessionContext);
  if (value === null) {
    throw new Error("useSession must be used inside a SessionProvider");
  }
  return value;
}

export function describeError(cause: unknown): string {
  if (cause instanceof BrokerError) {
    return `${cause.code}: ${cause.message}`;
  }
  if (cause instanceof Error) {
    return cause.message;
  }
  return String(cause);
}
