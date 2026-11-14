import { base64ToBytes, fingerprintBrokerKey } from "@mnemos/crypto";
import { brokerApi } from "./broker";
import { contractId } from "./config";
import { SAMPLE_NOTES } from "./exchange";
import { callView, type BrokerInfo } from "./near";
import { createOwnerSalt, ownerSaltFromBase64, sealVaultItem } from "./vault";

/** Public sample passphrase, never use it for personal notes. */
export const SAMPLE_PASSPHRASE = "mnemos-demo-expertise";

async function hasSample(sample: typeof SAMPLE_NOTES[number]): Promise<boolean> {
  let cursor: string | undefined;
  // The broker bounds a vault to at most 10,000 items. Follow its cursors
  // rather than treating an older sample as missing and inserting it twice.
  for (let page = 0; page < 100; page++) {
    const result = await brokerApi.vaultItems({ scope: sample.scope, limit: 100, ...(cursor ? { cursor } : {}) });
    if (result.items.some((item) => item.id === sample.id)) return true;
    if (result.next_cursor === null) return false;
    cursor = result.next_cursor;
  }
  throw new Error("The vault exceeded its supported page limit. Inspect Vault before preparing samples.");
}

export async function sampleAvailability(): Promise<boolean> {
  return (await Promise.all(SAMPLE_NOTES.map(hasSample))).every(Boolean);
}

export async function prepareSamples(owner: string): Promise<void> {
  const [identity, registered] = await Promise.all([
    brokerApi.identity(), callView<BrokerInfo>("get_broker", { owner }),
  ]);
  const key = base64ToBytes(identity.public_key_b64);
  if (!registered || identity.contract_id !== contractId || identity.network !== "testnet" ||
      identity.account !== registered.broker_account || identity.fingerprint !== registered.broker_pubkey_fingerprint ||
      fingerprintBrokerKey(key) !== registered.broker_pubkey_fingerprint) {
    throw new Error("Broker key mismatch. No sample knowledge was encrypted or uploaded. Check Setup.");
  }
  let salt: Uint8Array;
  try { salt = ownerSaltFromBase64((await brokerApi.vaultSalt()).owner_salt_b64); }
  catch (error) {
    if (!(error instanceof Error && "status" in error && error.status === 404)) throw error;
    salt = createOwnerSalt();
  }
  for (const sample of SAMPLE_NOTES) {
    if (await hasSample(sample)) continue;
    await brokerApi.createVaultItem(sealVaultItem({
      owner, scope: sample.scope, itemId: sample.id, plaintext: sample.text,
      passphrase: SAMPLE_PASSPHRASE, ownerSalt: salt, brokerPublicKey: key,
    }));
  }
}
