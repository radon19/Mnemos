import { describe, expect, it } from "vitest";
import { ed25519 } from "@noble/curves/ed25519.js";
import { sha256 } from "@noble/hashes/sha2.js";
import { hexToBytes } from "@noble/hashes/utils.js";

import {
  AgentSigner,
  buildAskMessage,
  newNonceHex,
  questionDigest,
  questionHash,
} from "../src/signer.js";

// The same question and nonce are pinned in the Python broker test suite
// (apps/broker/tests/test_security.py), so a change to either implementation
// breaks a test on both sides.
const QUESTION = "When is my flight?";
const NONCE = "11".repeat(32);
const SECRET_KEY = "ed25519:6Ef6Uap1S82NDKQ35YtjwzKKoPjJ8QDQBEz6JWXUZE3m";

const BASE58_ALPHABET =
  "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz";

function decodeBase58(value: string): Uint8Array {
  let number = 0n;
  for (const character of value) {
    const index = BASE58_ALPHABET.indexOf(character);
    if (index < 0) {
      throw new Error(`invalid base58 character ${character}`);
    }
    number = number * 58n + BigInt(index);
  }
  const bytes: number[] = [];
  while (number > 0n) {
    bytes.unshift(Number(number % 256n));
    number /= 256n;
  }
  for (const character of value) {
    if (character !== "1") {
      break;
    }
    bytes.unshift(0);
  }
  return Uint8Array.from(bytes);
}

describe("signer", () => {
  it("hashes the question the same way the broker does", () => {
    expect(questionDigest(QUESTION)).toBe(
      "8cb2e018977f5ea40a0701b74a0b2712f8a7e03f82725195f382ce57d8a68b8c",
    );
    expect(questionHash(QUESTION, NONCE)).toBe(
      "f3a0b770b51754a113ea2da0a03ffde614b152509db26289a1759759eec2bc71",
    );
  });

  it("builds the canonical ask message from decision D-010", () => {
    expect(buildAskMessage(7, QUESTION, NONCE, "localhost:8000")).toBe(
      `mnemos:v1:ask|7|${questionDigest(QUESTION)}|${NONCE}|localhost:8000`,
    );
  });

  it("generates a 32 byte nonce", () => {
    const nonce = newNonceHex();
    expect(nonce).toHaveLength(64);
    expect(hexToBytes(nonce)).toHaveLength(32);
    expect(newNonceHex()).not.toBe(nonce);
  });

  it("produces a signature the broker can verify", () => {
    const signer = new AgentSigner(SECRET_KEY);
    const message = buildAskMessage(1, QUESTION, NONCE, "localhost:8000");
    const signature = signer.sign(message);
    const raw = Uint8Array.from(Buffer.from(signature, "base64"));
    expect(raw).toHaveLength(64);

    const publicKey = signer.publicKey;
    expect(publicKey.startsWith("ed25519:")).toBe(true);
    const publicBytes = decodeBase58(publicKey.slice("ed25519:".length));
    expect(publicBytes).toHaveLength(32);
    expect(
      ed25519.verify(raw, sha256(new TextEncoder().encode(message)), publicBytes),
    ).toBe(true);
  });

  it("rejects a message that was changed after signing", () => {
    const signer = new AgentSigner(SECRET_KEY);
    const message = buildAskMessage(1, QUESTION, NONCE, "localhost:8000");
    const signature = signer.sign(message);
    const raw = Uint8Array.from(Buffer.from(signature, "base64"));
    const publicBytes = decodeBase58(signer.publicKey.slice("ed25519:".length));
    const tampered = buildAskMessage(2, QUESTION, NONCE, "localhost:8000");
    expect(
      ed25519.verify(raw, sha256(new TextEncoder().encode(tampered)), publicBytes),
    ).toBe(false);
  });

  it("rejects a key that is not an ed25519 secret key", () => {
    expect(() => new AgentSigner("not-a-key")).toThrow();
  });
});
