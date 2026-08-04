import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import userEvent from "@testing-library/user-event";

import { listUrlIngestionJobs } from "@/lib/api/radar-client";

import { JobHistory } from "./job-history";

vi.mock("@/lib/api/radar-client");
const mockedListUrlIngestionJobs = vi.mocked(listUrlIngestionJobs);

function renderWithClient(children: ReactNode) {
  return render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>{children}</QueryClientProvider>);
}

const baseJob = {
  id: "job-1", url: "https://acme.example.com", source_type: "startup_evidence", status: "completed" as const,
  scraping_job_id: null, scraping_result_id: null, ingestion_job_id: null, document_id: null, embedding_job_id: null,
  startup_id: "startup-1", parent_job_id: null, enrichment_round: 0, recommendation_count: 2, briefing_id: "briefing-1", error_message: null,
  created_at: "2026-06-24T10:00:00Z", started_at: null, finished_at: null,
};

describe("JobHistory", () => {
  beforeEach(() => vi.resetAllMocks());

  it("exibe a lista de jobs e o total do historico", async () => {
    mockedListUrlIngestionJobs.mockResolvedValue({ items: [baseJob], total: 1, page: 1, page_size: 15 });

    renderWithClient(<JobHistory />);

    expect(await screen.findByText("https://acme.example.com")).toBeInTheDocument();
    expect(screen.getByText("1 job no historico")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /acme\.example\.com/i })).toHaveAttribute("href", "/jobs/job-1");
  });

  it("mostra estado vazio quando nenhum job corresponde aos filtros", async () => {
    mockedListUrlIngestionJobs.mockResolvedValue({ items: [], total: 0, page: 1, page_size: 15 });

    renderWithClient(<JobHistory />);

    expect(await screen.findByText(/nenhum job corresponde/i)).toBeInTheDocument();
  });

  it("envia os filtros e reinicia a pagina", async () => {
    const user = userEvent.setup();
    mockedListUrlIngestionJobs.mockResolvedValue({ items: [], total: 0, page: 1, page_size: 15 });

    renderWithClient(<JobHistory />);
    await screen.findByText(/nenhum job corresponde/i);
    await user.selectOptions(screen.getByLabelText("Filtrar por status"), "completed");
    await user.type(screen.getByLabelText("Filtrar por tipo de fonte"), "nvidia_knowledge");

    await waitFor(() => expect(mockedListUrlIngestionJobs).toHaveBeenLastCalledWith({
      page: 1, page_size: 15, status: "completed", source_type: "nvidia_knowledge",
    }));
  });
});
