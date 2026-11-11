import { defineConfig, devices } from "@playwright/test";

const PORT = Number(process.env.MNEMOS_WEB_PORT ?? 3000);
// The browser, the web app and the broker have to share a host, because the
// session cookie is set by the web app and read by the broker. "localhost"
// everywhere is the documented setup.
const baseURL = process.env.MNEMOS_WEB_URL ?? `http://localhost:${PORT}`;

export default defineConfig({
  testDir: "./e2e",
  timeout: 45_000,
  expect: { timeout: 10_000 },
  fullyParallel: false,
  workers: 1,
  reporter: [["list"]],
  use: {
    baseURL,
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
  },
  projects: [
    {
      name: "desktop-1440",
      use: { ...devices["Desktop Chrome"], viewport: { width: 1440, height: 900 } },
    },
    {
      name: "tablet-768",
      use: { ...devices["Desktop Chrome"], viewport: { width: 768, height: 1024 } },
    },
    {
      name: "mobile-390",
      use: { ...devices["Pixel 7"], viewport: { width: 390, height: 844 } },
    },
  ],
  webServer: {
    command: "pnpm build && pnpm start",
    url: baseURL,
    reuseExistingServer: true,
    timeout: 240_000,
    env: {
      NEXT_PUBLIC_BROKER_URL: process.env.NEXT_PUBLIC_BROKER_URL ?? "http://127.0.0.1:8000",
    },
  },
});
