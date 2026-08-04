import type { Metadata } from "next";
import Link from "next/link";

import { RadarBoard } from "./board";

// Radar de startups (F5.4): casca server (metadata + cabecalho) sobre o board client que filtra
// por setor/AIMI/classe e lista as empresas ordenadas por inception_priority (F5.2). UI PT-BR (F0.13).
export const metadata: Metadata = {
  title: "Radar de startups — NVIDIA Radar",
  description:
    "Lista filtravel de startups por setor, AIMI e classe, ordenada por Inception Priority.",
};

export default function RadarPage() {
  return (
    <main className="flex flex-1 flex-col items-center bg-background text-foreground">
      <div className="w-full max-w-4xl px-6 py-16 sm:py-24">
        <header className="flex flex-col gap-3">
          <Link href="/" className="w-fit text-sm text-muted-foreground hover:text-foreground">
            ← NVIDIA Radar
          </Link>
          <h1 className="text-3xl font-semibold tracking-tight sm:text-4xl">Radar de startups</h1>
          <p className="text-muted-foreground">
            A coorte mapeada, filtravel por setor, maturidade (AIMI) e classe. A lista vem
            ordenada por Inception Priority — a fila de outreach do gerente.
          </p>
        </header>

        <div className="mt-10">
          <RadarBoard />
        </div>
      </div>
    </main>
  );
}
