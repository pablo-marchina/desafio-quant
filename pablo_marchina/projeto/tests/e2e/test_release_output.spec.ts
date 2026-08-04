import { expect, test } from "@playwright/test";

const workflowId = process.env.RELEASE_WORKFLOW_ID?.trim() ?? "";

test.skip(!workflowId, "RELEASE_WORKFLOW_ID is required only for production release validation.");

test("production frontend presents the validated end-to-end RAG result", async ({ page }) => {
  const consoleErrors: string[] = [];
  const pageErrors: string[] = [];

  page.on("console", (message) => {
    if (message.type() !== "error") return;
    const value = message.text();
    if (value.includes("favicon.ico")) return;
    consoleErrors.push(value);
  });
  page.on("pageerror", (error) => pageErrors.push(error.message));

  await page.goto("/", { waitUntil: "networkidle" });
  await expect(page.getByText("NVIDIA Startup AI Radar")).toBeVisible();
  await expect(page.locator("body")).not.toHaveText(/Failed to fetch|Unexpected Application Error/i);
  await expect(page.locator(".vite-error-overlay, #webpack-dev-server-client-overlay")).toHaveCount(0);

  await page.getByRole("button", { name: "Workflow", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Workflow Runs" })).toBeVisible();

  const workflowRow = page
    .getByRole("row")
    .filter({ hasText: workflowId.slice(0, 12) })
    .first();
  await expect(workflowRow).toBeVisible({ timeout: 60_000 });
  await workflowRow.getByRole("button", { name: "Final Result" }).click();

  await expect(page.getByRole("heading", { name: "Final Pipeline Result" })).toBeVisible();
  const statusTile = page.locator(".summary-tile").filter({ hasText: "Workflow status" });
  await expect(statusTile).toContainText(/completed|awaiting_review/i, { timeout: 60_000 });
  await expect(statusTile).not.toContainText(/failed|cancelled|blocked/i);

  const recommendationPanel = page
    .locator(".priority-panel")
    .filter({ hasText: "NVIDIA recommendation ranking" });
  await expect(recommendationPanel).toBeVisible();
  const recommendationCards = recommendationPanel.locator(".recommendation-card");
  const recommendationCount = await recommendationCards.count();
  expect(recommendationCount).toBeGreaterThan(0);
  expect(recommendationCount).toBeLessThanOrEqual(2);
  await expect(recommendationPanel.getByText("TensorRT", { exact: true }).first()).toBeVisible();
  await expect(recommendationPanel).not.toContainText(/Clara|MONAI|Riva|Isaac|Morpheus/i);
  for (let index = 0; index < recommendationCount; index += 1) {
    const card = recommendationCards.nth(index);
    await expect(card).toContainText("Evidence support");
    await expect(card).toContainText("RAG support");
    await expect(card).toContainText("Production allowed");
    await expect(card).not.toContainText(/No reasoning persisted/i);
  }

  const evidencePanel = page
    .locator(".priority-panel")
    .filter({ hasText: "Evidence matrix" });
  await expect(evidencePanel).toBeVisible();
  expect(await evidencePanel.locator("tbody tr").count()).toBeGreaterThan(0);
  await expect(evidencePanel).toContainText(/Supported|Critical supported/);

  const technicalPanel = page
    .locator(".priority-panel")
    .filter({ hasText: "Technical gaps and NVIDIA context" });
  await expect(technicalPanel).toBeVisible();
  const gapTable = technicalPanel.locator("table").first();
  await expect(gapTable).toContainText("computer_vision_gap");
  await expect(gapTable).not.toContainText(
    /genai_llm_gap|cybersecurity_ai_gap|data_pipeline_gap|training_scalability_gap|nvidia_ecosystem_fit_gap/i,
  );
  const ragTable = technicalPanel.locator("table.rag-context-table");
  expect(await ragTable.locator("tbody tr").count()).toBeGreaterThan(0);
  await expect(ragTable).toContainText(/TensorRT/i);
  await expect(ragTable).not.toContainText("No snippet persisted.");

  const qualityPanel = page.locator(".panel").filter({ hasText: "Quality gates and runtime trace" });
  await expect(qualityPanel).toBeVisible();
  const pipelineQuality = qualityPanel.locator(".evidence-mini-grid > div").filter({ hasText: "Pipeline quality gate" });
  await expect(pipelineQuality).toContainText("passed");
  const retrievalMode = qualityPanel.locator(".evidence-mini-grid > div").filter({ hasText: "RAG retrieval mode" });
  await expect(retrievalMode).toContainText("bm25_graphrag_qdrant_triton_rerank");
  const graphRag = qualityPanel.locator(".evidence-mini-grid > div").filter({ hasText: "GraphRAG" });
  await expect(graphRag).toContainText("true");
  const triton = qualityPanel.locator(".evidence-mini-grid > div").filter({ hasText: "Triton rerank" });
  await expect(triton).toContainText("true");

  await expect(page.locator(".error-message")).toHaveCount(0);
  const bodyHasHorizontalOverflow = await page.evaluate(
    () => document.documentElement.scrollWidth > document.documentElement.clientWidth + 2,
  );
  expect(bodyHasHorizontalOverflow).toBe(false);

  await page.screenshot({
    path: "release-test-results/release-frontend.png",
    fullPage: true,
  });

  expect(pageErrors).toEqual([]);
  expect(consoleErrors).toEqual([]);
});
