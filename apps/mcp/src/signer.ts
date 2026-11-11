/**
 * Agent signing for the broker's `/v1/ask` endpoint.
 *
 * The broker verifies an Ed25519 signature over SHA-256 of a canonical message
 * (decision D-010 in docs/DECISIONS.md):
 *
 *     mnemos:v1:ask|{req_id}|{sha256(question)}|{nonce_hex}|{recipient}
 *
 * The same nonce bytes are hashed into `q_hash`, which is what the contract
 * stores, so the question and the on-chain request cannot be swapped.
 */

import { KeyPair, type KeyPairString } from "near-api-js";
import { sha256 } from "@noble/hashes/sha2.js";
import { bytesToHex, hexToBytes, randomBytes } from "@noble/hashes/utils.js";

export const ASK_MESSAGE_PREFIX = "mnemos:v1:ask";
export const NONCE_BYTES = 32;

const encoder = new TextEncoder();

export function questionDigest(question: string): string {
  return bytesToHex(sha256(encoder.encode(question)));
}

export function questionHash(question: string, nonceHex: string): string {
  const nonce = hexToBytes(nonceHex);
  if (nonce.length !== NONCE_BYTES) {
    throw new Error("nonce must be 32 bytes");
  }
  const body = encoder.encode(question);
  const combined = new Uint8Array(body.length + nonce.length);
  combined.set(body, 0);
  combined.set(nonce, body.length);
  return bytesToHex(sha256(combined));
}

export function buildAskMessage(
  reqId: number,
  question: string,
  nonceHex: string,
  recipient: string,
): string {
  return [
    ASK_MESSAGE_PREFIX,
    String(reqId),
    questionDigest(question),
    nonceHex,
    recipient,
  ].join("|");
}

export function newNonceHex(): string {
  return bytesToHex(randomBytes(NONCE_BYTES));
}

export class AgentSigner {
  private readonly keyPair: KeyPair;

  constructor(secretKey: string) {
    this.keyPair = KeyPair.fromString(secretKey as KeyPairString);
  }

  get publicKey(): string {
    return this.keyPair.getPublicKey().toString();
  }

  /** Ed25519 over SHA-256 of the UTF-8 message, base64 encoded. */
  sign(message: string): string {
    const digest = sha256(encoder.encode(message));
    const signature = this.keyPair.sign(digest);
    return Buffer.from(signature.signature).toString("base64");
  }
}
