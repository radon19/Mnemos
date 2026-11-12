"use client";

import { useQuery } from "@tanstack/react-query";

import { brokerApi } from "./broker";
import { callView, type BrokerInfo, type ContractConfig } from "./near";

export type BrokerTrustState = "checking" | "trusted" | "mismatch" | "unverified";

export interface BrokerTrust {
  state: BrokerTrustState;
  servedFingerprint: string | null;
  registeredFingerprint: string | null;
  /** Why the browser refuses to encrypt, when it does. */
  reason: string | null;
}

/**
 * The broker's key has to be the one registered on chain.
 *
 * The brief requires the browser to check this before it encrypts anything,
 * because a note sealed for the wrong broker can never be read back. When the
 * two fingerprints differ, or when the chain cannot be read to check, the
 * browser refuses to encrypt and says why.
 */
export function useBrokerTrust(enabled: boolean): BrokerTrust {
  const identity = useQuery({
    queryKey: ["broker-identity"],
    queryFn: async () => brokerApi.identity(),
    retry: false,
    enabled,
  });

  const config = useQuery({
    queryKey: ["contract-config"],
    queryFn: async () => await callView<ContractConfig>("get_config", {}),
    retry: false,
    enabled,
  });

  const owner = config.data?.owner;

  const registered = useQuery({
    queryKey: ["broker-on-chain", owner],
    enabled: enabled && owner !== undefined,
    queryFn: async () => await callView<BrokerInfo>("get_broker", { owner: owner ?? "" }),
    retry: false,
  });

  const servedFingerprint = identity.data?.fingerprint ?? null;
  const registeredFingerprint = registered.data?.broker_pubkey_fingerprint ?? null;

  if (identity.isError) {
    return {
      state: "unverified",
      servedFingerprint,
      registeredFingerprint,
      reason:
        "the broker's public key could not be read, so nothing can be encrypted for it",
    };
  }
  if (registered.isError) {
    return {
      state: "unverified",
      servedFingerprint,
      registeredFingerprint,
      reason:
        "the key registered on chain could not be read, so the broker cannot be checked",
    };
  }
  if (
    servedFingerprint !== null &&
    registeredFingerprint !== null &&
    servedFingerprint !== registeredFingerprint
  ) {
    return {
      state: "mismatch",
      servedFingerprint,
      registeredFingerprint,
      reason:
        "the broker is serving a different key from the one registered on chain; " +
        "encrypting for it would make the note unreadable, so nothing is encrypted",
    };
  }
  if (servedFingerprint === null || registeredFingerprint === null) {
    return {
      state: "checking",
      servedFingerprint,
      registeredFingerprint,
      reason: null,
    };
  }
  return {
    state: "trusted",
    servedFingerprint,
    registeredFingerprint,
    reason: null,
  };
}
