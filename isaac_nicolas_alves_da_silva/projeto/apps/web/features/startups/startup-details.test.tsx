import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import {
  getStartup,
  getStartupEvidences,
  listBriefings,
  listRecommendations,
  refreshStartupAnalysis,
  reviewRecommendation,
} from "@/lib/api/radar-client";
import type { Briefing, Recommendation, Startup, StartupEvidence } from "@/lib/api/radar-types";

import { StartupDetails } from "./startup-details";

vi.mock("@/lib/api/radar-client");

const mockedGetStartup = vi.mocked(getStartup);
const mockedGetEvidences = vi.mocked(getStartupEvidences);
const mockedListRecommendations = vi.mocked(listRecommendations);
const mockedListBriefings = vi.mocked(listBriefings);
const mockedRefresh = vi.mocked(refreshStartupAnalysis);
const mockedReviewRecommendation = vi.mocked(reviewRecommendation);

const STARTUP_ID = "11111111-1111-1111-1111-111111111111";

function baseStartup(overrides: Partial<Startup> = {}): Startup {
  return {
    id: STARTUP_ID,
    name: "Acme AI",
    website_url: "https://acme.example.com",
    description: "Plataforma de IA generativa para atendimento.",
    sector: "fintech",
    country: "BR",
    ai_maturity_level: "ai_native",
    classification_reason: null,
    classified_at: null,
    founders: ["Ana Silva"],
    funding_stage: "seed",
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

function baseRecommendation(overrides: Partial<Recommendation> = {}): Recommendation {
  return {
    id: "rec-1",
    startup_id: STARTUP_ID,
    technology_slug: "nim",
    technology_name: "NVIDIA NIM",
    category: "inference",
    score: 0.8,
    confidence: 0.7,
    complexity: "medium",
    priority: 1,
    justification: "Evidencias mencionam inferencia de modelos.",
    matched_keywords: [],
    evidence_ids: [],
    signal_origins: [],
    missing_signals: [],
    nivel: "exploratoria",
    faltando: [],
    review_status: "pending",
    review_comment: null,
    reviewed_by: null,
    reviewed_at: null,
    created_at: "2026-06-01T00:00:00Z",
    ...overrides,
  };
}

function baseBriefing(overrides: Partial<Briefing> = {}): Briefing {
  return {
    id: "brief-1",
    startup_id: STARTUP_ID,
    content: "# Briefing",
    review_status: "pending",
    review_comment: null,
    reviewed_by: null,
    reviewed_at: null,
    generated_at: "2026-06-01T00:00:00Z",
    ...overrides,
  };
}

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

describe("StartupDetails", () => {
  it("mostra estado de carregamento", () => {
    mockedGetStartup.mockReturnValue(new Promise(() => {}));
    mockedGetEvidences.mockReturnValue(new Promise(() => {}));
    mockedListRecommendations.mockReturnValue(new Promise(() => {}));
    mockedListBriefings.mockReturnValue(new Promise(() => {}));

    renderWithClient(<StartupDetails startupId={STARTUP_ID} />);

    expect(screen.getByText(/carregando resultado/i)).toBeInTheDocument();
  });

  it("mostra mensagem de erro quando a busca da startup falha", async () => {
    mockedGetStartup.mockRejectedValue(new Error("startup indisponivel"));
    mockedGetEvidences.mockResolvedValue([]);
    mockedListRecommendations.mockResolvedValue([]);
    mockedListBriefings.mockResolvedValue([]);

    renderWithClient(<StartupDetails startupId={STARTUP_ID} />);

    expect(await screen.findByText("startup indisponivel")).toBeInTheDocument();
  });

  it("renderiza perfil, evidencias, recomendacoes e briefing quando populados", async () => {
    const evidence: StartupEvidence = {
      id: "ev-1",
      startup_id: STARTUP_ID,
      scraping_result_id: "sr-1",
      source_url: "https://acme.example.com/blog",
      evidence_type: "product_description",
      title: "Acme lanca produto de IA",
      confidence_score: 0.9,
      notes: "Evidencia coletada e aprovada pelo pipeline.",
      created_at: "2026-06-01T00:00:00Z",
    };
    const recommendation = baseRecommendation({ matched_keywords: ["inference"], evidence_ids: ["ev-1"] });
    const briefing = baseBriefing({ content: "# Briefing Executivo - Acme AI" });

    mockedGetStartup.mockResolvedValue(baseStartup());
    mockedGetEvidences.mockResolvedValue([evidence]);
    mockedListRecommendations.mockResolvedValue([recommendation]);
    mockedListBriefings.mockResolvedValue([briefing]);

    renderWithClient(<StartupDetails startupId={STARTUP_ID} />);

    expect(await screen.findByText("Acme AI")).toBeInTheDocument();
    expect(screen.getByText("Acme lanca produto de IA")).toBeInTheDocument();
    expect(screen.getByText("NVIDIA NIM")).toBeInTheDocument();
    expect(screen.getByText(/Briefing Executivo/)).toBeInTheDocument();
  });

  it("mostra textos de fallback quando nao ha evidencia, recomendacao ou briefing", async () => {
    mockedGetStartup.mockResolvedValue(baseStartup({ description: null }));
    mockedGetEvidences.mockResolvedValue([]);
    mockedListRecommendations.mockResolvedValue([]);
    mockedListBriefings.mockResolvedValue([]);

    renderWithClient(<StartupDetails startupId={STARTUP_ID} />);

    expect(await screen.findByText("Nenhuma evidencia disponivel.")).toBeInTheDocument();
    expect(screen.getByText("Nenhuma recomendacao foi gerada.")).toBeInTheDocument();
    expect(screen.getByText("Briefing ainda nao disponivel.")).toBeInTheDocument();
  });

  it("mostra badge 'Pronto para contato' quando AI-native, melhor score alto e briefing existe", async () => {
    const recommendation = baseRecommendation({ justification: "Justificativa." });
    const briefing = baseBriefing();
    mockedGetStartup.mockResolvedValue(baseStartup());
    mockedGetEvidences.mockResolvedValue([]);
    mockedListRecommendations.mockResolvedValue([recommendation]);
    mockedListBriefings.mockResolvedValue([briefing]);

    renderWithClient(<StartupDetails startupId={STARTUP_ID} />);

    expect(await screen.findByText("Pronto para contato")).toBeInTheDocument();
  });

  it("mostra badge 'Precisa mais evidencia' quando nao ha recomendacao com score relevante", async () => {
    mockedGetStartup.mockResolvedValue(baseStartup({ ai_maturity_level: null }));
    mockedGetEvidences.mockResolvedValue([]);
    mockedListRecommendations.mockResolvedValue([]);
    mockedListBriefings.mockResolvedValue([]);

    renderWithClient(<StartupDetails startupId={STARTUP_ID} />);

    expect(await screen.findByText("Precisa mais evidencia")).toBeInTheDocument();
  });

  it("expande a evidencia vinculada a uma recomendacao ao clicar em Ver evidencia", async () => {
    const user = userEvent.setup();
    const evidence: StartupEvidence = {
      id: "ev-1", startup_id: STARTUP_ID, scraping_result_id: "sr-1", source_url: "https://acme.example.com/blog",
      evidence_type: "product_description", title: "Acme lanca produto de IA", confidence_score: 0.9,
      notes: null, created_at: "2026-06-01T00:00:00Z",
    };
    const recommendation = baseRecommendation({ justification: "Justificativa.", matched_keywords: ["inference"], evidence_ids: ["ev-1"] });
    mockedGetStartup.mockResolvedValue(baseStartup());
    mockedGetEvidences.mockResolvedValue([evidence]);
    mockedListRecommendations.mockResolvedValue([recommendation]);
    mockedListBriefings.mockResolvedValue([]);

    renderWithClient(<StartupDetails startupId={STARTUP_ID} />);

    const toggle = await screen.findByRole("button", { name: /ver evidencia/i });
    await user.click(toggle);

    const recommendationCard = screen.getByText("NVIDIA NIM").closest("article") as HTMLElement;
    expect(within(recommendationCard).getByRole("link", { name: /acme lanca produto de ia/i })).toHaveAttribute("href", evidence.source_url);
  });

  it("renderiza links Markdown da justificativa e do briefing como links clicaveis", async () => {
    const recommendation = baseRecommendation({ justification: "NIM acelera inferencia. Fontes: [Fonte 1](https://docs.nvidia.com/nim/)." });
    const briefing = baseBriefing({
      content: "# Briefing Executivo\n\n## Evidencias Principais\n- [Acme lanca produto](https://acme.example.com/blog) - news",
    });
    mockedGetStartup.mockResolvedValue(baseStartup());
    mockedGetEvidences.mockResolvedValue([]);
    mockedListRecommendations.mockResolvedValue([recommendation]);
    mockedListBriefings.mockResolvedValue([briefing]);

    renderWithClient(<StartupDetails startupId={STARTUP_ID} />);

    expect(await screen.findByRole("link", { name: "Fonte 1" })).toHaveAttribute("href", "https://docs.nvidia.com/nim/");
    expect(screen.getByRole("link", { name: "Acme lanca produto" })).toHaveAttribute("href", "https://acme.example.com/blog");
  });

  it("aciona refreshStartupAnalysis ao clicar em atualizar recomendacoes", async () => {
    const user = userEvent.setup();
    mockedGetStartup.mockResolvedValue(baseStartup());
    mockedGetEvidences.mockResolvedValue([]);
    mockedListRecommendations.mockResolvedValue([]);
    mockedListBriefings.mockResolvedValue([]);
    mockedRefresh.mockResolvedValue({ ...baseBriefing(), id: "brief-2", content: "novo briefing", generated_at: "2026-06-02T00:00:00Z" });

    renderWithClient(<StartupDetails startupId={STARTUP_ID} />);

    const button = await screen.findByRole("button", { name: /atualizar recomendacoes/i });
    await user.click(button);

    await waitFor(() => expect(mockedRefresh).toHaveBeenCalledWith(STARTUP_ID));
  });

  it("exibe secao de rastreabilidade de extracao quando field_confidence tem dados", async () => {
    mockedGetStartup.mockResolvedValue(
      baseStartup({
        field_confidence: { founders: 0.9, sector: 0.75 },
        field_evidence_ids: { founders: ["ev-1", "ev-2"], sector: ["ev-1"] },
      })
    );
    mockedGetEvidences.mockResolvedValue([]);
    mockedListRecommendations.mockResolvedValue([]);
    mockedListBriefings.mockResolvedValue([]);

    renderWithClient(<StartupDetails startupId={STARTUP_ID} />);

    expect(await screen.findByText("Rastreabilidade de Extração")).toBeInTheDocument();
    expect(screen.getByText("90%")).toBeInTheDocument();
    expect(screen.getByText("2 evidências de suporte")).toBeInTheDocument();
  });

  it("registra revisao de recomendacao ao clicar em aprovar", async () => {
    const user = userEvent.setup();
    const recommendation = baseRecommendation();
    mockedGetStartup.mockResolvedValue(baseStartup());
    mockedGetEvidences.mockResolvedValue([]);
    mockedListRecommendations.mockResolvedValue([recommendation]);
    mockedListBriefings.mockResolvedValue([]);
    mockedReviewRecommendation.mockResolvedValue({
      ...recommendation,
      review_status: "approved",
      review_comment: "Ok para contato",
    });

    renderWithClient(<StartupDetails startupId={STARTUP_ID} />);

    const card = (await screen.findByText("NVIDIA NIM")).closest("article") as HTMLElement;
    await user.type(within(card).getByPlaceholderText("Comentario da revisao"), "Ok para contato");
    await user.click(within(card).getByRole("button", { name: "Aprovar" }));

    await waitFor(() => expect(mockedReviewRecommendation).toHaveBeenCalledWith(
      "rec-1",
      { status: "approved", comment: "Ok para contato", reviewed_by: undefined },
    ));
  });
});
