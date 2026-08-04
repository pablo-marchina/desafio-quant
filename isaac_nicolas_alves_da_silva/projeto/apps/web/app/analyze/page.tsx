import { UrlSubmissionForm } from "@/features/analysis/url-submission-form";

export default function AnalyzePage() {
  return (
    <main className="mx-auto max-w-2xl px-6 py-16">
      <p className="text-sm font-semibold uppercase tracking-[0.2em] text-[var(--accent)]">Nova analise</p>
      <h1 className="mt-3 text-3xl font-semibold">Envie a URL de uma startup</h1>
      <p className="mt-3 text-[var(--muted)]">
        O pipeline vai coletar a fonte, criar ou associar o perfil e gerar o briefing automaticamente.
      </p>
      <div className="mt-8 rounded-xl border border-[var(--surface-border)] bg-[var(--surface)] p-6">
        <UrlSubmissionForm />
      </div>
    </main>
  );
}
