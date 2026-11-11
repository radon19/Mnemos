import { readFileSync, readdirSync, statSync } from "node:fs";
import { join } from "node:path";

import { describe, expect, it } from "vitest";

const APP_ROOT = new URL("../", import.meta.url).pathname;
const SOURCE_DIR = join(APP_ROOT, "src");
const STYLES = join(SOURCE_DIR, "app", "globals.css");

function sourceFiles(directory: string): string[] {
  const files: string[] = [];
  for (const entry of readdirSync(directory)) {
    const path = join(directory, entry);
    if (statSync(path).isDirectory()) {
      files.push(...sourceFiles(path));
      continue;
    }
    if (path.endsWith(".tsx")) {
      files.push(path);
    }
  }
  return files;
}

const theme = readFileSync(STYLES, "utf-8");
const defined = new Set(
  Array.from(theme.matchAll(/--color-([a-z-]+):/g)).map((match) => match[1] ?? ""),
);

const used = new Set<string>();
for (const file of sourceFiles(SOURCE_DIR)) {
  const text = readFileSync(file, "utf-8");
  const patterns = [
    /\b(?:bg|text|ring|from|to|via)-([a-z][a-z0-9-]*)/g,
    /\bborder(?:-[trblxy])?-([a-z][a-z0-9-]*)/g,
  ];
  for (const pattern of patterns) {
    for (const match of text.matchAll(pattern)) {
      used.add(match[1] ?? "");
    }
  }
}

describe("colour tokens", () => {
  it("defines every colour the app uses", () => {
    const unknown = Array.from(used)
      .filter((token) => token.includes("-"))
      .filter((token) => !defined.has(token))
      .filter((token) => !/^(a|e|x|y)-/.test(token))
      .filter((token) => !/^[trblxy]-\d+$/.test(token))
      .sort();
    expect(unknown).toEqual([]);
  });

  it("keeps the accent, the verified state and the destructive state apart", () => {
    expect(defined.has("accent")).toBe(true);
    expect(defined.has("verified")).toBe(true);
    expect(defined.has("destructive")).toBe(true);
  });
});
