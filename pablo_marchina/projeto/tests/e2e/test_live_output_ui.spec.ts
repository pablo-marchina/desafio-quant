import { expect, test } from "@playwright/test";
import fs from "node:fs";
import path from "node:path";

type CompanyResult = {
  company: string;
  workflow_id?: string;
  top_technologies?: string[];
};

type LiveReport = {
  companies: CompanyResult[];
};

const reportPath = process.env.LIVE_VALIDATION_REPORT
  ?? path.resolve(process.cwd(), "../final_case_evidence/live_output_validation_report.json");
const report = JSON.parse(fs.readFileSync(reportPath, "utf8")) as LiveReport;
const target = report.companies.find((item) => item.workflow_id && (item.top_technologies?.length ?? 0) > 0);

if (!target?.workflow_id) {
  throw new Error("Live validation report has no workflow output suitable for UI verification.");
}

test("real persisted workflow output is presented in the final cockpit", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("button", { name: "Workflow" }).click();
  const workflowPrefix = `${target.workflow_id.slice(0, 12)}...`;
  const row = page.getByRole("row").filter({ hasText: workflowPrefix });
  await expect(row).toBeVisible({ timeout: 30_000 });
  await row.getByRole("button", { name: "Final Result" }).click();

  await expect(page.getByRole("heading", { name: "Final Pipeline Result" })).toBeVisible({ timeout: 30_000 });
  await expect(page.getByText(target.company, { exact: false }).first()).toBeVisible();
  await expect(page.getByRole("heading", { name: /NVIDIA recommendation ranking/i })).toBeVisible();
  await expect(page.getByRole("heading", { name: /Evidence matrix/i })).toBeVisible();
  await expect(page.getByRole("heading", { name: /Technical gaps and NVIDIA context/i })).toBeVisible();
  await expect(page.getByRole("heading", { name: /Quality gates and runtime trace/i })).toBeVisible();

  const topTechnology = target.top_technologies?.[0];
  if (topTechnology) {
    await expect(page.getByText(topTechnology, { exact: false }).first()).toBeVisible();
  }
});
