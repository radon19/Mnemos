/** Shared public demo contract. No signing keys or server configuration here. */
import type { ActivityAttestation } from "./broker";
import type { GrantView } from "./near";

export const EXCHANGE_TERMS = {
  scope: "expertise", price: "1000000000000000000000", priceNear: "0.001",
  dailyCap: 8, hours: 24, answerTokens: 256,
} as const;

export const SAMPLE_QUESTION = "I want a quiet Lisbon neighborhood with good food. Where should I stay, and how should I get around?";
export const SAMPLE_NOTES = [
  {
    id: "7c74ff51-5501-4bfe-9341-79bcfdfe7a11", scope: "expertise", title: "Lisbon field notes",
    text: "Demo dossier — Lisbon travel specialist. Campo de Ourique is my recommendation for travelers seeking calm streets and neighborhood restaurants. Its covered market is a convenient place to sample local food. For exploring central Lisbon, use the metro and short walks rather than renting a car. Hilly streets make comfortable shoes important. Reserve popular restaurants ahead of time and avoid carrying luggage onto a crowded tram.",
  },
  {
    id: "7c74ff51-5501-4bfe-9341-79bcfdfe7a12", scope: "private", title: "Private business note",
    text: "Demo private business note. My internal supplier discount code is JUNIPER-427. This business information belongs in the private scope and must not be available through an expertise-only grant. It is fictional sample content for demonstrating scope isolation, not a real credential.",
  },
] as const;

export interface ExchangeStatus {
  owner: string;
  agent: string;
  contract: string;
  network: "testnet";
  grant: GrantView | null;
  credit: string;
  earnings: string;
  paused: boolean;
  broker_verified: boolean;
}

export interface ExchangeAnswer {
  req_id: number;
  owner: string;
  scope: string;
  status: "served" | "withheld";
  answer: string | null;
  answer_withheld: boolean;
  verified: boolean;
  receipt_hash: string | null;
  tx_hash: string | null;
  refund_tx_hash: string | null;
  latency_ms: number;
  attestation_summary: ActivityAttestation | null;
}

export interface ExchangeActionResult {
  action: "grant" | "ask" | "revoke";
  tx_hash?: string | null;
  already_active?: boolean;
  result?: ExchangeAnswer;
}

export class ExchangeClientError extends Error {
  constructor(readonly code: string, message: string) { super(message); }
}

export async function exchangeRequest<T>(body?: Record<string, unknown>): Promise<T> {
  let response: Response;
  try {
    response = await fetch("/api/demo/exchange", {
      method: body === undefined ? "GET" : "POST",
      headers: { "content-type": "application/json" },
      ...(body === undefined ? {} : { body: JSON.stringify(body) }),
      cache: "no-store",
    });
  } catch {
    throw new ExchangeClientError("E_CONNECTION", "Connection lost. Refresh status before retrying; a submitted transaction may already have settled.");
  }
  const payload = await response.json() as T & { code?: string; message?: string };
  if (!response.ok) throw new ExchangeClientError(payload.code ?? "E_DEMO", payload.message ?? "The action failed. Refresh status and try again.");
  return payload;
}
