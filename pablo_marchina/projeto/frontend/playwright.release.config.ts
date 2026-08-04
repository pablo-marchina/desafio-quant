import { defineConfig, devices } from "@playwright/test";
import path from "node:path";
import { fileURLToPath } from "node:url";

const frontendRoot = path.dirname(fileURLToPath(import.meta.url));
const repositoryRoot = path.resolve(frontendRoot, "..");

export default defineConfig({
  testDir: path.join(repositoryRoot, "tests", "e2e"),
  timeout: 120_000,
  expect: {
    timeout: 30_000,
  },
  fullyParallel: false,
  retries: 0,
  reporter: [
    ["list"],
    ["html", { open: "never", outputFolder: "release-playwright-report" }],
  ],
  outputDir: "release-test-results",
  use: {
    baseURL: "http://127.0.0.1:3000",
    trace: "on",
    screenshot: "on",
    video: "retain-on-failure",
  },
  projects: [
    {
      name: "chromium-release",
      use: {
        ...devices["Desktop Chrome"],
        viewport: { width: 1440, height: 1000 },
      },
    },
  ],
});
