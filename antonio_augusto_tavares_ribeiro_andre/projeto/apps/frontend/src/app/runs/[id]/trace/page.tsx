import type { Metadata } from "next";

import { RunTraceView } from "./trace-view";

// Trace viewer (F5.7): casca server (metadata) sobre a view client que busca o
// `GET /runs/{id}/trace` (F5.2) e desenha os passos dos agentes (estado do grafo) + custo +
// link Langfuse. UI PT-BR (F0.13). Em Next 16 o `params` e Promise (App Router) — resolvido
// com await, como no detalhe da startup (F5.5).
export const metadata: Metadata = {
  title: "Trace do run — NVIDIA Radar",
  description: "Passos dos agentes de um run (estado do grafo) com custo e link ao Langfuse.",
};

export default async function RunTracePage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  return <RunTraceView runId={id} />;
}
