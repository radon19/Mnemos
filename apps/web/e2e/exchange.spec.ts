import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";

// Deterministic browser contract. The live rehearsal uses the real services
// separately; these fixtures test recovery and interaction without AI costs.
test("exchange explains terms and guides a paid answer through revoke and denial", async ({ page }) => {
  let signed = false;
  let revoked = false;
  let granted = false;
  let paid = false;
  await page.route("**/v1/auth/optional", (route) => route.fulfill({ json: { authenticated: signed, account: signed ? "owner.testnet" : null } }));
  await page.route("**/api/auth/demo", (route) => { signed = true; return route.fulfill({ json: { account: "owner.testnet", demo: true } }); });
  await page.route("**/api/demo/exchange", async (route) => {
    const body = route.request().postDataJSON() as { action?: string; scope?: string } | null;
    if (!body) return route.fulfill({ json: {
      owner: "owner.testnet", agent: "agent.testnet", contract: "contract.testnet", network: "testnet", broker_verified: true, paused: false,
      credit: "5000000000000000000000000", earnings: paid ? "1000000000000000000000" : "0",
      grant: granted ? { agent: "agent.testnet", owner: "owner.testnet", scopes: ["expertise"], price: "1000000000000000000000", daily_cap: 8, remaining_today: 7, max_answer_tokens: 256, revoked, expires_ns: "1999999999999999999" } : null,
    } });
    if (body.action === "grant") { granted = true; revoked = false; return route.fulfill({ json: { action: "grant", tx_hash: "grant-transaction" } }); }
    if (body.action === "revoke") { revoked = true; return route.fulfill({ json: { action: "revoke", tx_hash: "revoke-transaction" } }); }
    if (body.action === "ask" && (revoked || body.scope === "private")) return route.fulfill({ status: 409, json: { code: revoked ? "E_GRANT_REVOKED" : "E_SCOPE_DENIED", message: "The contract refused this read." } });
    paid = true;
    return route.fulfill({ json: { action: "ask", result: { req_id: 42, status: "served", answer: "Stay in Campo de Ourique; explore by metro and on foot.", verified: true, answer_withheld: false, receipt_hash: "a".repeat(64), tx_hash: "receipt-transaction", latency_ms: 200, attestation_summary: { signature_kind: "provider_tee", verified_at: "2026-11-13T00:00:00Z" } } } });
  });
  // Existing encrypted samples avoid generating keys in this interaction test.
  await page.route("**/v1/vault/items?**", (route) => route.fulfill({ json: { items: [
    { id: "7c74ff51-5501-4bfe-9341-79bcfdfe7a11", scope: "expertise" },
    { id: "7c74ff51-5501-4bfe-9341-79bcfdfe7a12", scope: "private" },
  ], next_cursor: null } }));
  await page.goto("/exchange");
  await expect(page.getByRole("heading", { name: "Private expertise. Paid answers." })).toBeVisible();
  await expect(page.getByText("0.001 NEAR", { exact: true }).first()).toBeVisible();
  await page.getByRole("button", { name: "Start local owner session" }).click();
  await expect(page.getByRole("button", { name: "Grant expertise access" })).toBeEnabled();
  await page.getByRole("button", { name: "Grant expertise access" }).click();
  await expect(page.getByText("Active grant", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Ask for 0.001 NEAR" }).click();
  await expect(page.getByText("Stay in Campo de Ourique; explore by metro and on foot.")).toBeVisible();
  await expect(page.getByText("Response verified", { exact: true })).toBeVisible();
  await expect(page.getByRole("link", { name: "View settlement transaction" })).toHaveAttribute("href", /receipt-transaction/u);
  await page.getByRole("button", { name: "Try private scope" }).click();
  await expect(page.getByText("E_SCOPE_DENIED", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Revoke access", exact: true }).click();
  const dialog = page.getByRole("dialog");
  await expect(dialog).toBeVisible();
  await expect(page.getByRole("button", { name: "Keep access" })).toBeFocused();
  await page.keyboard.press("Escape");
  await expect(dialog).not.toBeVisible();
  await page.getByRole("button", { name: "Revoke access", exact: true }).click();
  await dialog.getByRole("button", { name: "Revoke access", exact: true }).click();
  await expect(page.getByText("Revoked grant", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Try the same question" }).click();
  await expect(page.getByText("E_GRANT_REVOKED", { exact: true })).toBeVisible();
  expect((await new AxeBuilder({ page }).analyze()).violations).toEqual([]);
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
});

test("exchange recovers from status failures without showing verified evidence", async ({ page }) => {
  await page.route("**/v1/auth/optional", (route) => route.fulfill({ json: { authenticated: true, account: "owner.testnet" } }));
  await page.route("**/v1/vault/items?**", (route) => route.fulfill({ json: { items: [], next_cursor: null } }));
  let fail = true;
  await page.route("**/api/demo/exchange", (route) => fail
    ? route.fulfill({ status: 502, json: { code: "E_DEMO_DEPENDENCY", message: "Broker unavailable. Run make doctor." } })
    : route.fulfill({ json: { owner: "owner.testnet", agent: "agent.testnet", contract: "contract.testnet", network: "testnet", broker_verified: true, paused: false, grant: null, credit: "0", earnings: "0" } }));
  await page.goto("/exchange");
  await expect(page.getByText("Broker unavailable. Run make doctor.")).toBeVisible();
  await expect(page.getByText("Response verified", { exact: true })).toHaveCount(0);
  fail = false;
  await page.getByRole("button", { name: "Refresh status" }).click();
  await expect(page.getByText("Broker key matches", { exact: true })).toBeVisible();
});
