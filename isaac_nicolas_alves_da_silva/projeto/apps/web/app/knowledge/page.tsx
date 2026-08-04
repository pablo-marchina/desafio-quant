import { NvidiaChat } from "@/features/knowledge/nvidia-chat";

export default function KnowledgePage() {
  return (
    <main className="mx-auto max-w-3xl px-6 py-16">
      <p className="text-sm font-semibold uppercase tracking-[0.2em] text-[var(--accent)]">Base de conhecimento</p>
      <h1 className="mt-3 text-3xl font-semibold">Chat sobre tecnologias NVIDIA</h1>
      <p className="mt-2 text-[var(--muted)]">Respostas fundamentadas em fontes oficiais NVIDIA ja ingeridas, com citacoes rastreaveis.</p>
      <NvidiaChat />
    </main>
  );
}
