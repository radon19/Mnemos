/**
 * Errors the MCP tools return to the agent.
 *
 * The contract uses stable `E_*` codes. They are preserved verbatim in
 * `code` and translated into a sentence that tells the agent what to do next.
 */

export const CONTRACT_CODE_PATTERN = /\bE_[A-Z0-9_]+\b/u;

export type MnemosErrorCode =
  | "E_GRANT_NOT_FOUND"
  | "E_GRANT_REVOKED"
  | "E_GRANT_EXPIRED"
  | "E_SCOPE_DENIED"
  | "E_CAP_REACHED"
  | "E_INSUFFICIENT_CREDIT"
  | "E_PAUSED"
  | "E_TOO_MANY_PENDING"
  | "E_REQUEST_NOT_FOUND"
  | "E_REQUEST_NOT_APPROVED"
  | "E_REQUEST_EXPIRED"
  | "E_REQUEST_CONSUMED"
  | "E_Q_HASH_MISMATCH"
  | "E_AGENT_MISMATCH"
  | "E_BAD_SIGNATURE"
  | "E_KEY_NOT_FOUND"
  | "E_RATE_LIMITED"
  | "E_NO_MEMORY"
  | "E_OUTPUT_FILTER"
  | "E_INFERENCE_FAILED"
  | "E_VERIFICATION_FAILED"
  | "E_BROKER_UNREACHABLE"
  | "E_RPC_ERROR"
  | "E_TIMEOUT"
  | "E_INVALID_INPUT"
  | "E_UNKNOWN";

export class MnemosToolError extends Error {
  readonly code: string;
  readonly hint: string;

  constructor(code: string, message: string, hint = "") {
    super(message);
    this.name = "MnemosToolError";
    this.code = code;
    this.hint = hint;
  }
}

const HINTS: Record<string, string> = {
  E_GRANT_NOT_FOUND:
    "The owner has not granted this agent access yet. Ask them to create a grant for this agent account.",
  E_GRANT_REVOKED:
    "The owner revoked this grant. Access stops immediately; the owner can create a new one.",
  E_GRANT_EXPIRED: "The grant expired. The owner can create a new grant with a later expiry.",
  E_SCOPE_DENIED:
    "The grant does not include this scope. Ask the owner which scopes this agent may read.",
  E_CAP_REACHED:
    "The daily read cap for this grant is used up. It resets at the next UTC day, or the owner can raise the cap.",
  E_INSUFFICIENT_CREDIT:
    "This agent has no prepaid credit left. Deposit NEAR into the agent account, then retry.",
  E_PAUSED: "The Mnemos contract is paused. No reads are served until the owner unpauses it.",
  E_TOO_MANY_PENDING:
    "Too many reads are already pending for this agent. Wait for one to settle, then retry.",
  E_REQUEST_NOT_FOUND: "The read request does not exist on chain.",
  E_REQUEST_NOT_APPROVED: "The read request is not approved, so it cannot be served.",
  E_REQUEST_EXPIRED: "The read request passed its 10 minute window. Create a new one.",
  E_REQUEST_CONSUMED: "This read request was already served. Create a new one.",
  E_Q_HASH_MISMATCH:
    "The question and nonce do not match the hash on chain. This is a client bug, not a permission problem.",
  E_AGENT_MISMATCH: "This read request belongs to a different agent account.",
  E_BAD_SIGNATURE: "The broker rejected the request signature. Check the agent key.",
  E_KEY_NOT_FOUND:
    "The signing key does not belong to the agent account. Check MNEMOS_AGENT_KEY.",
  E_RATE_LIMITED: "Too many reads in a short window. Wait a minute and retry.",
  E_NO_MEMORY: "The owner has no readable memory in this scope yet.",
  E_OUTPUT_FILTER:
    "The answer repeated memory content and was withheld. The read was refunded.",
  E_INFERENCE_FAILED: "The model call failed. The read was refunded.",
  E_VERIFICATION_FAILED:
    "The model response could not be verified, so it was discarded. The read was refunded.",
  E_BROKER_UNREACHABLE: "The broker could not be reached. Check MNEMOS_BROKER_URL.",
  E_RPC_ERROR: "The NEAR RPC node could not be reached or returned an error.",
  E_TIMEOUT: "The read request did not become approved in time.",
  E_INVALID_INPUT: "The arguments are not valid.",
};

export function hintFor(code: string): string {
  return HINTS[code] ?? "Inspect the Mnemos contract and broker logs for details.";
}

export function extractContractCode(text: string): string | null {
  const match = CONTRACT_CODE_PATTERN.exec(text);
  return match === null ? null : match[0];
}
