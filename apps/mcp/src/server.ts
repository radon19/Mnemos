/**
 * MCP server wiring.
 *
 * Three tools, no side effects beyond the read the caller asked for. Every
 * failure is returned as a readable message that keeps the stable contract
 * code, so an agent can decide what to do without parsing prose.
 */

import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import type { CallToolResult } from "@modelcontextprotocol/sdk/types.js";
import { z } from "zod";

import { MnemosToolError } from "./errors.js";
import { askMemory, checkCredit, listGrants, type ToolDeps } from "./tools.js";

export const SERVER_NAME = "mnemos";
export const SERVER_VERSION = "0.1.0";

export interface ToolResult {
  content: { type: "text"; text: string }[];
  isError?: boolean;
}

function ok(payload: unknown): CallToolResult {
  return { content: [{ type: "text", text: JSON.stringify(payload, null, 2) }] };
}

function fail(error: unknown): CallToolResult {
  if (error instanceof MnemosToolError) {
    const text = `${error.code}: ${error.message}${error.hint === "" ? "" : ` ${error.hint}`}`;
    return { content: [{ type: "text", text }], isError: true };
  }
  const message = error instanceof Error ? error.message : String(error);
  return {
    content: [{ type: "text", text: `E_UNKNOWN: ${message}` }],
    isError: true,
  };
}

export function createMcpServer(deps: ToolDeps): McpServer {
  const server = new McpServer(
    { name: SERVER_NAME, version: SERVER_VERSION },
    {
      instructions:
        "Mnemos gives an agent metered, revocable read access to a user's encrypted memory. " +
        "Every read is paid for on NEAR and produces a hash-only receipt. Use ask_memory for a " +
        "question, list_grants to see what is allowed, check_credit to see the prepaid balance.",
    },
  );

  server.registerTool(
    "ask_memory",
    {
      title: "Ask the owner's memory",
      description:
        "Read one scope of an owner's encrypted memory and answer a question about it. " +
        "Creates a metered read request on NEAR, waits for approval, and returns the answer " +
        "with a verification summary and a hash-only receipt.",
      inputSchema: {
        owner: z.string().describe("NEAR account id of the memory owner"),
        scope: z
          .string()
          .describe("Scope to read, for example 'travel' or 'health'"),
        question: z.string().describe("The question to answer from the memory"),
      },
    },
    async (args) => {
      try {
        return ok(
          await askMemory(deps, {
            owner: args.owner,
            scope: args.scope,
            question: args.question,
          }),
        );
      } catch (error) {
        return fail(error);
      }
    },
  );

  server.registerTool(
    "list_grants",
    {
      title: "List what this agent may read",
      description:
        "Show the grant that allows this agent to read an owner's memory: allowed scopes, " +
        "price, daily cap, remaining reads today and expiry.",
      inputSchema: {
        owner: z.string().describe("NEAR account id of the memory owner"),
      },
    },
    async (args) => {
      try {
        return ok(await listGrants(deps, args.owner));
      } catch (error) {
        return fail(error);
      }
    },
  );

  server.registerTool(
    "check_credit",
    {
      title: "Check the prepaid balance",
      description:
        "Show the prepaid NEAR balance of this agent account. Every read is paid from it, so " +
        "an empty balance means reads will fail with E_INSUFFICIENT_CREDIT.",
      inputSchema: {},
    },
    async () => {
      try {
        return ok(await checkCredit(deps));
      } catch (error) {
        return fail(error);
      }
    },
  );

  return server;
}
