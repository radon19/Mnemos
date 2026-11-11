/**
 * stdio entry point. This is the transport Claude Code, Cursor and other MCP
 * clients launch by default.
 */

import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";

import { createDeps } from "./deps.js";
import { createMcpServer } from "./server.js";

async function main(): Promise<void> {
  const deps = createDeps();
  const server = createMcpServer(deps);
  const transport = new StdioServerTransport();
  await server.connect(transport);
  process.stderr.write(
    `mnemos mcp server ready (agent ${deps.config.agentAccount}, contract ${deps.config.contractId})\n`,
  );
}

main().catch((error: unknown) => {
  process.stderr.write(`mnemos mcp server failed: ${String(error)}\n`);
  process.exitCode = 1;
});
