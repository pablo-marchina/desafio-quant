import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { askNvidiaKnowledge } from "@/lib/api/radar-client";
import type { RagAnswer } from "@/lib/api/radar-types";

import { NvidiaChat } from "./nvidia-chat";

vi.mock("@/lib/api/radar-client");
const mockedAsk = vi.mocked(askNvidiaKnowledge);

function renderWithClient(children: ReactNode) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  return render(<QueryClientProvider client={queryClient}>{children}</QueryClientProvider>);
}

beforeEach(() => vi.resetAllMocks());

describe("NvidiaChat", () => {
  it("mostra mensagem inicial antes de qualquer pergunta", () => {
    renderWithClient(<NvidiaChat />);

    expect(screen.getByText(/pergunte sobre tecnologias nvidia/i)).toBeInTheDocument();
  });

  it("envia a pergunta e exibe resposta com citacoes", async () => {
    const user = userEvent.setup();
    const answer: RagAnswer = {
      query: "Como o NIM ajuda em inferencia?",
      answer: "NIM empacota modelos otimizados para inferencia escalavel.",
      citations: [{ chunk_id: "c-1", document_id: "d-1", source_url: "https://docs.nvidia.com/nim/", quote: "trecho" }],
      evidences: [],
    };
    mockedAsk.mockResolvedValue(answer);

    renderWithClient(<NvidiaChat />);
    await user.type(screen.getByLabelText("Pergunta sobre tecnologias NVIDIA"), "Como o NIM ajuda em inferencia?");
    await user.click(screen.getByRole("button", { name: "Perguntar" }));

    expect(await screen.findByText(answer.answer)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "https://docs.nvidia.com/nim/" })).toHaveAttribute("href", "https://docs.nvidia.com/nim/");
    await waitFor(() => expect(mockedAsk).toHaveBeenCalledWith("Como o NIM ajuda em inferencia?"));
  });

  it("renderiza link Markdown dentro da resposta como link clicavel", async () => {
    const user = userEvent.setup();
    const answer: RagAnswer = {
      query: "O que e o NIM?",
      answer: "NIM e' descrito em [docs.nvidia.com/nim](https://docs.nvidia.com/nim/).",
      citations: [],
      evidences: [],
    };
    mockedAsk.mockResolvedValue(answer);

    renderWithClient(<NvidiaChat />);
    await user.type(screen.getByLabelText("Pergunta sobre tecnologias NVIDIA"), "O que e o NIM?");
    await user.click(screen.getByRole("button", { name: "Perguntar" }));

    expect(await screen.findByRole("link", { name: "docs.nvidia.com/nim" })).toHaveAttribute("href", "https://docs.nvidia.com/nim/");
  });

  it("mostra erro quando a pergunta falha", async () => {
    const user = userEvent.setup();
    mockedAsk.mockRejectedValue(new Error("RAG indisponivel"));

    renderWithClient(<NvidiaChat />);
    await user.type(screen.getByLabelText("Pergunta sobre tecnologias NVIDIA"), "teste");
    await user.click(screen.getByRole("button", { name: "Perguntar" }));

    expect(await screen.findByText("RAG indisponivel")).toBeInTheDocument();
  });
});
