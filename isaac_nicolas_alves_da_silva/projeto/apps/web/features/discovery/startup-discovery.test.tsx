import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { createDiscoveryRun, getDiscoveryRun } from "@/lib/api/radar-client";
import { StartupDiscovery } from "./startup-discovery";

vi.mock("next/link", () => ({
  default: ({ href, children, ...props }: { href: string; children: ReactNode; [k: string]: unknown }) => (
    <a href={href} {...props}>{children}</a>
  ),
}));

function renderWithClient(children: ReactNode) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={queryClient}>{children}</QueryClientProvider>);
}

vi.mock("@/lib/api/radar-client");
const mockedCreate = vi.mocked(createDiscoveryRun);
const mockedGet = vi.mocked(getDiscoveryRun);

function baseRun(overrides: Partial<import("@/lib/api/radar-types").DiscoveryRun> = {}) {
  return {
    id: "run-1",
    status: "completed" as const,
    hubs_processed: 3,
    urls_found: 12,
    jobs_submitted: 12,
    error_message: null,
    created_at: "2026-06-27T21:00:00Z",
    completed_at: "2026-06-27T21:00:30Z",
    ...overrides,
  };
}

describe("StartupDiscovery", () => {
  beforeEach(() => vi.resetAllMocks());

  it("renderiza lista de hubs e botao habilitado", () => {
    renderWithClient(<StartupDiscovery />);

    expect(screen.getByText("InovAtiva Brasil")).toBeInTheDocument();
    expect(screen.getByText("Abstartups")).toBeInTheDocument();
    expect(screen.getByText("100 Open Startups")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Descobrir startups" })).not.toBeDisabled();
  });

  it("dispara o run e exibe resultados quando concluido", async () => {
    const user = userEvent.setup();
    const run = baseRun({ status: "completed", urls_found: 7, jobs_submitted: 5 });
    mockedCreate.mockResolvedValue(run);
    mockedGet.mockResolvedValue(run);

    renderWithClient(<StartupDiscovery />);

    await user.click(screen.getByRole("button", { name: "Descobrir startups" }));

    expect(await screen.findByText("Concluído")).toBeInTheDocument();
    expect(screen.getByText("3")).toBeInTheDocument();
    expect(screen.getByText("7")).toBeInTheDocument();
    expect(screen.getByText("5")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Ver jobs no histórico/i })).toBeInTheDocument();
  });

  it("exibe mensagem de erro quando o run falha", async () => {
    const user = userEvent.setup();
    mockedCreate.mockResolvedValue(baseRun({ status: "failed", error_message: "Timeout nos hubs.", jobs_submitted: 0, urls_found: 0 }));
    mockedGet.mockResolvedValue(baseRun({ status: "failed", error_message: "Timeout nos hubs.", jobs_submitted: 0, urls_found: 0 }));

    renderWithClient(<StartupDiscovery />);

    await user.click(screen.getByRole("button", { name: "Descobrir startups" }));

    expect(await screen.findByText("Timeout nos hubs.")).toBeInTheDocument();
  });
});
