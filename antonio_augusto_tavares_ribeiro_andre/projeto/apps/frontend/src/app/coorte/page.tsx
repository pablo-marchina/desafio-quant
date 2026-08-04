import type { Metadata } from "next";
import Link from "next/link";

import { CohortRadar } from "./radar";

// Radar de coorte (F6.5–F6.7): casca server (metadata + cabecalho) sobre o radar client que
// consome o `GET /cohort/clusters` (F5.2) e desenha o ecossistema agrupado por perfil. UI PT-BR.
export const metadata: Metadata = {
  title: "Radar de coorte — NVIDIA Radar",
  description:
    "Visao de portfolio do ecossistema: startups agrupadas por perfil (clustering) e " +
    "ranqueadas por prontidao de graduacao para o NVIDIA Inception.",
};

export default function CoortePage() {
  return (
    <main className="flex flex-1 flex-col items-center bg-background text-foreground">
      <div className="w-full max-w-4xl px-6 py-16 sm:py-24">
        <header className="flex flex-col gap-3">
          <Link href="/" className="w-fit text-sm text-muted-foreground hover:text-foreground">
            ← NVIDIA Radar
          </Link>
          <h1 className="text-3xl font-semibold tracking-tight sm:text-4xl">Radar de coorte</h1>
          <p className="text-muted-foreground">
            A visao de portfolio (DSS nivel 3): a coorte agrupada por perfil (setor + stack) e os
            clusters ranqueados por prontidao de graduacao — quais blocos do ecossistema sao o melhor
            alvo de outreach do Inception.
          </p>
        </header>

        <div className="mt-10">
          <CohortRadar />
        </div>
      </div>
    </main>
  );
}
