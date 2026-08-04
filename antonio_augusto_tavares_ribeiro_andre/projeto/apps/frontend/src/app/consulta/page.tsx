import type { Metadata } from "next";
import Link from "next/link";

import { ConsultaConsole } from "./console";

// Tela de consulta (F5.3): casca server (metadata + cabecalho) sobre o console client que
// faz o POST /runs e acompanha o pipeline ao vivo via SSE (F5.2/F2.10). UI em PT-BR (F0.13).
export const metadata: Metadata = {
  title: "Consulta — NVIDIA Radar",
  description:
    "Lookup de uma empresa ou descoberta por setor/regiao, com o pipeline multi-agente ao vivo.",
};

export default function ConsultaPage() {
  return (
    <main className="flex flex-1 flex-col items-center bg-background text-foreground">
      <div className="w-full max-w-3xl px-6 py-16 sm:py-24">
        <header className="flex flex-col gap-3">
          <Link
            href="/"
            className="w-fit text-sm text-muted-foreground hover:text-foreground"
          >
            ← NVIDIA Radar
          </Link>
          <h1 className="text-3xl font-semibold tracking-tight sm:text-4xl">Consulta</h1>
          <p className="text-muted-foreground">
            Diagnostique uma empresa ou descubra startups por setor/regiao. O pipeline
            multi-agente roda no servidor e o progresso aparece ao vivo abaixo.
          </p>
        </header>

        <div className="mt-10">
          <ConsultaConsole />
        </div>
      </div>
    </main>
  );
}
