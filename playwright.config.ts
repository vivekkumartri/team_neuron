import { defineConfig, devices } from "@playwright/test";

/**
 * Runs against the Next.js static-export shell served by `next dev web` in
 * this repo's CI job. Browser binaries could not be installed in the
 * sandbox this config was authored in (no sudo for OS deps, no persistent
 * download cache across sandbox commands — see task.md Task 4H.1's status
 * note) so these specs are unrun here; a normal CI runner with
 * `npx playwright install --with-deps chromium` will execute them.
 */
export default defineConfig({
  testDir: "tests/e2e",
  timeout: 30_000,
  fullyParallel: true,
  retries: 0,
  webServer: {
    command: "npm run dev",
    port: 3000,
    reuseExistingServer: !process.env.CI,
    timeout: 60_000,
  },
  use: {
    baseURL: "http://localhost:3000",
    trace: "retain-on-failure",
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
});
