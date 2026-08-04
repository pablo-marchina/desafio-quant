import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { getStartup, listRecommendations, listStartups } from "@/lib/api/radar-client";
import type { Recommendation, Startup } from "@/lib/api/radar-types";

import { StartupCompare } from "./startup-compare";

vi.mock("@/lib/api/radar-client");

const mockedListStartups = vi.mocked(listStartups);
const mockedGetStartup = vi.mocked(getStartup);
const mockedListRecommendations = vi.mocked(listRecommendations);

function startup(overrides: Partial<Startup>): Startup {
  return {
    id: "startup-1",
    name: "Acme AI",
    website_url: "https://acme.ai",
    description: null,
    sector: "Legal AI",
    country: "BR",
    ai_maturity_level: "ai_native",
    classification_reason: null,
    classified_at: null,
    founders: [],
    funding_stage: null,
    funding_amount_usd: null,
    customers: [],
    ai_profile: null,
    field_confidence: {},
    field_evidence_ids: {},
    created_at: "2026-06-01T00:00:00Z",
    updated_at: "2026-06-01T00:00:00Z",
    ...overrides,
  };
}

function recommendation(overrides: Partial<Recommendation>): Recommendation {
  return {
    id: "rec-1",
    startup_id: "startup-1",
    technology_slug: "nvidia-nim",
    technology_name: "NVIDIA NIM",
    category: "model_serving",
    score: 0.73,
    confidence: 0.75,
    complexity: "low",
    priority: 1,
    justification: "Fit para serving de modelos.",
    matched_keywords: [],
    evidence_ids: [],
    signal_origins: [],
    missing_signals: [],
    nivel: "forte",
    faltando: [],
    review_status: "pending",
    review_comment: null,
    reviewed_by: null,
    reviewed_at: null,
    created_at: "2026-06-01T00:00:00Z",
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

describe("StartupCompare", () => {
  beforeEach(() => {
    vi.resetAllMocks();
    mockedListStartups.mockResolvedValue({
      items: [
        startup({ id: "startup-1", name: "Acme AI", sector: "Legal AI" }),
        startup({ id: "startup-2", name: "Beta Vision", sector: "Computer Vision" }),
      ],
      total: 2,
      page: 1,
      page_size: 100,
    });
    mockedGetStartup.mockResolvedValue(startup({ id: "startup-1", name: "Acme AI" }));
    mockedListRecommendations.mockResolvedValue([
      recommendation({ id: "rec-1", startup_id: "startup-1", technology_name: "NVIDIA NIM" }),
    ]);
  });

  it("mostra nomes no seletor e usa o id selecionado para carregar a comparacao", async () => {
    const user = userEvent.setup();

    renderWithClient(<StartupCompare />);

    const firstSelect = screen.getByLabelText("Selecionar startup 1");
    expect(await within(firstSelect).findByRole("option", { name: "Acme AI (Legal AI - BR)" })).toBeInTheDocument();
    expect(within(firstSelect).getByRole("option", { name: "Beta Vision (Computer Vision - BR)" })).toBeInTheDocument();

    await user.selectOptions(firstSelect, "startup-1");

    expect(mockedGetStartup).toHaveBeenCalledWith("startup-1");
    expect(await screen.findByText("Acme AI")).toBeInTheDocument();
    expect(await screen.findAllByText("NVIDIA NIM")).toHaveLength(2);
  });
});
