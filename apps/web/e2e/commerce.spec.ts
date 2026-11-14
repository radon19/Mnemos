import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";

test("mainnet purchase requires confirmation and retries the same read after a timeout", async ({ page }) => {
  await page.route("**/v1/auth/optional", route => route.fulfill({ json: { authenticated: true, account: "owner.testnet" } }));
  await page.route("**/api/demo/exchange", route => route.fulfill({ status: 503, json: { code: "E_DEMO_CONFIG", message: "Testnet configuration unavailable." } }));
  await page.route("**/v1/vault/items?**", route => route.fulfill({ json: { items: [], next_cursor: null } }));
  const ids: string[] = [];
  await page.route("**/api/demo/commerce", async route => {
    if (route.request().method() === "GET") return route.fulfill({ json: {
      network: "mainnet", buyer_id: "buyer", seller_account: "expert.near", asset: "usdc", price_usdc: "0.01",
      balances: { balances: [{ asset_id: "usdc", available_raw: "1000000" }] },
      policy: { policy: { budget: { daily_usd: "1.00" }, limits: { per_transaction: { usdc: "100000" } } } }, reads: [],
    } });
    const body = route.request().postDataJSON() as { read_id: string };
    ids.push(body.read_id);
    if (ids.length === 1) return route.fulfill({ status: 409, json: { code: "E_PAYMENT_PENDING", message: "Settlement is pending. Retry the same read ID." } });
    return route.fulfill({ json: { read_id: body.read_id, answer: "Take the metro and stay in Campo de Ourique.", network: "mainnet", verified: true, answer_hash: "a".repeat(64), attestation_summary: { signature_kind: "provider_tee", fresh_preflight: true }, payment: { correlation_id: "op_paid", status: "SUCCESS", details: { intent_hash: "settled-intent" } } } });
  });
  await page.goto("/exchange");
  const region = page.getByRole("region", { name: "Buy through NEAR Intents" });
  await expect(region.getByText("Mainnet · USDC", { exact: true })).toBeVisible();
  await region.getByRole("button", { name: "Buy answer for 0.01 USDC" }).click();
  expect(ids).toEqual([]);
  const dialog = page.getByRole("dialog", { name: "Buy this expertise answer?" });
  await expect(dialog).toBeVisible();
  await dialog.getByRole("button", { name: "Pay 0.01 USDC" }).click();
  await expect(region.getByText("Settlement is pending. Retry the same read ID.")).toBeVisible();
  await region.getByRole("button", { name: "Retry the same purchase" }).click();
  await expect(region.getByText("Take the metro and stay in Campo de Ourique.")).toBeVisible();
  expect(ids).toHaveLength(2);
  expect(ids[0]).toBe(ids[1]);
  expect((await new AxeBuilder({ page }).analyze()).violations).toEqual([]);
});

test("an unfunded mainnet wallet never offers a simulated successful purchase", async ({ page }) => {
  await page.route("**/v1/auth/optional", route => route.fulfill({ json: { authenticated: true, account: "owner.testnet" } }));
  await page.route("**/api/demo/exchange", route => route.fulfill({ status: 503, json: { code: "E_DEMO_CONFIG", message: "Testnet configuration unavailable." } }));
  await page.route("**/v1/vault/items?**", route => route.fulfill({ json: { items: [], next_cursor: null } }));
  await page.route("**/api/demo/commerce", route => route.fulfill({ json: { network: "mainnet", buyer_id: "buyer", seller_account: "expert.near", asset: "usdc", price_usdc: "0.01", balances: { balances: [] }, policy: {}, reads: [] } }));
  await page.goto("/exchange");
  const region = page.getByRole("region", { name: "Buy through NEAR Intents" });
  await expect(region.getByText("Funding needed", { exact: true })).toBeVisible();
  await expect(region.getByRole("button", { name: "Buy answer for 0.01 USDC" })).toBeDisabled();
});

test("reload resumes a pending paid read even when the remaining balance is empty", async ({ page }) => {
  await page.route("**/v1/auth/optional", route => route.fulfill({ json: { authenticated: true, account: "owner.testnet" } }));
  await page.route("**/api/demo/exchange", route => route.fulfill({ status: 503, json: { code: "E_DEMO_CONFIG", message: "Testnet configuration unavailable." } }));
  await page.route("**/v1/vault/items?**", route => route.fulfill({ json: { items: [], next_cursor: null } }));
  const recovered = "12345678-1234-4321-8123-123456789012";
  let sent: string | null = null;
  await page.route("**/api/demo/commerce", async route => {
    if (route.request().method() === "GET") return route.fulfill({ json: {
      network: "mainnet", buyer_id: "buyer", seller_account: "expert.near", asset: "usdc",
      balances: { balances: [] }, policy: {}, reads: [{ read_id: recovered, status: "pending", payment: null, refund: null }],
    } });
    sent = (route.request().postDataJSON() as { read_id: string }).read_id;
    return route.fulfill({ status: 409, json: { code: "E_PAYMENT_PENDING", message: "Still pending." } });
  });
  await page.goto("/exchange");
  const region = page.getByRole("region", { name: "Buy through NEAR Intents" });
  const retry = region.getByRole("button", { name: "Retry the same purchase" });
  await expect(retry).toBeEnabled();
  await retry.click();
  await expect.poll(() => sent).toBe(recovered);
});
