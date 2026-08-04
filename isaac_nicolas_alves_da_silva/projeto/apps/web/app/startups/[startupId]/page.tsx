import { StartupDetails } from "@/features/startups/startup-details";

export default async function StartupPage({ params }: { params: Promise<{ startupId: string }> }) {
  const { startupId } = await params;
  return (
    <main className="mx-auto max-w-6xl px-6 py-16">
      <p className="text-sm font-semibold uppercase tracking-[0.2em] text-[var(--accent)]">Resultado da analise</p>
      <StartupDetails startupId={startupId} />
    </main>
  );
}
