/**
 * Streamable HTTP entry point.
 *
 * The transport is stateless: every POST creates a server and a transport, so
 * the process can be scaled horizontally without sticky sessions. This is the
 * transport to expose when the MCP server runs as a service.
 */

import { createServer, type IncomingMessage, type ServerResponse } from "node:http";

import { StreamableHTTPServerTransport } from "@modelcontextprotocol/sdk/server/streamableHttp.js";
import type { StreamableHTTPServerTransportOptions } from "@modelcontextprotocol/sdk/server/streamableHttp.js";

import { createDeps } from "./deps.js";
import { createMcpServer } from "./server.js";

const MAX_BODY_BYTES = 1_048_576;

// The SDK documents `sessionIdGenerator: undefined` as the stateless mode, but
// its option type does not allow an explicit undefined under
// exactOptionalPropertyTypes.
const STATELESS_OPTIONS = {
  sessionIdGenerator: undefined,
} as unknown as StreamableHTTPServerTransportOptions;

async function readBody(request: IncomingMessage): Promise<unknown> {
  const chunks: Buffer[] = [];
  let size = 0;
  for await (const chunk of request) {
    const buffer = Buffer.isBuffer(chunk) ? chunk : Buffer.from(chunk as string);
    size += buffer.length;
    if (size > MAX_BODY_BYTES) {
      throw new Error("request body is too large");
    }
    chunks.push(buffer);
  }
  if (chunks.length === 0) {
    return undefined;
  }
  const text = Buffer.concat(chunks).toString("utf-8");
  return JSON.parse(text) as unknown;
}

function methodNotAllowed(response: ServerResponse): void {
  response.writeHead(405, { "content-type": "application/json" });
  response.end(
    JSON.stringify({
      jsonrpc: "2.0",
      error: { code: -32_000, message: "Method not allowed." },
      id: null,
    }),
  );
}

export async function startHttpServer(port: number): Promise<void> {
  const deps = createDeps();

  const server = createServer((request: IncomingMessage, response: ServerResponse) => {
    const url = new URL(request.url ?? "/", "http://localhost");
    if (url.pathname !== "/mcp") {
      response.writeHead(404, { "content-type": "application/json" });
      response.end(JSON.stringify({ error: "not found" }));
      return;
    }
    if (request.method === "POST") {
      void (async () => {
        let body: unknown;
        try {
          body = await readBody(request);
        } catch (error) {
          response.writeHead(400, { "content-type": "application/json" });
          response.end(
            JSON.stringify({
              jsonrpc: "2.0",
              error: {
                code: -32_700,
                message: error instanceof Error ? error.message : "invalid body",
              },
              id: null,
            }),
          );
          return;
        }
        const mcpServer = createMcpServer(deps);
        const transport = new StreamableHTTPServerTransport(STATELESS_OPTIONS);
        try {
          await mcpServer.connect(transport);
          await transport.handleRequest(request, response, body);
        } catch (error) {
          if (!response.headersSent) {
            response.writeHead(500, { "content-type": "application/json" });
            response.end(
              JSON.stringify({
                jsonrpc: "2.0",
                error: {
                  code: -32_603,
                  message: error instanceof Error ? error.message : "internal error",
                },
                id: null,
              }),
            );
          }
        } finally {
          void transport.close();
          void mcpServer.close();
        }
      })();
      return;
    }
    if (request.method === "GET" || request.method === "DELETE") {
      methodNotAllowed(response);
      return;
    }
    response.writeHead(405).end();
  });

  await new Promise<void>((resolve) => {
    server.listen(port, resolve);
  });
  process.stderr.write(`mnemos mcp server listening on http://127.0.0.1:${port}/mcp\n`);
}

startHttpServer(Number(process.env.MNEMOS_HTTP_PORT ?? "3000")).catch(
  (error: unknown) => {
    process.stderr.write(`mnemos mcp http server failed: ${String(error)}\n`);
    process.exitCode = 1;
  },
);
