import { expect, test } from "@playwright/test";

/**
 * Responsive guard.
 *
 * The screens are checked at every width a device actually uses, from the
 * narrowest phone to a large desktop. Two things must hold everywhere: the
 * page never scrolls sideways, and no text is cut off without a way to read
 * it.
 */

const WIDTHS = [320, 360, 390, 414, 480, 540, 640, 768, 834, 1024, 1280, 1440, 1920];

const PATHS = ["/", "/setup", "/vault", "/grants", "/activity", "/earnings", "/redteam"];

async function signIn(page: import("@playwright/test").Page): Promise<void> {
  await page.goto("/setup");
  await page.waitForSelector("body[data-hydrated='true']", { timeout: 20_000 });
  const demo = page.getByRole("button", { name: "Use local demo signer" });
  if ((await demo.count()) > 0) {
    await demo.click();
    await page.waitForTimeout(1_200);
  }
}

for (const width of WIDTHS) {
  test(`nothing overflows or is cut off at ${width} pixels`, async ({ page }) => {
    await page.setViewportSize({ width, height: 900 });
    await signIn(page);

    for (const path of PATHS) {
      await page.goto(path, { waitUntil: "networkidle" });
      const report = await page.evaluate(() => {
        const limit = document.documentElement.clientWidth;
        const overflow: string[] = [];
        const clipped: string[] = [];
        for (const element of Array.from(document.querySelectorAll("body *"))) {
          const rect = element.getBoundingClientRect();
          if (rect.width === 0 || rect.height === 0) continue;
          const style = getComputedStyle(element);
          const className = element.className;
          if (className.includes("sr-only")) continue;
          if (style.overflowX === "auto" || style.overflowX === "scroll") continue;
          if (rect.right > limit + 1 || rect.left < -1) {
            overflow.push(`${element.tagName.toLowerCase()}.${className.slice(0, 60)}`);
          }
          if (
            element.children.length === 0 &&
            element.textContent.trim().length > 0 &&
            element.scrollWidth > element.clientWidth + 2 &&
            style.overflow === "hidden" &&
            element.getAttribute("title") === null
          ) {
            clipped.push(
              `${element.tagName.toLowerCase()}.${className.slice(0, 60)} "${element.textContent.trim().slice(0, 30)}"`,
            );
          }
        }
        return {
          scrollWidth: document.documentElement.scrollWidth,
          clientWidth: limit,
          overflow: [...new Set(overflow)],
          clipped: [...new Set(clipped)],
        };
      });

      expect(report.scrollWidth, `${path} scrolls sideways`).toBeLessThanOrEqual(
        report.clientWidth + 1,
      );
      expect(report.overflow, `${path} overflows`).toEqual([]);
      expect(report.clipped, `${path} cuts text off`).toEqual([]);
    }
  });
}

test("the ledger tables become a stack of records on a phone", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await signIn(page);
  await page.goto("/earnings", { waitUntil: "networkidle" });

  const table = page.locator("section[aria-labelledby=history] table");
  await expect(table).toBeHidden();

  const records = page.locator("section[aria-labelledby=history] ul li");
  await expect(records.first()).toBeVisible();
  await expect(records.first()).toContainText("NEAR");
});

test("every control is reachable by touch", async ({ page }) => {
  await page.setViewportSize({ width: 360, height: 800 });
  await signIn(page);
  await page.goto("/grants", { waitUntil: "networkidle" });

  const small = await page.evaluate(() => {
    const results: string[] = [];
    for (const element of Array.from(
      document.querySelectorAll("a, button, select, input:not([type=hidden]), textarea"),
    )) {
      const rect = element.getBoundingClientRect();
      if (rect.width === 0 || rect.height === 0) continue;
      if (element.className.includes("sr-only")) continue;
      if (rect.height < 30 || rect.width < 24) {
        results.push(
          `${element.tagName.toLowerCase()}.${element.className.slice(0, 40)} ${Math.round(rect.width)}x${Math.round(rect.height)}`,
        );
      }
    }
    return results;
  });
  expect(small).toEqual([]);
});
