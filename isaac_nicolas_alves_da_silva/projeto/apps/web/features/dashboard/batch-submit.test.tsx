import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { createBatchUrlIngestionJobs } from "@/lib/api/radar-client";
import { BatchSubmit } from "./batch-submit";

vi.mock("@/lib/api/radar-client");
const mockedBatch = vi.mocked(createBatchUrlIngestionJobs);

describe("BatchSubmit", () => {
  beforeEach(() => vi.resetAllMocks());

  it("botão fica desabilitado quando não há URLs válidas", () => {
    render(<BatchSubmit />);
    expect(screen.getByRole("button")).toBeDisabled();
  });

  it("detecta URLs separadas por linha e habilita o botão", async () => {
    const user = userEvent.setup();
    render(<BatchSubmit />);

    await user.type(
      screen.getByRole("textbox"),
      "https://startup1.com{Enter}https://startup2.io"
    );

    await waitFor(() =>
      expect(screen.getByRole("button")).toHaveTextContent("Analisar 2 URLs")
    );
    expect(screen.getByRole("button")).not.toBeDisabled();
  });

  it("exibe links para os jobs criados após submissão bem-sucedida", async () => {
    const user = userEvent.setup();
    mockedBatch.mockResolvedValue([
      {
        url: "https://startup1.com",
        job: {
          id: "job-abc",
          url: "https://startup1.com",
          source_type: "startup_evidence",
          status: "pending",
          scraping_job_id: null,
          scraping_result_id: null,
          ingestion_job_id: null,
          document_id: null,
          embedding_job_id: null,
          startup_id: null,
          parent_job_id: null,
          enrichment_round: 0,
          recommendation_count: null,
          briefing_id: null,
          error_message: null,
          created_at: "2026-06-25T10:00:00Z",
          started_at: null,
          finished_at: null,
        },
        error: null,
      },
    ]);

    render(<BatchSubmit />);
    await user.type(screen.getByRole("textbox"), "https://startup1.com");
    await user.click(screen.getByRole("button"));

    expect(await screen.findByRole("link", { name: /Ver job/i })).toHaveAttribute(
      "href",
      "/jobs/job-abc"
    );
  });
});
