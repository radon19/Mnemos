import { readFileSync } from "node:fs";

import { describe, expect, it } from "vitest";

import {
  MAX_ITEM_BYTES,
  MnemosCryptoError,
  base64ToBytes,
  bytesToBase64,
  decodePlaintext,
  deriveOwnerKek,
  envelopeFromJson,
  envelopeToJson,
  fingerprintBrokerKey,
  hexToUint8Array,
  openItemWithBroker,
  openItemWithKek,
  openItemWithOwner,
  sealItem,
  sealItemWithKek,
  uint8ArrayToHex,
  type ItemEnvelope,
} from "../src/index.js";

interface VectorItem {
  itemId: string;
  scope: string;
  plaintextUtf8: string;
  materials: {
    dek: string;
    itemNonce: string;
    ownerWrapNonce: string;
    brokerEphemeralSecret: string;
    brokerWrapNonce: string;
  };
  expected: {
    ciphertext: string;
    nonce: string;
    wrappedDekOwner: string;
    wrappedDekBroker: string;
    contentHash: string;
  };
}

interface Vectors {
  owner: string;
  ownerSalt: string;
  passphrase: string;
  brokerPrivateKey: string;
  brokerPublicKey: string;
  items: VectorItem[];
}

const vectors = JSON.parse(
  readFileSync(
    new URL("../../crypto-vectors/vectors.json", import.meta.url),
    "utf8",
  ),
) as Vectors;

function envelopeOf(item: VectorItem): ItemEnvelope {
  return {
    itemId: item.itemId,
    owner: vectors.owner,
    scope: item.scope,
    ciphertext: hexToUint8Array(item.expected.ciphertext),
    nonce: hexToUint8Array(item.expected.nonce),
    wrappedDekOwner: hexToUint8Array(item.expected.wrappedDekOwner),
    wrappedDekBroker: hexToUint8Array(item.expected.wrappedDekBroker),
    contentHash: item.expected.contentHash,
  };
}

function flipByte(bytes: Uint8Array, index: number): Uint8Array {
  const copy = new Uint8Array(bytes);
  copy[index] = (copy[index] ?? 0) ^ 0x01;
  return copy;
}

function expectCode(action: () => unknown, code: string): void {
  try {
    action();
  } catch (error) {
    expect(error).toBeInstanceOf(MnemosCryptoError);
    expect((error as MnemosCryptoError).code).toBe(code);
    return;
  }
  throw new Error(`expected MnemosCryptoError ${code}, but nothing was thrown`);
}

describe("committed vectors", () => {
  it("contains three vectors and the expected constants", () => {
    expect(vectors.items).toHaveLength(3);
    expect(vectors.passphrase).toContain("mnemos");
    expect(fingerprintBrokerKey(hexToUint8Array(vectors.brokerPublicKey))).toMatch(
      /^[0-9a-f]{64}$/,
    );
  });

  for (const [index, item] of vectors.items.entries()) {
    it(`re-encrypts vector ${index + 1} byte for byte`, () => {
      const envelope = sealItem({
        owner: vectors.owner,
        scope: item.scope,
        itemId: item.itemId,
        plaintext: item.plaintextUtf8,
        passphrase: vectors.passphrase,
        ownerSalt: hexToUint8Array(vectors.ownerSalt),
        brokerPublicKey: hexToUint8Array(vectors.brokerPublicKey),
        materials: {
          dek: hexToUint8Array(item.materials.dek),
          itemNonce: hexToUint8Array(item.materials.itemNonce),
          ownerWrapNonce: hexToUint8Array(item.materials.ownerWrapNonce),
          brokerEphemeralSecret: hexToUint8Array(
            item.materials.brokerEphemeralSecret,
          ),
          brokerWrapNonce: hexToUint8Array(item.materials.brokerWrapNonce),
        },
      });
      expect(uint8ArrayToHex(envelope.ciphertext)).toBe(
        item.expected.ciphertext,
      );
      expect(uint8ArrayToHex(envelope.nonce)).toBe(item.expected.nonce);
      expect(uint8ArrayToHex(envelope.wrappedDekOwner)).toBe(
        item.expected.wrappedDekOwner,
      );
      expect(uint8ArrayToHex(envelope.wrappedDekBroker)).toBe(
        item.expected.wrappedDekBroker,
      );
      expect(envelope.contentHash).toBe(item.expected.contentHash);
    });

    it(`decrypts vector ${index + 1} as owner and as broker`, () => {
      const envelope = envelopeOf(item);
      const ownerPlaintext = decodePlaintext(
        openItemWithOwner({
          envelope,
          passphrase: vectors.passphrase,
          ownerSalt: hexToUint8Array(vectors.ownerSalt),
        }),
      );
      expect(ownerPlaintext).toBe(item.plaintextUtf8);

      const brokerPlaintext = decodePlaintext(
        openItemWithBroker({
          envelope,
          brokerPrivateKey: hexToUint8Array(vectors.brokerPrivateKey),
        }),
      );
      expect(brokerPlaintext).toBe(item.plaintextUtf8);
    });
  }
});

describe("tamper detection", () => {
  const item = vectors.items[0];
  if (item === undefined) throw new Error("missing vector");
  const envelope = envelopeOf(item);
  const kek = deriveOwnerKek(
    vectors.passphrase,
    hexToUint8Array(vectors.ownerSalt),
  );

  it("rejects a flipped item ciphertext byte", () => {
    expectCode(
      () =>
        openItemWithKek({
          envelope: { ...envelope, ciphertext: flipByte(envelope.ciphertext, 3) },
          kek,
        }),
      "E_DECRYPT_FAILED",
    );
  });

  it("rejects a changed scope", () => {
    expectCode(
      () => openItemWithKek({ envelope: { ...envelope, scope: "work" }, kek }),
      "E_DECRYPT_FAILED",
    );
  });

  it("rejects a changed owner", () => {
    expectCode(
      () =>
        openItemWithKek({
          envelope: { ...envelope, owner: "mnemos-agent-76badc8e.testnet" },
          kek,
        }),
      "E_DECRYPT_FAILED",
    );
  });

  it("rejects a different valid item id", () => {
    expectCode(
      () =>
        openItemWithKek({
          envelope: {
            ...envelope,
            itemId: "00000000-0000-4000-8000-000000000000",
          },
          kek,
        }),
      "E_DECRYPT_FAILED",
    );
  });

  it("rejects the wrong passphrase", () => {
    expectCode(
      () =>
        openItemWithOwner({
          envelope,
          passphrase: "wrong passphrase",
          ownerSalt: hexToUint8Array(vectors.ownerSalt),
        }),
      "E_DECRYPT_FAILED",
    );
  });

  it("rejects the wrong owner salt", () => {
    expectCode(
      () =>
        openItemWithOwner({
          envelope,
          passphrase: vectors.passphrase,
          ownerSalt: new Uint8Array(16),
        }),
      "E_DECRYPT_FAILED",
    );
  });

  it("rejects a flipped owner-wrapped DEK byte", () => {
    expectCode(
      () =>
        openItemWithKek({
          envelope: {
            ...envelope,
            wrappedDekOwner: flipByte(envelope.wrappedDekOwner, 20),
          },
          kek,
        }),
      "E_DECRYPT_FAILED",
    );
  });

  it("rejects a flipped broker-wrapped DEK byte", () => {
    expectCode(
      () =>
        openItemWithBroker({
          envelope: {
            ...envelope,
            wrappedDekBroker: flipByte(envelope.wrappedDekBroker, 50),
          },
          brokerPrivateKey: hexToUint8Array(vectors.brokerPrivateKey),
        }),
      "E_DECRYPT_FAILED",
    );
  });

  it("rejects a mismatched content hash after decryption", () => {
    expectCode(
      () =>
        openItemWithKek({
          envelope: { ...envelope, contentHash: "00".repeat(32) },
          kek,
        }),
      "E_CONTENT_HASH_MISMATCH",
    );
  });
});

describe("validation", () => {
  const brokerPublicKey = hexToUint8Array(vectors.brokerPublicKey);

  it("rejects invalid metadata", () => {
    const base = {
      owner: vectors.owner,
      scope: "travel",
      itemId: "6f1c2a10-1b2c-4d3e-8f90-0123456789ab",
      plaintext: "note",
      kek: new Uint8Array(32),
      brokerPublicKey,
    };
    expectCode(
      () => sealItemWithKek({ ...base, owner: "BadOwner" }),
      "E_INVALID_OWNER",
    );
    expectCode(
      () => sealItemWithKek({ ...base, scope: "Travel" }),
      "E_INVALID_SCOPE",
    );
    expectCode(
      () =>
        sealItemWithKek({
          ...base,
          itemId: "6F1C2A10-1B2C-4D3E-8F90-0123456789AB",
        }),
      "E_INVALID_ITEM_ID",
    );
  });

  it("rejects empty and oversized items", () => {
    const base = {
      owner: vectors.owner,
      scope: "travel",
      itemId: "6f1c2a10-1b2c-4d3e-8f90-0123456789ab",
      kek: new Uint8Array(32),
      brokerPublicKey,
    };
    expectCode(
      () => sealItemWithKek({ ...base, plaintext: new Uint8Array() }),
      "E_EMPTY_ITEM",
    );
    expectCode(
      () =>
        sealItemWithKek({
          ...base,
          plaintext: new Uint8Array(MAX_ITEM_BYTES + 1),
        }),
      "E_ITEM_TOO_LARGE",
    );
  });

  it("rejects a bad key length", () => {
    expectCode(
      () =>
        sealItemWithKek({
          owner: vectors.owner,
          scope: "travel",
          itemId: "6f1c2a10-1b2c-4d3e-8f90-0123456789ab",
          plaintext: "note",
          kek: new Uint8Array(31),
          brokerPublicKey,
        }),
      "E_INVALID_KEY",
    );
  });
});

describe("encoding", () => {
  it("round-trips base64 for all byte values", () => {
    const bytes = Uint8Array.from({ length: 256 }, (_, index) => index);
    expect(base64ToBytes(bytesToBase64(bytes))).toEqual(bytes);
  });

  it("round-trips the envelope JSON shape used by the broker API", () => {
    const item = vectors.items[0];
    if (item === undefined) throw new Error("missing vector");
    const envelope = envelopeOf(item);
    const json = envelopeToJson(envelope);
    expect(json.item_id).toBe(envelope.itemId);
    expect(envelopeFromJson(json)).toEqual(envelope);
  });
});
