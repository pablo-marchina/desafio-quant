import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { getUrlIngestionJob, listUrlIngestionJobs } from "@/lib/api/radar-client";
import type { UrlIngestionJob } from "@/lib/api/radar-types";

import { JobStatusPanel } from "./job-status-panel";

vi.mock("@/lib/api/radar-client");
vi.mock("next/link", () => ({
  default: ({ children, href }: { children: ReactNode; href: string }) => (
    <a href={href}>{children}</a>
  ),
}));

const mockedGetJob = vi.mocked(getUrlIngestionJob);
const mockedListJobs = vi.mocked(listUrlIngestionJobs);

const JOB_ID = "22222222-2222-2222-2222-222222222222";

function baseJob(overrides: Partial<UrlIngestionJob> = {}): UrlIngestionJob {
  return {
    id: JOB_ID,
    url: "https://acme.example.com",
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
    created_at: "2026-06-01T00:00:00Z",
    started_at: null,
    finished_at: null,
    ...overrides,
  };
}

function renderWithClient(children: ReactNode) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>,
  );
}

beforeEach(() => {
  vi.resetAllMocks();
  mockedListJobs.mockResolvedValue({ items: [], total: 0, page: 1, page_size: 100 });
});

describe("JobStatusPanel", () => {
  it("mostra estado de carregamento", () => {
    mockedGetJob.mockReturnValue(new Promise(() => {}));

    renderWithClient(<JobStatusPanel jobId={JOB_ID} />);

    expect(screen.getByText(/carregando job/i)).toBeInTheDocument();
  });

  it("mostra mensagem de erro quando a busca falha", async () => {
    mockedGetJob.mockRejectedValue(new Error("job indisponivel"));

    renderWithClient(<JobStatusPanel jobId={JOB_ID} />);

    expect(await screen.findByText("job indisponivel")).toBeInTheDocument();
  });

  it("mostra a timeline para um job pendente", async () => {
    mockedGetJob.mockResolvedValue(baseJob({ status: "pending" }));

    renderWithClient(<JobStatusPanel jobId={JOB_ID} />);

    // "Na fila" aparece mais de uma vez (titulo + timeline + auditoria) - usar
    // getAllByText em vez de findByText (que exige match unico).
    expect(await screen.findAllByText("Na fila")).toHaveLength(3);
    expect(screen.getByText("Coletando fonte")).toBeInTheDocument();
    expect(screen.getByText("Auditoria do job")).toBeInTheDocument();
    expect(screen.getByText("Familia do job")).toBeInTheDocument();
  });

  it("mostra a mensagem de erro para um job falho", async () => {
    mockedGetJob.mockResolvedValue(
      baseJob({ status: "failed", error_message: "scraping rejeitado" }),
    );

    renderWithClient(<JobStatusPanel jobId={JOB_ID} />);

    expect(await screen.findByText("scraping rejeitado")).toBeInTheDocument();
  });

  it("continua mostrando progresso quando o job raiz falhou mas ha enriquecimento rodando", async () => {
    mockedGetJob.mockResolvedValue(
      baseJob({ status: "failed", error_message: "fonte inicial rejeitada" }),
    );
    mockedListJobs.mockResolvedValue({
      items: [
        baseJob({
          id: "child-1",
          url: "https://news.example.com/acme",
          status: "embedding",
          parent_job_id: JOB_ID,
          enrichment_round: 1,
          startup_id: "startup-1",
        }),
      ],
      total: 1,
      page: 1,
      page_size: 100,
    });

    renderWithClient(<JobStatusPanel jobId={JOB_ID} />);

    expect(await screen.findByText(/fonte inicial foi rejeitada/i)).toBeInTheDocument();
    expect(screen.getAllByText("Indexando conhecimento")).toHaveLength(3);
    expect(screen.queryByText("fonte inicial rejeitada")).not.toBeInTheDocument();
  });

  it("mostra link para o resultado quando o job conclui com startup_id", async () => {
    mockedGetJob.mockResolvedValue(
      baseJob({ status: "completed", startup_id: "startup-1" }),
    );

    renderWithClient(<JobStatusPanel jobId={JOB_ID} />);

    const link = await screen.findByRole("link", { name: /ver resultado da startup/i });
    expect(link).toHaveAttribute("href", "/startups/startup-1");
  });
});
