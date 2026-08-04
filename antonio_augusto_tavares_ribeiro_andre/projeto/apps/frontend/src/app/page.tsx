import Link from "next/link";

import { buttonVariants } from "@/components/ui/button";
import { cn } from "@/lib/utils";

// Hub do dashboard: a home e a porta de entrada das telas que ja rodam. Cada card leva direto
// a sua tela; o detalhe AIMI (4 pilares, recomendacoes, briefing) abre a partir de cada startup
// no radar. UI em PT-BR (F0.13).
const TELAS = [
  {
    href: "/consulta",
    titulo: "Consulta",
    descricao:
      "Diagnostique uma empresa ou descubra startups por setor/regiao, com o pipeline multi-agente ao vivo.",
  },
  {
    href: "/radar",
    titulo: "Radar de startups",
    descricao:
      "A coorte mapeada, filtravel por setor, maturidade (AIMI) e classe — ordenada por Inception Priority.",
  },
  {
    href: "/descoberta",
    titulo: "Descoberta da coorte",
    descricao:
      "Pergunte em portugues sobre as startups (classe, AIMI, tecnologia NVIDIA) e receba as empresas como conversa.",
  },
  {
    href: "/coorte",
    titulo: "Radar de coorte",
    descricao:
      "Visao de portfolio: o ecossistema agrupado por perfil e ranqueado por prontidao de graduacao.",
  },
] as const;

export default function Home() {
  return (
    <main className="flex flex-1 flex-col items-center bg-background text-foreground">
      <div className="w-full max-w-5xl px-6 py-16 sm:py-24">
        <header className="flex flex-col gap-4">
          <span className="inline-flex w-fit items-center rounded-full border border-border px-3 py-1 text-xs font-medium text-muted-foreground">
            NVIDIA Inception · ferramenta interna
          </span>
          <h1 className="text-4xl font-semibold tracking-tight sm:text-5xl">
            NVIDIA Startup AI Radar
          </h1>
          <p className="max-w-2xl text-lg text-muted-foreground">
            Mapeia startups brasileiras AI-native, diagnostica a maturidade tecnica (AIMI) e
            recomenda tecnologias NVIDIA com evidencia rastreavel dos dois lados — para apoiar a
            decisao de outreach do gerente de Startups &amp; VCs.
          </p>
          <div className="mt-2 flex flex-wrap gap-3">
            <Link
              href="/consulta"
              className={cn(buttonVariants({ variant: "brand", size: "lg" }))}
            >
              Nova consulta
            </Link>
            <Link
              href="/radar"
              className={cn(buttonVariants({ variant: "outline", size: "lg" }))}
            >
              Ver radar de startups
            </Link>
          </div>
        </header>

        <section className="mt-12 grid gap-4 sm:grid-cols-2">
          {TELAS.map((tela) => (
            <Link
              key={tela.href}
              href={tela.href}
              className="group flex flex-col gap-2 rounded-lg border border-border bg-card p-5 text-card-foreground transition-colors hover:border-brand/40 hover:bg-accent"
            >
              <div className="flex items-center justify-between gap-2">
                <h2 className="text-base font-semibold">{tela.titulo}</h2>
                <span
                  aria-hidden
                  className="text-muted-foreground transition-all group-hover:translate-x-0.5 group-hover:text-brand-ink"
                >
                  →
                </span>
              </div>
              <p className="text-sm text-muted-foreground">{tela.descricao}</p>
            </Link>
          ))}
        </section>

        <p className="mt-8 max-w-2xl text-sm text-muted-foreground">
          Cada startup no radar abre o diagnostico AIMI completo: os 4 pilares com evidencia dos dois
          lados, as recomendacoes de tecnologia NVIDIA e o briefing executivo com export em PDF.
        </p>

        <footer className="mt-12 border-t border-border pt-6 text-sm text-muted-foreground">
          Next.js (App Router) · TypeScript · Tailwind · shadcn/ui · UI em PT-BR.
        </footer>
      </div>
    </main>
  );
}
