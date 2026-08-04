import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { getPortfolioStats, getTechnologyStats } from "@/lib/api/radar-client";
import { PortfolioCharts } from "./portfolio-charts";

vi.mock("@/lib/api/radar-client");
const mockedGetPortfolioStats = vi.mocked(getPortfolioStats);
const mockedGetTechnologyStats = vi.mocked(getTechnologyStats);

function renderWithClient(children: ReactNode) {
  return render(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      {children}
    </QueryClientProvider>
  );
}

describe("PortfolioCharts", () => {
  beforeEach(() => vi.resetAllMocks());

  it("renderiza os dois gráficos quando há dados", async () => {
    mockedGetPortfolioStats.mockResolvedValue({
      ai_native: 3, ai_enabled: 5, non_ai: 1, unclassified: 2, total: 11,
    });
    mockedGetTechnologyStats.mockResolvedValue({
      items: [
        { technology_slug: "nvidia-nim", technology_name: "NVIDIA NIM", count: 4 },
        { technology_slug: "triton", technology_name: "Triton", count: 2 },
      ],
    });

    renderWithClient(<PortfolioCharts />);

    expect(await screen.findByText("Distribuição por Maturidade em IA")).toBeInTheDocument();
    expect(await screen.findByText("Tecnologias NVIDIA Mais Recomendadas")).toBeInTheDocument();
    expect(await screen.findByText(/Total: 11 startups/)).toBeInTheDocument();
    expect(await screen.findByText("NVIDIA NIM")).toBeInTheDocument();
    expect(await screen.findByText("Triton")).toBeInTheDocument();
  });

  it("mostra estado vazio para maturidade quando não há startups classificadas", async () => {
    mockedGetPortfolioStats.mockResolvedValue({
      ai_native: 0, ai_enabled: 0, non_ai: 0, unclassified: 0, total: 0,
    });
    mockedGetTechnologyStats.mockResolvedValue({ items: [] });

    renderWithClient(<PortfolioCharts />);

    expect(await screen.findByText("Nenhuma startup classificada ainda.")).toBeInTheDocument();
    expect(await screen.findByText("Nenhuma recomendação gerada ainda.")).toBeInTheDocument();
  });
});
