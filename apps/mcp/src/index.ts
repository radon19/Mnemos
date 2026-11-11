/**
 * Public surface of the Mnemos MCP server.
 */

export { createMcpServer, SERVER_NAME, SERVER_VERSION } from "./server.js";
export { loadConfig, ConfigError, type McpConfig } from "./config.js";
export {
  HttpBrokerClient,
  type AskRequestBody,
  type AskResponseBody,
  type BrokerClient,
} from "./broker.js";
export {
  NearChainClient,
  type ChainClient,
  type ChainOptions,
  type ConfigView,
  type GrantView,
  type RequestView,
} from "./chain.js";
export {
  MnemosToolError,
  type MnemosErrorCode,
  extractContractCode,
  hintFor,
} from "./errors.js";
export {
  AgentSigner,
  buildAskMessage,
  newNonceHex,
  questionDigest,
  questionHash,
} from "./signer.js";
export {
  askMemory,
  checkCredit,
  listGrants,
  type AskMemoryInput,
  type AskMemoryOutput,
  type CreditOutput,
  type GrantOutput,
  type ToolDeps,
} from "./tools.js";
export { createDeps, type DepsOptions } from "./deps.js";
