/**
 * HTTP client for the Mnemos broker.
 *
 * The broker is the only component that can decrypt the owner's memory. This
 * client never sees plaintext: it sends the question and a signature, and
 * receives the answer plus the verification summary.
 */

import { MnemosToolError, hintFor } from "./errors.js";

export interface AskRequestBody {
  req_id: number;
  question: string;
  nonce: string;
  signature_b64: string;
  agent: string;
  public_key: string;
}

export interface AttestationSummary {
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

export interface AskResponseBody {
  req_id: number;
  status: "served" | "withheld";
  answer: string | null;
  answer_withheld: boolean;
  verified: boolean;
  attestation_summary: AttestationSummary | null;
  receipt_hash: string | null;
  tx_hash: string | null;
  refund_tx_hash?: string | null;
  error_code?: string | null;
  latency_ms: number;
}

export interface BrokerClient {
  ask(body: AskRequestBody): Promise<AskResponseBody>;
}

export type FetchLike = (
  input: string,
  init?: { method?: string; headers?: Record<string, string>; body?: string },
) => Promise<{ ok: boolean; status: number; json: () => Promise<unknown>; text: () => Promise<string> }>;

export class HttpBrokerClient implements BrokerClient {
  private readonly baseUrl: string;
  private readonly fetchImpl: FetchLike;

  constructor(baseUrl: string, fetchImpl: FetchLike = fetch) {
    this.baseUrl = baseUrl.replace(/\/+$/u, "");
    this.fetchImpl = fetchImpl;
  }

  async ask(body: AskRequestBody): Promise<AskResponseBody> {
    let response: Awaited<ReturnType<FetchLike>>;
    try {
      response = await this.fetchImpl(`${this.baseUrl}/v1/ask`, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify(body),
      });
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      throw new MnemosToolError(
        "E_BROKER_UNREACHABLE",
        `the broker could not be reached: ${message}`,
        hintFor("E_BROKER_UNREACHABLE"),
      );
    }

    const text = await response.text();
    let payload: unknown;
    try {
      payload = text === "" ? null : JSON.parse(text);
    } catch {
      payload = null;
    }

    if (!response.ok) {
      const envelope =
        typeof payload === "object" && payload !== null
          ? (payload as { code?: unknown; message?: unknown })
          : {};
      const code =
        typeof envelope.code === "string" ? envelope.code : `E_BROKER_${response.status}`;
      const message =
        typeof envelope.message === "string" ? envelope.message : text.slice(0, 400);
      throw new MnemosToolError(code, message, hintFor(code));
    }

    if (typeof payload !== "object" || payload === null) {
      throw new MnemosToolError(
        "E_BROKER_UNREACHABLE",
        "the broker returned a response that is not JSON",
        hintFor("E_BROKER_UNREACHABLE"),
      );
    }
    return payload as AskResponseBody;
  }
}
