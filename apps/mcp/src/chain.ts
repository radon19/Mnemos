/**
 * Typed access to the Mnemos contract.
 *
 * The view calls go through near-api-js. The only state changing call the MCP
 * server makes is `request_read`, signed by the agent key, exactly like any
 * other agent.
 */

import {
  Account,
  JsonRpcProvider,
  actions,
  type KeyPairString,
  type SerializedReturnValue,
} from "near-api-js";

import { MnemosToolError, extractContractCode, hintFor } from "./errors.js";

export interface GrantView {
  owner: string;
  agent: string;
  scopes: string[];
  price: string;
  daily_cap: number;
  expires_ns: string;
  max_answer_tokens: number;
  revoked: boolean;
  used_today: number;
  remaining_today: number;
  day_index: number;
}

export interface RequestView {
  id: number;
  owner: string;
  agent: string;
  scope: string;
  price: string;
  q_hash: string;
  status: string;
  created_ns: string;
  receipt_hash: string | null;
}

export interface ConfigView {
  owner: string;
  paused: boolean;
  next_request_id: number;
  request_ttl_ns: string;
  day_ns: string;
}

export interface ChainOptions {
  contractId: string;
  agentAccount: string;
  agentSecretKey: string;
  rpcUrl: string;
  requestGas: bigint;
}

export interface ChainClient {
  getRequest(reqId: number): Promise<RequestView | null>;
  getGrant(owner: string, agent: string): Promise<GrantView | null>;
  getConfig(): Promise<ConfigView>;
  getRequestTtlNs(): Promise<bigint>;
  creditOf(agent: string): Promise<string>;
  requestRead(owner: string, scope: string, qHash: string): Promise<number>;
  expireRequest(reqId: number): Promise<string>;
}

function describe(error: unknown): string {
  if (error instanceof Error) {
    return error.message;
  }
  if (typeof error === "string") {
    return error;
  }
  try {
    return JSON.stringify(error);
  } catch {
    return String(error);
  }
}

export function chainError(error: unknown, fallbackCode = "E_RPC_ERROR"): MnemosToolError {
  const text = describe(error);
  const code = extractContractCode(text) ?? fallbackCode;
  return new MnemosToolError(code, text, hintFor(code));
}

export class NearChainClient implements ChainClient {
  private readonly provider: JsonRpcProvider;
  private readonly account: Account;
  private readonly options: ChainOptions;

  constructor(options: ChainOptions) {
    this.options = options;
    this.provider = new JsonRpcProvider({ url: options.rpcUrl });
    this.account = new Account(
      options.agentAccount,
      this.provider,
      options.agentSecretKey as KeyPairString,
    );
  }

  private async view<T extends SerializedReturnValue>(
    methodName: string,
    args: Record<string, unknown>,
  ): Promise<T | null> {
    try {
      const result = await this.provider.callFunction<T>({
        contractId: this.options.contractId,
        method: methodName,
        args,
      });
      return result ?? null;
    } catch (error) {
      throw chainError(error);
    }
  }

  async getRequest(reqId: number): Promise<RequestView | null> {
    return await this.view<RequestView>("get_request", { req_id: reqId });
  }

  async getGrant(owner: string, agent: string): Promise<GrantView | null> {
    return await this.view<GrantView>("get_grant", { owner, agent });
  }

  /** The request window in nanoseconds, as the contract reports it. */
  async getRequestTtlNs(): Promise<bigint> {
    const config = await this.getConfig();
    return BigInt(config.request_ttl_ns);
  }

  async getConfig(): Promise<ConfigView> {
    const config = await this.view<ConfigView>("get_config", {});
    if (config === null) {
      throw new MnemosToolError(
        "E_RPC_ERROR",
        "the contract returned no configuration",
        hintFor("E_RPC_ERROR"),
      );
    }
    return config;
  }

  async creditOf(agent: string): Promise<string> {
    const credit = await this.view<string>("credit_of", { agent });
    return credit ?? "0";
  }

  /**
   * Creates the on-chain read request and returns its id.
   *
   * Request ids are sequential, so the id is read before and after the call
   * and the request whose `q_hash` matches ours is selected. That stays
   * correct when another agent creates a request at the same time.
   */
  async requestRead(owner: string, scope: string, qHash: string): Promise<number> {
    const before = (await this.getConfig()).next_request_id;
    let failure: string | null = null;
    try {
      const response = await this.account.signAndSendTransaction({
        receiverId: this.options.contractId,
        actions: [
          actions.functionCall(
            "request_read",
            { owner, scope, q_hash: qHash },
            this.options.requestGas,
          ),
        ],
        waitUntil: "FINAL",
        throwOnFailure: false,
      });
      const status = response.status;
      if (typeof status === "object" && "Failure" in status) {
        // The contract's panic message ("E_CODE: detail") is nested inside the
        // typed execution error, so the whole failure is serialised and the
        // stable code is extracted from it.
        failure = JSON.stringify(status.Failure);
      }
    } catch (error) {
      throw chainError(error);
    }
    if (failure !== null) {
      const code = extractContractCode(failure) ?? "E_RPC_ERROR";
      throw new MnemosToolError(code, failure, hintFor(code));
    }

    const after = (await this.getConfig()).next_request_id;
    for (let reqId = before; reqId < after; reqId += 1) {
      const request = await this.getRequest(reqId);
      if (request !== null && request.q_hash === qHash) {
        return reqId;
      }
    }
    throw new MnemosToolError(
      "E_RPC_ERROR",
      `the read request was created but could not be found on chain (ids ${before}..${after - 1})`,
      hintFor("E_RPC_ERROR"),
    );
  }

  /**
   * Expire a read request that was never served.
   *
   * The call is permissionless: anyone may return the credit of a request
   * that passed its window. The agent calls it when it finds its own request
   * expired, so a request that was created and never asked for does not hold
   * the credit.
   */
  async expireRequest(reqId: number): Promise<string> {
    try {
      const response = await this.account.signAndSendTransaction({
        receiverId: this.options.contractId,
        actions: [
          actions.functionCall(
            "expire_request",
            { req_id: reqId },
            this.options.requestGas,
          ),
        ],
        waitUntil: "FINAL",
        throwOnFailure: false,
      });
      const status = response.status;
      if (typeof status === "object" && "Failure" in status) {
        const failure = JSON.stringify(status.Failure);
        const code = extractContractCode(failure) ?? "E_RPC_ERROR";
        throw new MnemosToolError(code, failure, hintFor(code));
      }
    } catch (error) {
      if (error instanceof MnemosToolError) {
        throw error;
      }
      throw chainError(error);
    }
    return `expired request ${reqId}`;
  }
}
