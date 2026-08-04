import { JobStatusPanel } from "@/features/analysis/job-status-panel";

export default async function JobPage({ params }: { params: Promise<{ jobId: string }> }) {
  const { jobId } = await params;
  return (
    <main className="mx-auto max-w-3xl px-6 py-16">
      <p className="text-sm font-semibold uppercase tracking-[0.2em] text-[var(--accent)]">Acompanhamento</p>
      <h1 className="mt-3 text-3xl font-semibold">Analise em andamento</h1>
      <JobStatusPanel jobId={jobId} />
    </main>
  );
}
