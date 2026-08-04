import { defineConfig, devices } from "@playwright/test";
import Module from "node:module";
import path from "node:path";
import { fileURLToPath } from "node:url";

const frontendRoot = path.dirname(fileURLToPath(import.meta.url));
const repoRoot = path.resolve(frontendRoot, "..");
const mockApi = process.env.PLAYWRIGHT_MOCK_API === "true";
const reuseExistingServers = !process.env.CI || process.env.PLAYWRIGHT_REUSE_EXISTING_SERVERS === "true";
process.env.NODE_PATH = path.join(frontendRoot, "node_modules");
(Module as typeof Module & { _initPaths: () => void })._initPaths();

const webServer = [
  ...(!mockApi
    ? [
        {
          command: "python -m uvicorn src.api.main:app --host 127.0.0.1 --port 8000",
          cwd: repoRoot,
          url: "http://127.0.0.1:8000/health/product",
          reuseExistingServer: reuseExistingServers,
          timeout: 120_000,
          env: {
            ...process.env,
            APP_MODE: process.env.APP_MODE || "development",
            PRODUCT_DB_URL:
              process.env.PRODUCT_DB_URL ||
              `sqlite:///${path.join(repoRoot, "data", "product", "playwright.db").replaceAll("\\", "/")}`,
            CORS_ALLOWED_ORIGINS:
              process.env.CORS_ALLOWED_ORIGINS || "http://127.0.0.1:5173,http://localhost:5173",
            RAG_REQUIRED_FOR_PRODUCT: process.env.RAG_REQUIRED_FOR_PRODUCT || "false",
          },
        },
      ]
    : []),
  {
    command: "node node_modules/vite/bin/vite.js --host 127.0.0.1 --port 5173",
    cwd: frontendRoot,
    url: "http://127.0.0.1:5173",
    reuseExistingServer: reuseExistingServers,
    timeout: 120_000,
  },
];

export default defineConfig({
  testDir: path.join(repoRoot, "tests", "e2e"),
  timeout: 90_000,
  expect: {
    timeout: 10_000,
  },
  fullyParallel: false,
  retries: process.env.CI ? 1 : 0,
  reporter: [["list"], ["html", { open: "never", outputFolder: "playwright-report" }]],
  use: {
    baseURL: "http://127.0.0.1:5173",
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
    video: "retain-on-failure",
  },
  webServer,
  projects: [
    {
      name: "chromium",
      use: {
        ...devices["Desktop Chrome"],
      },
    },
  ],
});
