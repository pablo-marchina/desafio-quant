import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import userEvent from "@testing-library/user-event";

import { listStartups } from "@/lib/api/radar-client";

import { StartupPortfolio } from "./startup-portfolio";

vi.mock("@/lib/api/radar-client");
const mockedListStartups = vi.mocked(listStartups);

function renderWithClient(children: ReactNode) {
  return render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>{children}</QueryClientProvider>);
}

describe("StartupPortfolio", () => {
  beforeEach(() => vi.resetAllMocks());

  it("exibe cards e o total do portfolio", async () => {
    mockedListStartups.mockResolvedValue({
      items: [{ id: "startup-1", name: "Acme AI", website_url: null, description: "IA para atendimento", sector: "SaaS", country: "BR", ai_maturity_level: "ai_native", classification_reason: null, classified_at: null, founders: [], funding_stage: null, funding_amount_usd: null, customers: [], ai_profile: null, field_confidence: {}, field_evidence_ids: {}, created_at: "2026-01-01", updated_at: "2026-01-01" }],
      total: 1, page: 1, page_size: 20,
    });

    renderWithClient(<StartupPortfolio />);

    expect(await screen.findByText("Acme AI")).toBeInTheDocument();
    expect(screen.getByText("1 startup analisada")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Acme AI/i })).toHaveAttribute("href", "/startups/startup-1");
  });

  it("envia os filtros e reinicia a pagina", async () => {
    const user = userEvent.setup();
    mockedListStartups.mockResolvedValue({ items: [], total: 0, page: 1, page_size: 12 });

    renderWithClient(<StartupPortfolio />);
    await screen.findByText(/nenhuma startup corresponde/i);
    await user.type(screen.getByLabelText("Buscar startups"), "Acme");
    await user.selectOptions(screen.getByLabelText("Filtrar por maturidade de IA"), "ai_native");
    await user.click(screen.getByRole("button", { name: "Buscar" }));

    await waitFor(() => expect(mockedListStartups).toHaveBeenLastCalledWith({ page: 1, page_size: 12, query: "Acme", sector: "", country: "", ai_maturity_level: "ai_native" }));
  });
});
