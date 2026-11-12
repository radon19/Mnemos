/**
 * Reading the owner's own vault in the browser.
 *
 * The broker stores the item wrapped twice: once for the owner, once for the
 * broker. Only the owner wrap is needed here, so the note is opened with the
 * passphrase in this tab and never leaves the device.
 */

import { MnemosCryptoError, base64ToBytes, openOwnerItem } from "@mnemos/crypto";

import type { VaultItem } from "./broker";
import { ownerSaltFromBase64 } from "./vault";

export interface DecryptedItem {
  id: string;
  scope: string;
  text: string;
}

export class VaultDecryptError extends Error {
  readonly code: string;

  constructor(code: string, message: string) {
    super(message);
    this.name = "VaultDecryptError";
    this.code = code;
  }
}

export function decryptVaultItem(
  item: VaultItem,
  owner: string,
  passphrase: string,
  ownerSaltB64: string,
): DecryptedItem {
  try {
    const plain = openOwnerItem(
      {
        itemId: item.id,
        owner,
        scope: item.scope,
        ciphertext: base64ToBytes(item.ciphertext_b64),
        nonce: base64ToBytes(item.nonce_b64),
        wrappedDekOwner: base64ToBytes(item.wrapped_dek_owner_b64),
        contentHash: item.content_hash,
      },
      passphrase,
      ownerSaltFromBase64(ownerSaltB64),
    );
    return { id: item.id, scope: item.scope, text: new TextDecoder().decode(plain) };
  } catch (error) {
    const code = error instanceof MnemosCryptoError ? error.code : "E_DECRYPT_FAILED";
    throw new VaultDecryptError(
      code,
      code === "E_DECRYPT_FAILED"
        ? "this note could not be opened with the current passphrase"
        : `this note could not be opened (${code})`,
    );
  }
}
