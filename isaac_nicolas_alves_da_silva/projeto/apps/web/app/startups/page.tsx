import Link from "next/link";

import { StartupPortfolio } from "@/features/startups/startup-portfolio";

export default function StartupsPage() {
  return (
    <main className="mx-auto max-w-6xl px-6 py-16">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div><p className="text-sm font-semibold uppercase tracking-[0.2em] text-[var(--accent)]">Portfolio</p><h1 className="mt-3 text-3xl font-semibold">Startups analisadas</h1><p className="mt-3 text-[var(--muted)]">Acompanhe os perfis e volte ao briefing de cada analise.</p></div>
        <Link className="rounded-md bg-[var(--accent)] px-5 py-3 font-semibold text-[#07111f]" href="/analyze">Nova analise</Link>
      </div>
      <StartupPortfolio />
    </main>
  );
}
