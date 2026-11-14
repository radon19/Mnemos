import { expect, test } from "@playwright/test";

test("signing out clears an exchange answer and its cached private evidence", async ({ page }) => {
  await page.route("**/v1/auth/optional", (route) => route.fulfill({ json: { authenticated: true, account: "owner.testnet" } }));
  await page.route("**/v1/auth/logout", (route) => route.fulfill({ json: { ok: true } }));
  await page.route("**/v1/vault/items?**", (route) => route.fulfill({ json: { items: [
    { id: "7c74ff51-5501-4bfe-9341-79bcfdfe7a11", scope: "expertise" },
    { id: "7c74ff51-5501-4bfe-9341-79bcfdfe7a12", scope: "private" },
  ], next_cursor: null } }));
  await page.route("**/api/demo/exchange", (route) => {
    const body = route.request().postDataJSON() as { action?: string } | null;
    return route.fulfill({ json: body ? { action: "ask", result: {
      req_id: 9, status: "served", answer: "Private answer that must disappear at signout.", verified: true,
      answer_withheld: false, receipt_hash: "b".repeat(64), tx_hash: "receipt", latency_ms: 100,
      attestation_summary: { signature_kind: "provider_tee" },
    } } : {
      owner: "owner.testnet", agent: "agent.testnet", contract: "contract.testnet", network: "testnet", broker_verified: true,
      credit: "10000000000000000000000", earnings: "0", paused: false,
      grant: { agent: "agent.testnet", scopes: ["expertise"], price: "1000000000000000000000", daily_cap: 8, remaining_today: 8, max_answer_tokens: 256, revoked: false, expires_ns: "1999999999999999999" },
    } });
  });
  await page.goto("/exchange");
  await page.getByRole("button", { name: "Ask for 0.001 NEAR" }).click();
  await expect(page.getByText("Private answer that must disappear at signout.")).toBeVisible();
  await expect(page.getByRole("button", { name: "Refresh status" })).toBeEnabled();
  const signOut = page.getByRole("button", { name: "Sign out", exact: true }).filter({ visible: true });
  if (await signOut.count() === 0) await page.getByRole("button", { name: "Menu", exact: true }).click();
  await page.getByRole("button", { name: "Sign out", exact: true }).filter({ visible: true }).click();
  await expect(page.getByRole("button", { name: "Start local owner session" })).toBeVisible();
  await expect(page.getByText("Private answer that must disappear at signout.")).toHaveCount(0);
  await expect(page.getByText("Response verified", { exact: true })).toHaveCount(0);
  await expect(page.getByText("owner.testnet", { exact: true })).toHaveCount(0);
});

test("owner tools expose the demo knowledge scopes", async ({ page }) => {
  await page.goto("/vault");
  await expect(page.getByRole("combobox", { name: "Scope", exact: true }).getByRole("option", { name: "expertise", exact: true })).toHaveCount(1);
  await expect(page.getByRole("combobox", { name: "Scope", exact: true }).getByRole("option", { name: "private", exact: true })).toHaveCount(1);
  await page.goto("/grants");
  await expect(page.getByRole("checkbox", { name: "expertise", exact: true })).toHaveCount(1);
  await page.goto("/redteam");
  await expect(page.getByRole("combobox", { name: "Scope", exact: true }).getByRole("option", { name: "expertise", exact: true })).toHaveCount(1);
});
