import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "@playwright/test";

/**
 * Accessibility and layout checks.
 *
 * Every screen is checked for automated accessibility violations at 390, 768
 * and 1440 pixels. The axe rules are the ones that catch real defects:
 * colour contrast, names, roles, landmarks and keyboard traps.
 */

async function analyse(page: Page): Promise<void> {
  const results = await new AxeBuilder({ page }).analyze();
  const violations = results.violations.map((violation) => ({
    id: violation.id,
    impact: violation.impact,
    nodes: violation.nodes.map((node) => node.target.join(" ")),
  }));
  expect(violations, JSON.stringify(violations, null, 2)).toEqual([]);
}

const SCREENS = [
  { path: "/", name: "landing" },
  { path: "/setup", name: "setup" },
  { path: "/vault", name: "vault" },
  { path: "/grants", name: "grants" },
  { path: "/activity", name: "activity" },
  { path: "/earnings", name: "earnings" },
  { path: "/redteam", name: "red-team" },
];

for (const screen of SCREENS) {
  test(`${screen.name} has no automated accessibility violations`, async ({ page }) => {
    await page.goto(screen.path);
    await expect(page.locator("main")).toBeVisible();
    await analyse(page);
  });
}

test("the page does not scroll sideways at 390 pixels", async ({ page }) => {
  await page.goto("/setup");
  const overflow = await page.evaluate(() => {
    return document.documentElement.scrollWidth - document.documentElement.clientWidth;
  });
  expect(overflow).toBeLessThanOrEqual(1);
});

test("the navigation reaches every screen from the rail", async ({ page }) => {
  // Six client-side navigations, each opening the menu on a narrow screen.
  test.setTimeout(90_000);
  await page.goto("/");
  for (const screen of SCREENS.slice(1)) {
    const navs = page.getByRole("navigation", { name: "Sections" });
    if ((await navs.filter({ visible: true }).count()) === 0) {
      await page.getByRole("button", { name: "Menu" }).click();
    }
    const visible = page.getByRole("navigation", { name: "Sections" }).filter({ visible: true });
    await visible.getByRole("link", { name: new RegExp(screen.name, "i") }).click();
    await expect(page).toHaveURL(new RegExp(`${screen.path}$`), { timeout: 15_000 });
    await expect(page.locator("h1")).toBeVisible();
  }
});
