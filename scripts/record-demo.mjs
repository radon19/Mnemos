/** Record and assert the REAL browser flow. No network interception or fixtures. */
import { createRequire } from "node:module";
import { mkdir, writeFile, rename } from "node:fs/promises";
import { resolve } from "node:path";

const require = createRequire(new URL("../apps/web/package.json", import.meta.url));
const { chromium, expect } = require("@playwright/test");
const output = resolve("artifacts/demo");
await mkdir(output, { recursive: true });
const browser = await chromium.launch({ headless: true, slowMo: 100 });
const context = await browser.newContext({
  viewport: { width: 1440, height: 1000 }, colorScheme: "light",
  recordVideo: { dir: output, size: { width: 1440, height: 1000 } },
});
const page = await context.newPage();
page.setDefaultTimeout(30_000);
const evidence = { recorded_at: new Date().toISOString(), source: "real browser, real NEAR testnet and NEAR AI; no mocked responses", events: [], responses: [] };
const errors = [];
page.on("pageerror", (error) => { errors.push(error.message); });
page.on("response", async (response) => {
  if (response.url().endsWith("/api/demo/exchange")) {
    const body = await response.json().catch(() => null);
    evidence.responses.push({ status: response.status(), method: response.request().method(), body });
  }
});
const started = Date.now();
async function mark(name) {
  evidence.events.push({ name, elapsed_ms: Date.now() - started });
  console.log(name);
  await page.screenshot({ path: `${output}/${name}.png`, fullPage: true });
  await page.waitForTimeout(800); // Deliberate viewing time for the recording.
}
async function action(button, bodyAction) {
  await button.scrollIntoViewIfNeeded();
  const pending = page.waitForResponse((response) => response.url().endsWith("/api/demo/exchange") && response.request().method() === "POST" && response.request().postDataJSON()?.action === bodyAction, { timeout: 180_000 });
  await button.click();
  const response = await pending;
  const payload = await response.json();
  if (!response.ok()) throw new Error(`${bodyAction} failed: ${payload.code ?? response.status()} — ${payload.message ?? "inspect the local demo"}`);
  await expect(page.getByRole("button", { name: "Refresh status" })).toBeEnabled({ timeout: 45_000 });
  return payload;
}

try {
  await page.goto("http://localhost:3000/exchange");
  await expect(page.locator("body")).toHaveAttribute("data-hydrated", "true");
  await mark("01-exchange");
  await page.getByRole("button", { name: "Start local owner session" }).click();
  await expect(page.getByText("Broker key matches", { exact: true })).toBeVisible({ timeout: 45_000 });
  const encrypted = page.getByRole("button", { name: "Encrypt demo knowledge" });
  if (await encrypted.count()) {
    await encrypted.click();
    await expect(page.getByRole("button", { name: "Sample knowledge sealed" })).toBeVisible();
  }
  await mark("02-encrypted-samples");
  const grantButton = page.getByRole("button", { name: /^(Grant expertise access|Renew expertise access)$/ });
  if (await grantButton.isEnabled()) await action(grantButton, "grant");
  await expect(page.getByText("Active grant", { exact: true })).toBeVisible();
  await mark("03-active-grant");
  const paid = await action(page.getByRole("button", { name: "Ask for 0.001 NEAR" }), "ask");
  if (paid.result?.status !== "served" || !paid.result.verified || !paid.result.tx_hash) throw new Error("The live answer was not served with verified evidence.");
  await page.getByRole("heading", { name: "The answer, with evidence" }).scrollIntoViewIfNeeded();
  await expect(page.getByText("Response verified", { exact: true })).toBeVisible();
  await mark("04-paid-answer");
  await page.getByText("Inspect TEE and signature evidence", { exact: true }).click();
  await mark("05-attestation");
  const scopeResponse = page.waitForResponse((response) => response.url().endsWith("/api/demo/exchange") && response.request().method() === "POST", { timeout: 90_000 });
  await page.getByRole("button", { name: "Try private scope" }).click();
  const scope = await (await scopeResponse).json();
  if (scope.code !== "E_SCOPE_DENIED") throw new Error("The deployed contract did not refuse the private scope.");
  await page.getByText("E_SCOPE_DENIED", { exact: true }).scrollIntoViewIfNeeded();
  await mark("06-private-scope-denied");
  await page.getByRole("button", { name: "Revoke access", exact: true }).click();
  await expect(page.getByRole("dialog")).toBeVisible();
  await mark("07-revoke-confirmation");
  await action(page.getByRole("dialog").getByRole("button", { name: "Revoke access", exact: true }), "revoke");
  await expect(page.getByText("Revoked grant", { exact: true })).toBeVisible();
  const deniedResponse = page.waitForResponse((response) => response.url().endsWith("/api/demo/exchange") && response.request().method() === "POST", { timeout: 90_000 });
  await page.getByRole("button", { name: "Try the same question" }).click();
  const denied = await (await deniedResponse).json();
  if (denied.code !== "E_GRANT_REVOKED") throw new Error("The deployed contract did not refuse the revoked grant.");
  await page.getByText("E_GRANT_REVOKED", { exact: true }).scrollIntoViewIfNeeded();
  await mark("08-revocation-proved");
  const wallet = page.getByRole("region", { name: "Buy through NEAR Intents" });
  await wallet.scrollIntoViewIfNeeded();
  await expect(wallet.getByRole("button", { name: "Refresh agent wallet" })).toBeEnabled({ timeout: 45_000 });
  evidence.agent_api_status = await page.evaluate(async () => (await fetch("/api/demo/commerce")).json());
  if (evidence.agent_api_status.network !== "mainnet") throw new Error("The live Agent API wallet network was not confirmed.");
  await mark("11-agent-wallet");
  const status = await page.evaluate(async () => (await fetch("/api/demo/exchange")).json());
  evidence.final_status = status;
  evidence.answer = paid.result;
  evidence.console_errors = errors;
  if (errors.length) throw new Error("Browser console errors occurred; inspect evidence.json.");
  await page.setViewportSize({ width: 390, height: 844 });
  await page.evaluate(() => window.scrollTo(0, 0));
  await page.screenshot({ path: `${output}/09-mobile.png`, fullPage: true });
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
  if (overflow > 1) throw new Error(`Mobile overflow: ${overflow}px`);
  await page.setViewportSize({ width: 1440, height: 1000 });
  await page.emulateMedia({ colorScheme: "dark", reducedMotion: "reduce" });
  await page.evaluate(() => document.documentElement.classList.add("dark"));
  await page.screenshot({ path: `${output}/10-dark.png`, fullPage: true });
  console.log(`Live flow passed. Receipt ${paid.result.receipt_hash}; transaction ${paid.result.tx_hash}`);
} catch (error) {
  evidence.error = String(error);
  await page.screenshot({ path: `${output}/failure.png`, fullPage: true }).catch(() => {});
  process.exitCode = 1;
  console.error(String(error));
} finally {
  // Only sample answers and public testnet metadata are written. No cookies,
  // tokens, request headers, account secrets or browser storage are exported.
  await writeFile(`${output}/evidence.json`, `${JSON.stringify(evidence, null, 2)}\n`);
  const video = page.video();
  await context.close();
  if (video) await rename(await video.path(), `${output}/mnemos-demo.webm`);
  await browser.close();
}
