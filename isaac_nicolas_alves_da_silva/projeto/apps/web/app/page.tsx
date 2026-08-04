import Link from "next/link";

import { radarRequest } from "@/lib/api/radar-server";

async function getStartupCount(): Promise<number | null> {
  try {
    const response = await radarRequest("/startups?page=1&page_size=1");
    if (!response.ok) return null;
    const data = (await response.json()) as { total?: number };
    return data.total ?? null;
  } catch {
    return null;
  }
}

export default async function HomePage() {
  const startupCount = await getStartupCount();

  return (
    <main className="mx-auto max-w-6xl px-6 py-20">
      <p className="mb-4 text-sm font-semibold uppercase tracking-[0.2em] text-[var(--accent)]">Startup intelligence</p>
      <h1 className="max-w-3xl text-4xl font-semibold leading-tight md:text-6xl">
        Transforme uma URL em uma analise rastreavel para o ecossistema NVIDIA.
      </h1>
      <p className="mt-6 max-w-2xl text-lg leading-8 text-[var(--muted)]">
        Coletamos evidencias, estruturamos o perfil da startup, classificamos a maturidade em IA e geramos recomendacoes e briefing executivo.
      </p>
      <p className="mt-4 text-sm font-semibold text-[var(--accent)]">
        {startupCount !== null
          ? `${startupCount} startup${startupCount === 1 ? "" : "s"} analisada${startupCount === 1 ? "" : "s"} ate agora.`
          : "Comece enviando a primeira URL para analise."}
      </p>
      <div className="mt-10 flex flex-wrap gap-3">
        <Link className="inline-flex rounded-md bg-[var(--accent)] px-5 py-3 font-semibold text-[#07111f]" href="/analyze">Comecar uma analise</Link>
        <Link className="inline-flex rounded-md border border-[var(--surface-border)] px-5 py-3 font-semibold" href="/startups">Ver portfolio</Link>
      </div>
    </main>
  );
}
