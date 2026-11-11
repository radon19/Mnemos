/**
 * Client-side vault encryption.
 *
 * The plaintext never leaves the device: the item is sealed here with the
 * owner's passphrase-derived key and a broker wrap for the broker's X25519
 * public key. The broker can open only what was wrapped for it, and only
 * inside the scope a paid grant allows.
 */

import {
  base64ToBytes,
  bytesToBase64,
  deriveOwnerKek,
  envelopeToJson,
  randomBytes,
  sealItemWithKek,
} from "@mnemos/crypto";

import type { VaultItemInput } from "./broker";

const SALT_STORAGE_KEY = "mnemos.owner-salt";
export const OWNER_SALT_BYTES = 16;
export const MAX_ITEM_CHARS = 16 * 1024;

export function createOwnerSalt(): Uint8Array {
  return randomBytes(OWNER_SALT_BYTES);
}

export function readStoredSalt(): string | null {
  if (typeof window === "undefined") {
    return null;
  }
  return window.localStorage.getItem(SALT_STORAGE_KEY);
}

export function storeSalt(salt: Uint8Array): void {
  if (typeof window === "undefined") {
    return;
  }
  window.localStorage.setItem(SALT_STORAGE_KEY, bytesToBase64(salt));
}

export function ownerSaltFromBase64(value: string): Uint8Array {
  const bytes = base64ToBytes(value);
  if (bytes.length !== OWNER_SALT_BYTES) {
    throw new Error("the owner salt has an unexpected length");
  }
  return bytes;
}

export interface SealInput {
  owner: string;
  scope: string;
  itemId: string;
  plaintext: string;
  passphrase: string;
  ownerSalt: Uint8Array;
  brokerPublicKey: Uint8Array;
}

export function sealVaultItem(input: SealInput): VaultItemInput {
  const kek = deriveOwnerKek(input.passphrase, input.ownerSalt);
  const envelope = sealItemWithKek({
    owner: input.owner,
    scope: input.scope,
    itemId: input.itemId,
    plaintext: input.plaintext,
    kek,
    brokerPublicKey: input.brokerPublicKey,
  });
  const json = envelopeToJson(envelope);
  return {
    id: json.item_id,
    scope: json.scope,
    ciphertext_b64: json.ciphertext_b64,
    nonce_b64: json.nonce_b64,
    wrapped_dek_owner_b64: json.wrapped_dek_owner_b64,
    wrapped_dek_broker_b64: json.wrapped_dek_broker_b64,
    content_hash: json.content_hash,
    owner_salt_b64: bytesToBase64(input.ownerSalt),
  };
}

export function randomItemId(): string {
  const bytes = randomBytes(16);
  const hex = Array.from(bytes, (byte: number) => byte.toString(16).padStart(2, "0")).join("");
  return `${hex.slice(0, 8)}-${hex.slice(8, 12)}-${hex.slice(12, 16)}-${hex.slice(
    16,
    20,
  )}-${hex.slice(20, 32)}`;
}
