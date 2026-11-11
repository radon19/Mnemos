#!/usr/bin/env node
/**
 * `mnemos-agent` command line.
 *
 * The MCP server is the product surface, but scripts and the demo need the
 * same three tools from a shell:
 *
 *     mnemos-agent ask --owner alice.testnet --scope travel "When is my flight?"
 *     mnemos-agent grants --owner alice.testnet
 *     mnemos-agent credit
 */

import { createDeps } from "./deps.js";
import { MnemosToolError } from "./errors.js";
import { askMemory, checkCredit, listGrants } from "./tools.js";

interface ParsedArgs {
  command: string;
  options: Record<string, string>;
  positionals: string[];
}

export function parseArgs(argv: string[]): ParsedArgs {
  const [command = "", ...rest] = argv;
  const options: Record<string, string> = {};
  const positionals: string[] = [];
  for (let index = 0; index < rest.length; index += 1) {
    const token = rest[index];
    if (token === undefined) {
      continue;
    }
    if (token.startsWith("--")) {
      const [name, inlineValue] = token.slice(2).split("=", 2);
      if (name === undefined) {
        continue;
      }
      if (inlineValue !== undefined) {
        options[name] = inlineValue;
        continue;
      }
      const next = rest[index + 1];
      if (next !== undefined && !next.startsWith("--")) {
        options[name] = next;
        index += 1;
        continue;
      }
      options[name] = "true";
      continue;
    }
    positionals.push(token);
  }
  return { command, options, positionals };
}

function requireOption(options: Record<string, string>, name: string): string {
  const value = options[name];
  if (value === undefined || value === "") {
    throw new Error(`missing required option --${name}`);
  }
  return value;
}

const USAGE = `mnemos-agent <command>

Commands:
  ask --owner <account> --scope <scope> <question>   ask one question of the owner's memory
  grants --owner <account>                            show the grant for this agent
  credit                                              show the prepaid balance of this agent

Environment:
  MNEMOS_CONTRACT_ID, MNEMOS_AGENT_ACCOUNT, MNEMOS_AGENT_KEY, MNEMOS_BROKER_URL, NEAR_RPC_URL
`;

export async function run(argv: string[]): Promise<number> {
  const parsed = parseArgs(argv);
  switch (parsed.command) {
    case "ask": {
      const owner = requireOption(parsed.options, "owner");
      const scope = requireOption(parsed.options, "scope");
      const question = parsed.positionals.join(" ").trim();
      if (question === "") {
        throw new Error("ask needs a question");
      }
      const deps = createDeps();
      const result = await askMemory(deps, { owner, scope, question });
      process.stdout.write(`${JSON.stringify(result, null, 2)}\n`);
      return 0;
    }
    case "grants": {
      const owner = requireOption(parsed.options, "owner");
      const deps = createDeps();
      const result = await listGrants(deps, owner);
      process.stdout.write(`${JSON.stringify(result, null, 2)}\n`);
      return 0;
    }
    case "credit": {
      const deps = createDeps();
      const result = await checkCredit(deps);
      process.stdout.write(`${JSON.stringify(result, null, 2)}\n`);
      return 0;
    }
    case "help":
    case "--help":
    case "-h":
    case "":
      process.stdout.write(USAGE);
      return 0;
    default:
      process.stderr.write(`unknown command '${parsed.command}'\n\n${USAGE}`);
      return 2;
  }
}

run(process.argv.slice(2))
  .then((code) => {
    process.exitCode = code;
  })
  .catch((error: unknown) => {
    if (error instanceof MnemosToolError) {
      process.stderr.write(`${error.code}: ${error.message}\n${error.hint}\n`);
    } else {
      process.stderr.write(`${error instanceof Error ? error.message : String(error)}\n`);
    }
    process.exitCode = 1;
  });
