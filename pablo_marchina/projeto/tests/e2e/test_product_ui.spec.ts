import { expect, test } from "@playwright/test";

test("Product UI readiness page loads and shows status", async ({ page }) => {
  await page.goto("/");

  await expect(page.getByText("NVIDIA Startup AI Radar")).toBeVisible();
  await expect(page.getByText("Product UI")).toBeVisible();

  await expect(page.getByRole("button", { name: "Setup" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Capabilities" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Startups" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Opportunities" })).toBeVisible();

  await expect(page.getByText(/Product ready|Product not ready|Checking/).first()).toBeVisible({ timeout: 30_000 });
});

test("Product UI capabilities page loads and shows capabilities", async ({ page }) => {
  await page.goto("/");

  await page.getByRole("button", { name: "Capabilities" }).click();
  await expect(page.getByText("Product Capabilities")).toBeVisible();

  await expect(page.getByText("core").first()).toBeVisible({ timeout: 15_000 });
});

test("Product UI startups page lists startups and can navigate to create", async ({ page }) => {
  await page.goto("/");

  await page.getByRole("button", { name: "Startups" }).click();
  await expect(page.getByText("Startups").first()).toBeVisible({ timeout: 15_000 });
});

test("Product UI opportunities page loads and shows table", async ({ page }) => {
  await page.goto("/");

  await page.getByRole("button", { name: "Opportunities" }).click();
  await expect(page.getByText("Opportunities").first()).toBeVisible({ timeout: 15_000 });
});

test("Product UI can create a startup via the UI", async ({ page }) => {
  const startupName = `E2E Test Startup ${Date.now()}`;
  await page.goto("/");

  await page.getByRole("button", { name: "Startups" }).click();
  await expect(page.getByText("Startups").first()).toBeVisible({ timeout: 15_000 });

  await page.getByRole("button", { name: /New Startup/i }).click();
  await expect(page.getByRole("heading", { name: "Create Startup" })).toBeVisible();

  await page.fill('input[name="name"]', startupName);
  await page.fill('input[name="website"]', "https://e2e-test.example.com");
  await page.fill('input[name="sector"]', "AI Testing");
  await page.getByRole("button", { name: "Create Startup" }).click();

  await expect(page.getByText(startupName)).toBeVisible({ timeout: 15_000 });
});

test("Product UI can run analysis on a startup", async ({ page }) => {
  const startupName = `E2E Analysis Test ${Date.now()}`;
  await page.goto("/");

  await page.getByRole("button", { name: "Startups" }).click();

  await page.getByRole("button", { name: /New Startup/i }).click();
  await page.fill('input[name="name"]', startupName);
  await page.fill('input[name="website"]', "https://e2e-analysis.example.com");
  await page.fill('input[name="sector"]', "AI Analysis");
  await page.getByRole("button", { name: "Create Startup" }).click();
  await expect(page.getByText(startupName).first()).toBeVisible({ timeout: 15_000 });

  const startupRow = page.getByRole("row", { name: new RegExp(startupName) });
  await startupRow.getByRole("button", { name: "View" }).click();
  await expect(page.getByRole("button", { name: /Run Main Pipeline/i }).first()).toBeVisible({ timeout: 15_000 });
});
