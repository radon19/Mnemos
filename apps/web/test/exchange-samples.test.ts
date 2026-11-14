import { beforeEach, expect, it, vi } from "vitest";
import { bytesToBase64, fingerprintBrokerKey } from "@mnemos/crypto";
import { brokerApi } from "../src/lib/broker";
import { callView } from "../src/lib/near";
import { prepareSamples, sampleAvailability } from "../src/lib/exchange-samples";

vi.mock("../src/lib/broker", () => ({ brokerApi: {
  vaultItems: vi.fn(), vaultSalt: vi.fn(), identity: vi.fn(), createVaultItem: vi.fn(),
} }));
vi.mock("../src/lib/near", () => ({ callView: vi.fn() }));
vi.mock("../src/lib/config", () => ({ contractId: "contract.testnet" }));

beforeEach(() => {
  vi.resetAllMocks();
  vi.mocked(brokerApi.vaultItems).mockImplementation((params) => Promise.resolve({
    items: params?.scope === "private" ? [{ id: "7c74ff51-5501-4bfe-9341-79bcfdfe7a12", scope: "private" }] :
      params?.cursor ? [{ id: "7c74ff51-5501-4bfe-9341-79bcfdfe7a11", scope: "expertise" }] : [],
    next_cursor: params?.scope === "expertise" && !params.cursor ? "older-items" : null,
  } as Awaited<ReturnType<typeof brokerApi.vaultItems>>));
});

it("recognizes samples on later vault pages instead of treating them as missing", async () => {
  await expect(sampleAvailability()).resolves.toBe(true);
});

it("does not reinsert or replace samples found on later pages", async () => {
  const key = new Uint8Array(32); key[0] = 9;
  const fingerprint = fingerprintBrokerKey(key);
  vi.mocked(brokerApi.identity).mockResolvedValue({
    account: "broker.testnet", contract_id: "contract.testnet", network: "testnet",
    public_key_b64: bytesToBase64(key), fingerprint, recipient: "localhost:8000",
  });
  vi.mocked(callView).mockResolvedValue({ broker_account: "broker.testnet", broker_pubkey_fingerprint: fingerprint });
  vi.mocked(brokerApi.vaultSalt).mockResolvedValue({ owner_salt_b64: bytesToBase64(new Uint8Array(16)) });
  vi.mocked(brokerApi.createVaultItem).mockRejectedValue(new Error("Attempted duplicate insertion"));
  await expect(prepareSamples("owner.testnet")).resolves.toBeUndefined();
});
