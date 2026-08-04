import type { Metadata } from "next";

import { CompanyDetailView } from "./detail";

// Detalhe da startup (F5.5): casca server (metadata) sobre a view client que busca o
// `GET /companies/{id}` (F5.2) e desenha o radar AIMI dos 4 pilares + evidencias por pilar.
// UI PT-BR (F0.13). Em Next 16 o `params` e Promise (App Router) — resolvido com await.
export const metadata: Metadata = {
  title: "Detalhe da startup — NVIDIA Radar",
  description: "Diagnostico AIMI (radar dos 4 pilares) com evidencias citadas por pilar.",
};

export default async function CompanyDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  return <CompanyDetailView id={Number(id)} />;
}
