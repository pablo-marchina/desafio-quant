import { JobHistory } from "@/features/jobs/job-history";

export default function JobsHistoryPage() {
  return (
    <main className="mx-auto max-w-5xl px-6 py-16">
      <p className="text-sm font-semibold uppercase tracking-[0.2em] text-[var(--accent)]">Operacao</p>
      <h1 className="mt-3 text-3xl font-semibold">Historico de analises</h1>
      <p className="mt-2 text-[var(--muted)]">Acompanhe todas as URLs enviadas e o status de cada etapa da analise.</p>
      <JobHistory />
    </main>
  );
}
