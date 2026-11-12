import { chromium } from "@playwright/test";

const BASE = process.argv[2] ?? "http://localhost:3000";
const widths = [320, 360, 390, 414, 480, 540, 640, 768, 834, 1024, 1280, 1440, 1920];
const paths = ["/", "/setup", "/vault", "/grants", "/activity", "/earnings", "/redteam"];

const browser = await chromium.launch();
let problems = 0;

for (const width of widths) {
  const page = await browser.newPage({ viewport: { width, height: 900 } });
  // Sign in so the screens carry their real content.
  await page.goto(`${BASE}/setup`, { waitUntil: "networkidle" });
  await page.waitForSelector("body[data-hydrated='true']", { timeout: 20_000 });
  const demo = page.getByRole("button", { name: "Use local demo signer" });
  if ((await demo.count()) > 0) {
    await demo.click();
    await page.waitForTimeout(1200);
  }

  for (const path of paths) {
    await page.goto(`${BASE}${path}`, { waitUntil: "networkidle" });
    await page.waitForTimeout(400);
    const report = await page.evaluate(() => {
      const limit = document.documentElement.clientWidth;
      const overflow = [];
      const clipped = [];
      const small = [];
      const overlaps = [];
      for (const element of Array.from(document.querySelectorAll("body *"))) {
        const rect = element.getBoundingClientRect();
        if (rect.width === 0 || rect.height === 0) continue;
        const style = getComputedStyle(element);
        const className = String(element.className);
        if (className.includes("sr-only")) continue;
        if (style.overflowX === "auto" || style.overflowX === "scroll") continue;
        if (rect.right > limit + 1 || rect.left < -1) {
          overflow.push(
            `${element.tagName.toLowerCase()}.${className.slice(0, 50)} r=${Math.round(rect.right)}`,
          );
        }
        if (
          element.children.length === 0 &&
          (element.textContent ?? "").trim().length > 0 &&
          element.scrollWidth > element.clientWidth + 2 &&
          style.overflow === "hidden"
        ) {
          clipped.push(
            `${element.tagName.toLowerCase()}.${className.slice(0, 50)} "${(element.textContent ?? "").trim().slice(0, 30)}"`,
          );
        }
      }
      for (const element of Array.from(
        document.querySelectorAll("a, button, select, input:not([type=hidden]), textarea"),
      )) {
        const rect = element.getBoundingClientRect();
        if (rect.width === 0 || rect.height === 0) continue;
        if (String(element.className).includes("sr-only")) continue;
        if (rect.height < 30 || rect.width < 24) {
          small.push(
            `${element.tagName.toLowerCase()}.${String(element.className).slice(0, 40)} ${Math.round(rect.width)}x${Math.round(rect.height)}`,
          );
        }
      }
      return {
        scrollWidth: document.documentElement.scrollWidth,
        clientWidth: limit,
        overflow: [...new Set(overflow)].slice(0, 4),
        clipped: [...new Set(clipped)].slice(0, 4),
        small: [...new Set(small)].slice(0, 3),
      };
    });
    const pageScrolls = report.scrollWidth > report.clientWidth + 1;
    if (pageScrolls || report.overflow.length > 0 || report.clipped.length > 0) {
      problems += 1;
      console.log(`\n${path} @ ${width}px  scrollWidth=${report.scrollWidth} client=${report.clientWidth}`);
      for (const item of report.overflow) console.log(`  overflow: ${item}`);
      for (const item of report.clipped) console.log(`  clipped:  ${item}`);
    }
    if (width <= 414 && report.small.length > 0) {
      console.log(`  small target @${width} ${path}: ${report.small.join(" | ")}`);
    }
  }
  await page.close();
}
await browser.close();
console.log(`\nscreens with problems: ${problems}`);
