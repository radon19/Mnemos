/**
 * Mnemos envelope encryption, v1.
 *
 * Two wraps of the same per-item data key (DEK):
 *   - owner wrap: PBKDF2-HMAC-SHA256(passphrase, salt, 600000, 32) -> AES-256-GCM
 *   - broker wrap: X25519(ephemeral, broker public) -> HKDF-SHA256 -> AES-256-GCM
 *
 * Wire formats:
 *   item ciphertext        raw ciphertext || 16-byte tag, nonce stored separately
 *   owner-wrapped DEK      12-byte nonce || ciphertext || tag
 *   broker-wrapped DEK     32-byte ephemeral public || 12-byte nonce || ciphertext || tag
 *
 * All AAD strings and byte layouts are pinned by packages/crypto-vectors and
 * mirrored in apps/broker/src/mnemos_broker/crypto.py.
 */

import { gcm } from "@noble/ciphers/aes.js";
import { x25519 } from "@noble/curves/ed25519.js";
import { hkdf } from "@noble/hashes/hkdf.js";
import { pbkdf2 } from "@noble/hashes/pbkdf2.js";
import { sha256 } from "@noble/hashes/sha2.js";
import {
  bytesToHex,
  concatBytes,
  hexToBytes,
  randomBytes as nobleRandomBytes,
} from "@noble/hashes/utils.js";

export const PROTOCOL_VERSION = "mnemos:v1";
export const PBKDF2_ITERATIONS = 600_000;
export const OWNER_SALT_BYTES = 16;
export const DEK_BYTES = 32;
export const NONCE_BYTES = 12;
export const X25519_KEY_BYTES = 32;
export const MAX_ITEM_BYTES = 16 * 1024;
export const BROKER_WRAP_INFO = new TextEncoder().encode("mnemos:v1:wrap-broker");

const textEncoder = new TextEncoder();
const textDecoder = new TextDecoder("utf-8", { fatal: true });

export type CryptoErrorCode =
  | "E_INVALID_OWNER"
  | "E_INVALID_SCOPE"
  | "E_INVALID_ITEM_ID"
  | "E_INVALID_PASSPHRASE"
  | "E_INVALID_KEY"
  | "E_EMPTY_ITEM"
  | "E_ITEM_TOO_LARGE"
  | "E_DECRYPT_FAILED"
  | "E_CONTENT_HASH_MISMATCH"
  | "E_INVALID_ENVELOPE";

export class MnemosCryptoError extends Error {
  readonly code: CryptoErrorCode;

  constructor(code: CryptoErrorCode, message: string, options?: ErrorOptions) {
    super(message, options);
    this.name = "MnemosCryptoError";
    this.code = code;
  }
}

export interface ItemEnvelope {
  itemId: string;
  owner: string;
  scope: string;
  ciphertext: Uint8Array;
  nonce: Uint8Array;
  wrappedDekOwner: Uint8Array;
  wrappedDekBroker: Uint8Array;
  contentHash: string;
}

export interface ItemEnvelopeJson {
  item_id: string;
  owner: string;
  scope: string;
  ciphertext_b64: string;
  nonce_b64: string;
  wrapped_dek_owner_b64: string;
  wrapped_dek_broker_b64: string;
  content_hash: string;
}

export interface SealMaterials {
  dek?: Uint8Array;
  itemNonce?: Uint8Array;
  ownerWrapNonce?: Uint8Array;
  brokerEphemeralSecret?: Uint8Array;
  brokerWrapNonce?: Uint8Array;
}

export interface SealItemWithKekInput {
  owner: string;
  scope: string;
  itemId: string;
  plaintext: string | Uint8Array;
  kek: Uint8Array;
  brokerPublicKey: Uint8Array;
  materials?: SealMaterials;
}

export interface SealItemInput extends Omit<SealItemWithKekInput, "kek"> {
  passphrase: string;
  ownerSalt: Uint8Array;
}

export interface OpenItemWithKekInput {
  envelope: ItemEnvelope;
  kek: Uint8Array;
}

export interface OpenItemWithOwnerInput {
  envelope: ItemEnvelope;
  passphrase: string;
  ownerSalt: Uint8Array;
}

export interface OpenItemWithBrokerInput {
  envelope: ItemEnvelope;
  brokerPrivateKey: Uint8Array;
}

export function itemAad(owner: string, scope: string, itemId: string): Uint8Array {
  return textEncoder.encode(`${PROTOCOL_VERSION}|${owner}|${scope}|${itemId}`);
}

export function ownerWrapAad(itemId: string): Uint8Array {
  return textEncoder.encode(`${PROTOCOL_VERSION}:wrap-owner|${itemId}`);
}

export function brokerWrapAad(itemId: string): Uint8Array {
  return textEncoder.encode(`${PROTOCOL_VERSION}:wrap-broker|${itemId}`);
}

export function assertValidOwner(owner: string): void {
  if (!/^[a-z0-9][a-z0-9._-]{0,62}[a-z0-9]$/.test(owner)) {
    throw new MnemosCryptoError(
      "E_INVALID_OWNER",
      "owner must be a lowercase NEAR account id of 2 to 64 characters",
    );
  }
}

export function assertValidScope(scope: string): void {
  if (!/^[a-z0-9-]{1,32}$/.test(scope)) {
    throw new MnemosCryptoError(
      "E_INVALID_SCOPE",
      "scope must match [a-z0-9-]{1,32}",
    );
  }
}

export function assertValidItemId(itemId: string): void {
  if (
    !/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/.test(
      itemId,
    )
  ) {
    throw new MnemosCryptoError(
      "E_INVALID_ITEM_ID",
      "item id must be a lowercase UUID",
    );
  }
}

export function assertValidPassphrase(passphrase: string): void {
  if (passphrase.length === 0 || passphrase.length > 1024) {
    throw new MnemosCryptoError(
      "E_INVALID_PASSPHRASE",
      "passphrase must be 1 to 1024 characters",
    );
  }
}

export function assertKeyLength(
  name: string,
  key: Uint8Array,
  expected: number,
): void {
  if (key.length !== expected) {
    throw new MnemosCryptoError(
      "E_INVALID_KEY",
      `${name} must be ${expected} bytes, got ${key.length}`,
    );
  }
}

export function deriveOwnerKek(
  passphrase: string,
  ownerSalt: Uint8Array,
): Uint8Array {
  assertValidPassphrase(passphrase);
  assertKeyLength("owner salt", ownerSalt, OWNER_SALT_BYTES);
  return pbkdf2(sha256, textEncoder.encode(passphrase), ownerSalt, {
    c: PBKDF2_ITERATIONS,
    dkLen: DEK_BYTES,
  });
}

export function fingerprintBrokerKey(publicKey: Uint8Array): string {
  assertKeyLength("broker public key", publicKey, X25519_KEY_BYTES);
  return bytesToHex(sha256(publicKey));
}

/** Cryptographically secure random bytes, for nonces, salts and item ids. */
export function randomBytes(length: number): Uint8Array {
  if (!Number.isInteger(length) || length <= 0) {
    throw new MnemosCryptoError("E_INVALID_KEY", "length must be a positive integer");
  }
  return nobleRandomBytes(length);
}

export function sealItem(input: SealItemInput): ItemEnvelope {
  const kek = deriveOwnerKek(input.passphrase, input.ownerSalt);
  return sealItemWithKek({
    owner: input.owner,
    scope: input.scope,
    itemId: input.itemId,
    plaintext: input.plaintext,
    kek,
    brokerPublicKey: input.brokerPublicKey,
    ...(input.materials === undefined ? {} : { materials: input.materials }),
  });
}

export function sealItemWithKek(input: SealItemWithKekInput): ItemEnvelope {
  assertValidOwner(input.owner);
  assertValidScope(input.scope);
  assertValidItemId(input.itemId);
  assertKeyLength("owner KEK", input.kek, DEK_BYTES);
  assertKeyLength("broker public key", input.brokerPublicKey, X25519_KEY_BYTES);

  const plaintext =
    typeof input.plaintext === "string"
      ? textEncoder.encode(input.plaintext)
      : input.plaintext;
  if (plaintext.length === 0) {
    throw new MnemosCryptoError("E_EMPTY_ITEM", "item content must not be empty");
  }
  if (plaintext.length > MAX_ITEM_BYTES) {
    throw new MnemosCryptoError(
      "E_ITEM_TOO_LARGE",
      `item content must be at most ${MAX_ITEM_BYTES} bytes`,
    );
  }

  const materials = input.materials ?? {};
  const dek = materials.dek ?? randomBytes(DEK_BYTES);
  const itemNonce = materials.itemNonce ?? randomBytes(NONCE_BYTES);
  const ownerWrapNonce = materials.ownerWrapNonce ?? randomBytes(NONCE_BYTES);
  const brokerEphemeralSecret =
    materials.brokerEphemeralSecret ?? x25519.utils.randomSecretKey();
  const brokerWrapNonce = materials.brokerWrapNonce ?? randomBytes(NONCE_BYTES);

  assertKeyLength("item DEK", dek, DEK_BYTES);
  assertKeyLength("item nonce", itemNonce, NONCE_BYTES);
  assertKeyLength("owner wrap nonce", ownerWrapNonce, NONCE_BYTES);
  assertKeyLength(
    "broker ephemeral secret",
    brokerEphemeralSecret,
    X25519_KEY_BYTES,
  );
  assertKeyLength("broker wrap nonce", brokerWrapNonce, NONCE_BYTES);

  const ciphertext = gcm(
    dek,
    itemNonce,
    itemAad(input.owner, input.scope, input.itemId),
  ).encrypt(plaintext);

  const wrappedDekOwner = concatBytes(
    ownerWrapNonce,
    gcm(input.kek, ownerWrapNonce, ownerWrapAad(input.itemId)).encrypt(dek),
  );

  const brokerEphemeralPublic = x25519.getPublicKey(brokerEphemeralSecret);
  const shared = x25519.getSharedSecret(
    brokerEphemeralSecret,
    input.brokerPublicKey,
  );
  const brokerKek = hkdf(sha256, shared, undefined, BROKER_WRAP_INFO, DEK_BYTES);
  const wrappedDekBroker = concatBytes(
    brokerEphemeralPublic,
    brokerWrapNonce,
    gcm(brokerKek, brokerWrapNonce, brokerWrapAad(input.itemId)).encrypt(dek),
  );

  return {
    itemId: input.itemId,
    owner: input.owner,
    scope: input.scope,
    ciphertext,
    nonce: itemNonce,
    wrappedDekOwner,
    wrappedDekBroker,
    contentHash: bytesToHex(sha256(ciphertext)),
  };
}

export function openItemWithOwner(input: OpenItemWithOwnerInput): Uint8Array {
  const kek = deriveOwnerKek(input.passphrase, input.ownerSalt);
  return openItemWithKek({ envelope: input.envelope, kek });
}

export interface OwnerEnvelope {
  itemId: string;
  owner: string;
  scope: string;
  ciphertext: Uint8Array;
  nonce: Uint8Array;
  wrappedDekOwner: Uint8Array;
  contentHash: string;
}

/**
 * Open an item with the owner's passphrase.
 *
 * This is the path the browser uses to read the owner's own vault: the broker
 * never hands out the broker wrap, so the owner wrap is all that is needed.
 */
export function openOwnerItem(
  envelope: OwnerEnvelope,
  passphrase: string,
  ownerSalt: Uint8Array,
): Uint8Array {
  const kek = deriveOwnerKek(passphrase, ownerSalt);
  const dek = unwrapOwnerDek(
    {
      itemId: envelope.itemId,
      owner: envelope.owner,
      scope: envelope.scope,
      ciphertext: envelope.ciphertext,
      nonce: envelope.nonce,
      wrappedDekOwner: envelope.wrappedDekOwner,
      wrappedDekBroker: new Uint8Array(0),
      contentHash: envelope.contentHash,
    },
    kek,
  );
  return decryptItem(
    {
      itemId: envelope.itemId,
      owner: envelope.owner,
      scope: envelope.scope,
      ciphertext: envelope.ciphertext,
      nonce: envelope.nonce,
      wrappedDekOwner: envelope.wrappedDekOwner,
      wrappedDekBroker: new Uint8Array(0),
      contentHash: envelope.contentHash,
    },
    dek,
  );
}

export function openItemWithKek(input: OpenItemWithKekInput): Uint8Array {
  assertKeyLength("owner KEK", input.kek, DEK_BYTES);
  const { envelope } = input;
  const dek = unwrapOwnerDek(envelope, input.kek);
  return decryptItem(envelope, dek);
}

export function openItemWithBroker(
  input: OpenItemWithBrokerInput,
): Uint8Array {
  assertKeyLength(
    "broker private key",
    input.brokerPrivateKey,
    X25519_KEY_BYTES,
  );
  const dek = unwrapBrokerDek(input.envelope, input.brokerPrivateKey);
  return decryptItem(input.envelope, dek);
}

export function unwrapOwnerDek(
  envelope: ItemEnvelope,
  kek: Uint8Array,
): Uint8Array {
  assertEnvelope(envelope);
  if (envelope.wrappedDekOwner.length !== NONCE_BYTES + DEK_BYTES + 16) {
    throw new MnemosCryptoError(
      "E_INVALID_ENVELOPE",
      "owner-wrapped DEK has an unexpected length",
    );
  }
  const nonce = envelope.wrappedDekOwner.slice(0, NONCE_BYTES);
  const sealed = envelope.wrappedDekOwner.slice(NONCE_BYTES);
  try {
    return gcm(kek, nonce, ownerWrapAad(envelope.itemId)).decrypt(sealed);
  } catch (error) {
    throw new MnemosCryptoError(
      "E_DECRYPT_FAILED",
      "owner unwrap failed: wrong passphrase or tampered data",
      { cause: error },
    );
  }
}

export function unwrapBrokerDek(
  envelope: ItemEnvelope,
  brokerPrivateKey: Uint8Array,
): Uint8Array {
  assertEnvelope(envelope);
  if (
    envelope.wrappedDekBroker.length !==
    X25519_KEY_BYTES + NONCE_BYTES + DEK_BYTES + 16
  ) {
    throw new MnemosCryptoError(
      "E_INVALID_ENVELOPE",
      "broker-wrapped DEK has an unexpected length",
    );
  }
  const ephemeralPublic = envelope.wrappedDekBroker.slice(0, X25519_KEY_BYTES);
  const nonce = envelope.wrappedDekBroker.slice(
    X25519_KEY_BYTES,
    X25519_KEY_BYTES + NONCE_BYTES,
  );
  const sealed = envelope.wrappedDekBroker.slice(
    X25519_KEY_BYTES + NONCE_BYTES,
  );
  try {
    const shared = x25519.getSharedSecret(brokerPrivateKey, ephemeralPublic);
    const brokerKek = hkdf(
      sha256,
      shared,
      undefined,
      BROKER_WRAP_INFO,
      DEK_BYTES,
    );
    return gcm(brokerKek, nonce, brokerWrapAad(envelope.itemId)).decrypt(sealed);
  } catch (error) {
    throw new MnemosCryptoError(
      "E_DECRYPT_FAILED",
      "broker unwrap failed: wrong key or tampered data",
      { cause: error },
    );
  }
}

export function decryptItem(
  envelope: ItemEnvelope,
  dek: Uint8Array,
): Uint8Array {
  assertEnvelope(envelope);
  assertKeyLength("item DEK", dek, DEK_BYTES);
  if (envelope.nonce.length !== NONCE_BYTES) {
    throw new MnemosCryptoError(
      "E_INVALID_ENVELOPE",
      "item nonce has an unexpected length",
    );
  }
  try {
    const plaintext = gcm(
      dek,
      envelope.nonce,
      itemAad(envelope.owner, envelope.scope, envelope.itemId),
    ).decrypt(envelope.ciphertext);
    verifyContentHash(envelope);
    return plaintext;
  } catch (error) {
    if (error instanceof MnemosCryptoError) {
      throw error;
    }
    throw new MnemosCryptoError(
      "E_DECRYPT_FAILED",
      "item decryption failed: wrong scope, owner, item id, or tampered data",
      { cause: error },
    );
  }
}

export function verifyContentHash(envelope: ItemEnvelope): void {
  const actual = bytesToHex(sha256(envelope.ciphertext));
  if (actual !== envelope.contentHash) {
    throw new MnemosCryptoError(
      "E_CONTENT_HASH_MISMATCH",
      "content hash does not match the ciphertext",
    );
  }
}

export function assertEnvelope(envelope: ItemEnvelope): void {
  assertValidOwner(envelope.owner);
  assertValidScope(envelope.scope);
  assertValidItemId(envelope.itemId);
  if (!/^[0-9a-f]{64}$/.test(envelope.contentHash)) {
    throw new MnemosCryptoError(
      "E_INVALID_ENVELOPE",
      "content hash must be 64 lowercase hex characters",
    );
  }
  if (envelope.ciphertext.length < 16) {
    throw new MnemosCryptoError(
      "E_INVALID_ENVELOPE",
      "ciphertext is too short to contain a GCM tag",
    );
  }
}

export function envelopeToJson(envelope: ItemEnvelope): ItemEnvelopeJson {
  return {
    item_id: envelope.itemId,
    owner: envelope.owner,
    scope: envelope.scope,
    ciphertext_b64: bytesToBase64(envelope.ciphertext),
    nonce_b64: bytesToBase64(envelope.nonce),
    wrapped_dek_owner_b64: bytesToBase64(envelope.wrappedDekOwner),
    wrapped_dek_broker_b64: bytesToBase64(envelope.wrappedDekBroker),
    content_hash: envelope.contentHash,
  };
}

export function envelopeFromJson(json: ItemEnvelopeJson): ItemEnvelope {
  return {
    itemId: json.item_id,
    owner: json.owner,
    scope: json.scope,
    ciphertext: base64ToBytes(json.ciphertext_b64),
    nonce: base64ToBytes(json.nonce_b64),
    wrappedDekOwner: base64ToBytes(json.wrapped_dek_owner_b64),
    wrappedDekBroker: base64ToBytes(json.wrapped_dek_broker_b64),
    contentHash: json.content_hash,
  };
}

export function decodePlaintext(plaintext: Uint8Array): string {
  try {
    return textDecoder.decode(plaintext);
  } catch (error) {
    throw new MnemosCryptoError(
      "E_DECRYPT_FAILED",
      "decrypted item is not valid UTF-8",
      { cause: error },
    );
  }
}

const BASE64_ALPHABET =
  "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/";

export function bytesToBase64(bytes: Uint8Array): string {
  let output = "";
  for (let index = 0; index < bytes.length; index += 3) {
    const first = bytes[index] ?? 0;
    const second = bytes[index + 1];
    const third = bytes[index + 2];
    const triple = (first << 16) | ((second ?? 0) << 8) | (third ?? 0);
    output += BASE64_ALPHABET.charAt((triple >> 18) & 63);
    output += BASE64_ALPHABET.charAt((triple >> 12) & 63);
    output +=
      second === undefined
        ? "="
        : BASE64_ALPHABET.charAt((triple >> 6) & 63);
    output += third === undefined ? "=" : BASE64_ALPHABET.charAt(triple & 63);
  }
  return output;
}

export function base64ToBytes(value: string): Uint8Array {
  if (!/^[A-Za-z0-9+/]*={0,2}$/.test(value) || value.length % 4 !== 0) {
    throw new MnemosCryptoError(
      "E_INVALID_ENVELOPE",
      "value is not valid base64",
    );
  }
  const padding = value.endsWith("==") ? 2 : value.endsWith("=") ? 1 : 0;
  const bytes = new Uint8Array((value.length / 4) * 3 - padding);
  let position = 0;
  for (let index = 0; index < value.length; index += 4) {
    const chunk = value.slice(index, index + 4);
    const decoded = [0, 1, 2, 3].map((offset) => {
      const char = chunk[offset];
      if (char === undefined || char === "=") {
        return 0;
      }
      const positionInAlphabet = BASE64_ALPHABET.indexOf(char);
      if (positionInAlphabet === -1) {
        throw new MnemosCryptoError(
          "E_INVALID_ENVELOPE",
          "value is not valid base64",
        );
      }
      return positionInAlphabet;
    });
    const triple =
      ((decoded[0] ?? 0) << 18) |
      ((decoded[1] ?? 0) << 12) |
      ((decoded[2] ?? 0) << 6) |
      (decoded[3] ?? 0);
    if (position < bytes.length) bytes[position++] = (triple >> 16) & 255;
    if (position < bytes.length) bytes[position++] = (triple >> 8) & 255;
    if (position < bytes.length) bytes[position++] = triple & 255;
  }
  return bytes;
}

export function hexToUint8Array(value: string): Uint8Array {
  return hexToBytes(value);
}

export function uint8ArrayToHex(value: Uint8Array): string {
  return bytesToHex(value);
}
