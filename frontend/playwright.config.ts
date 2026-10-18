import { defineConfig, devices } from "@playwright/test";

// Runs against a stack that is already up (docker compose), not a dev server: the point is
// to exercise the real build behind nginx, the real API and Postgres together.
export default defineConfig({
  testDir: "./e2e",
  fullyParallel: false,
  forbidOnly: Boolean(process.env.CI),
  retries: process.env.CI ? 1 : 0,
  reporter: process.env.CI ? [["list"], ["html", { open: "never" }]] : "list",
  use: {
    baseURL: process.env.E2E_BASE_URL ?? "http://localhost:8080",
    trace: "retain-on-failure",
    // For machines where Playwright can't download its own Chromium build.
    launchOptions: { executablePath: process.env.E2E_CHROMIUM_PATH },
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
});
