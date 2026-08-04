import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { createUrlIngestionJob } from "@/lib/api/radar-client";

import { UrlSubmissionForm } from "./url-submission-form";

vi.mock("@/lib/api/radar-client");

const mockedPush = vi.fn();
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: mockedPush }),
}));

const mockedCreateJob = vi.mocked(createUrlIngestionJob);

function renderWithClient(children: ReactNode) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>,
  );
}

beforeEach(() => {
  vi.resetAllMocks();
});

describe("UrlSubmissionForm", () => {
  it("envia a URL digitada e navega para a pagina do job ao concluir", async () => {
    const user = userEvent.setup();
    mockedCreateJob.mockResolvedValue({
      id: "job-1",
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
    });

    renderWithClient(<UrlSubmissionForm />);

    await user.type(screen.getByLabelText(/url publica da startup/i), "https://acme.example.com");
    await user.click(screen.getByRole("button", { name: /iniciar analise/i }));

    // TanStack Query v5 chama mutationFn com um 2o argumento de contexto
    // ({ client, meta, mutationKey }) - verificar so o 1o argumento.
    await waitFor(() =>
      expect(mockedCreateJob.mock.calls[0]?.[0]).toEqual({
        url: "https://acme.example.com",
      }),
    );
    await waitFor(() => expect(mockedPush).toHaveBeenCalledWith("/jobs/job-1"));
  });

  it("mostra mensagem de erro quando a criacao do job falha", async () => {
    const user = userEvent.setup();
    mockedCreateJob.mockRejectedValue(new Error("URL invalida"));

    renderWithClient(<UrlSubmissionForm />);

    await user.type(screen.getByLabelText(/url publica da startup/i), "https://acme.example.com");
    await user.click(screen.getByRole("button", { name: /iniciar analise/i }));

    expect(await screen.findByText("URL invalida")).toBeInTheDocument();
  });
});
