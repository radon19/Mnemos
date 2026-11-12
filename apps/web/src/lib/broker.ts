/**
 * Typed client for the Mnemos broker.
 *
 * The browser never holds a decryption key for the vault. It holds the owner
 * passphrase (in memory only) and encrypts an item before it leaves the
 * device. Everything else here is plain JSON over the session cookie.
 */

import { brokerUrl } from "./config";

export class BrokerError extends Error {
  readonly code: string;
  readonly status: number;

  constructor(status: number, code: string, message: string) {
    super(message);
    this.name = "BrokerError";
    this.status = status;
    this.code = code;
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const headers: Record<string, string> = { "content-type": "application/json" };
  const extra = init?.headers;
  if (extra !== undefined && !Array.isArray(extra) && !(extra instanceof Headers)) {
    for (const [key, value] of Object.entries(extra)) {
      headers[key] = value;
    }
  }
  let response: Response;
  try {
    response = await fetch(`${brokerUrl}${path}`, {
      ...init,
      credentials: "include",
      headers,
    });
  } catch (error) {
    throw new BrokerError(
      0,
      "E_BROKER_UNREACHABLE",
      `the broker could not be reached: ${error instanceof Error ? error.message : String(error)}`,
    );
  }
  const text = await response.text();
  let payload: unknown = null;
  if (text !== "") {
    try {
      payload = JSON.parse(text) as unknown;
    } catch {
      payload = null;
    }
  }
  if (!response.ok) {
    const envelope =
      typeof payload === "object" && payload !== null
        ? (payload as { code?: unknown; message?: unknown })
        : {};
    const code = typeof envelope.code === "string" ? envelope.code : `E_BROKER_${response.status}`;
    const message =
      typeof envelope.message === "string" ? envelope.message : text.slice(0, 300);
    throw new BrokerError(response.status, code, message);
  }
  return payload as T;
}

export interface BrokerIdentity {
  account: string;
  public_key_b64: string;
  fingerprint: string;
  recipient: string;
  network: string;
  contract_id: string;
}

export interface SessionInfo {
  account: string;
  expires_at: string;
  demo: boolean;
}

export interface VaultItem {
  id: string;
  scope: string;
  ciphertext_b64: string;
  nonce_b64: string;
  wrapped_dek_owner_b64: string;
  content_hash: string;
  created_at: string;
}

export interface VaultPage {
  items: VaultItem[];
  next_cursor: string | null;
}

export interface VaultItemInput {
  id: string;
  scope: string;
  ciphertext_b64: string;
  nonce_b64: string;
  wrapped_dek_owner_b64: string;
  wrapped_dek_broker_b64: string;
  content_hash: string;
  owner_salt_b64: string;
}

export interface ActivityAttestation {
  signature_kind?: string;
  signer?: { signing_address?: string; signing_algo?: string };
  tcb_status?: string;
  advisory_ids?: string[];
  deployment?: Record<string, unknown>;
  deployment_provenance?: string;
  gpu_evidence?: string;
  verified_at?: string;
  filter_retry?: boolean;
  candidates_considered?: number;
  [key: string]: unknown;
}

export interface ActivityItem {
  req_id: number;
  agent: string;
  scope: string;
  price: string;
  status: string;
  source: "broker" | "chain";
  created_at: string | null;
  served_at: string | null;
  receipt_hash: string | null;
  receipt_tx_hash: string | null;
  refund_tx_hash: string | null;
  chat_id: string | null;
  attestation: ActivityAttestation | null;
  latency_ms: number | null;
  error_code: string | null;
}

export interface ActivityPage {
  items: ActivityItem[];
  next_cursor: string | null;
}

export interface RedteamAttack {
  id: string;
  label: string;
  question: string;
  outcome: "blocked" | "withheld" | "refused" | "residual" | "passed";
  reason: string;
  answer_preview: string | null;
}

export interface RedteamReport {
  simulated: boolean;
  scope: string;
  model: string;
  items_considered: number;
  attacks: RedteamAttack[];
  note: string;
}

export const brokerApi = {
  identity: async (): Promise<BrokerIdentity> => request<BrokerIdentity>("/v1/broker/pubkey"),

  session: async (): Promise<SessionInfo> => request<SessionInfo>("/v1/auth/session"),

  optionalSession: async (): Promise<{ authenticated: boolean; account: string | null }> =>
    request<{ authenticated: boolean; account: string | null }>("/v1/auth/optional"),

  challenge: async (account: string): Promise<{
    nonce_hex: string;
    nonce_b64: string;
    message: string;
    recipient: string;
    expires_at: string;
  }> => request("/v1/auth/challenge", { method: "POST", body: JSON.stringify({ account }) }),

  verify: async (input: {
    account: string;
    nonce_hex: string;
    public_key: string;
    signature_b64: string;
  }): Promise<SessionInfo> =>
    request<SessionInfo>("/v1/auth/verify", { method: "POST", body: JSON.stringify(input) }),

  logout: async (): Promise<{ ok: boolean }> =>
    request<{ ok: boolean }>("/v1/auth/logout", { method: "POST" }),

  vaultSalt: async (): Promise<{ owner_salt_b64: string }> =>
    request<{ owner_salt_b64: string }>("/v1/vault/salt"),

  vaultItems: async (params?: { scope?: string; cursor?: string; limit?: number }): Promise<VaultPage> => {
    const search = new URLSearchParams();
    if (params?.scope !== undefined) {
      search.set("scope", params.scope);
    }
    if (params?.cursor !== undefined) {
      search.set("cursor", params.cursor);
    }
    if (params?.limit !== undefined) {
      search.set("limit", String(params.limit));
    }
    const query = search.toString();
    return request<VaultPage>(`/v1/vault/items${query === "" ? "" : `?${query}`}`);
  },

  createVaultItem: async (item: VaultItemInput): Promise<VaultItem> =>
    request<VaultItem>("/v1/vault/items", { method: "POST", body: JSON.stringify(item) }),

  deleteVaultItem: async (id: string): Promise<void> => {
    await request<null>(`/v1/vault/items/${id}`, { method: "DELETE" });
  },

  activity: async (params?: { cursor?: string; limit?: number }): Promise<ActivityPage> => {
    const search = new URLSearchParams();
    if (params?.cursor !== undefined) {
      search.set("cursor", params.cursor);
    }
    if (params?.limit !== undefined) {
      search.set("limit", String(params.limit));
    }
    const query = search.toString();
    return request<ActivityPage>(`/v1/activity${query === "" ? "" : `?${query}`}`);
  },

  startRedteam: async (
    scope: string,
    maxTokens?: number,
  ): Promise<{ job_id: string; status: string }> =>
    request<{ job_id: string; status: string }>("/v1/redteam/run", {
      method: "POST",
      body: JSON.stringify(maxTokens === undefined ? { scope } : { scope, max_tokens: maxTokens }),
    }),

  redteamStatus: async (jobId: string): Promise<{
    job_id: string;
    status: string;
    result: RedteamReport | null;
    error: string | null;
  }> => request(`/v1/redteam/run/${jobId}`),
};
