import type { Metadata } from "next";
import Link from "next/link";

import { DiscoveryChat } from "./chat";

// Descoberta da coorte (F5.12): casca server (metadata + cabecalho) sobre o chat client que
// pergunta em PT-BR ao `GET /discover` (F3.10) e desenha as empresas como conversa. UI PT-BR (F0.13).
export const metadata: Metadata = {
  title: "Descoberta da coorte — NVIDIA Radar",
  description:
    "Chat em linguagem natural sobre a coorte: pergunte por classe, maturidade (AIMI) ou " +
    "tecnologia NVIDIA e receba as startups ordenadas por Inception Priority.",
};

export default function DescobertaPage() {
  return (
    <main className="flex flex-1 flex-col items-center bg-background text-foreground">
      <div className="flex w-full max-w-3xl flex-col px-6 py-16 sm:py-24">
        <header className="flex flex-col gap-3">
          <Link href="/" className="w-fit text-sm text-muted-foreground hover:text-foreground">
            ← NVIDIA Radar
          </Link>
          <h1 className="text-3xl font-semibold tracking-tight sm:text-4xl">Descoberta da coorte</h1>
          <p className="text-muted-foreground">
            Pergunte em portugues sobre as startups mapeadas — por classe, maturidade (AIMI) ou
            tecnologia NVIDIA. A resposta traz as empresas ordenadas por Inception Priority e o eco
            de como a pergunta foi interpretada.
          </p>
        </header>

        <div className="mt-8">
          <DiscoveryChat />
        </div>
      </div>
    </main>
  );
}
