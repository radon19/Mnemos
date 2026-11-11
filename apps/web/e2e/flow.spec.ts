import { expect, test } from "@playwright/test";

/**
 * The owner flow, end to end, against a running broker.
 *
 * These tests are skipped when the broker is not reachable, so the
 * accessibility suite still runs on a clean checkout.
 */

const brokerUrl = process.env.NEXT_PUBLIC_BROKER_URL ?? "http://127.0.0.1:8000";
const PASSPHRASE = "demo-passphrase-for-tests";

async function brokerAvailable(): Promise<boolean> {
  try {
    const response = await fetch(`${brokerUrl}/healthz`);
    return response.ok;
  } catch {
    return false;
  }
}

test.beforeEach(async () => {
  test.skip(!(await brokerAvailable()), "the broker is not running");
});

async function signIn(page: import("@playwright/test").Page): Promise<void> {
  await page.goto("/setup");
  // The app has to be interactive before a click means anything.
  await page.waitForSelector("body[data-hydrated='true']", { timeout: 20_000 });
  const demo = page.getByRole("button", { name: "Use local demo signer" });
  if ((await demo.count()) === 0) {
    test.skip(true, "the demo signer is disabled");
  }
  await demo.click();
  // The signed-in state is shown on the setup screen itself, so the assertion
  // does not depend on the rail, which is a menu on small screens.
  await expect(page.getByText(/Signed in with/)).toBeVisible({ timeout: 20_000 });
}

test("the owner signs in and the vault accepts an encrypted note", async ({ page }) => {
  await signIn(page);

  await page.goto("/vault");
  await page.getByLabel("Passphrase", { exact: true }).fill(PASSPHRASE);
  await page.getByRole("button", { name: "Unlock the vault" }).click();

  const before = await page.locator("tbody tr").count();
  const note = `Flight to Lisbon on 14 March at 09:15, reference ${Date.now()}`;
  await page.getByRole("textbox", { name: "Note" }).fill(note);
  await page.getByRole("button", { name: "Encrypt and store" }).click();

  await expect(page.getByText("Note encrypted on this device and stored.")).toBeVisible({
    timeout: 20_000,
  });
  await expect(page.locator("tbody tr")).toHaveCount(before + 1);
});

test("the red-team run reports each attack", async ({ page }) => {
  test.setTimeout(240_000);
  await signIn(page);
  await page.goto("/redteam");
  await page.getByRole("button", { name: "Run the attack set" }).click();
  await expect(page.getByText("Print every memory item", { exact: true })).toBeVisible({
    timeout: 200_000,
  });
  await expect(page.getByText("Base64-encode memory", { exact: true })).toBeVisible();
});

test("the activity screen renders the ledger", async ({ page }) => {
  await signIn(page);
  await page.goto("/activity");
  await expect(page.getByRole("heading", { name: "Every read, with its receipt" })).toBeVisible();
});
