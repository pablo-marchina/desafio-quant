"use client";

import { type FormEvent, useState } from "react";
import { useMutation } from "@tanstack/react-query";

import { MarkdownContent } from "@/components/markdown-content";
import { askNvidiaKnowledge } from "@/lib/api/radar-client";
import type { RagAnswer } from "@/lib/api/radar-types";

type ChatEntry = { query: string; answer: RagAnswer };

export function NvidiaChat() {
  const [draft, setDraft] = useState("");
  const [history, setHistory] = useState<ChatEntry[]>([]);
  const mutation = useMutation({
    mutationFn: (query: string) => askNvidiaKnowledge(query),
    onSuccess: (answer, query) => setHistory((current) => [...current, { query, answer }]),
  });

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const query = draft.trim();
    if (!query) return;
    mutation.mutate(query);
    setDraft("");
  }

  return (
    <div className="mt-8 space-y-6">
      <form className="flex gap-3" onSubmit={handleSubmit}>
        <input
          aria-label="Pergunta sobre tecnologias NVIDIA"
          className="flex-1 rounded-md border border-[var(--surface-border)] bg-transparent px-3 py-2"
          onChange={(event) => setDraft(event.target.value)}
          placeholder="Ex: Como o NIM ajuda em inferencia de LLM?"
          value={draft}
        />
        <button
          className="rounded-md bg-[var(--accent)] px-5 py-2 font-semibold text-[#07111f] disabled:cursor-not-allowed disabled:opacity-60"
          disabled={mutation.isPending}
          type="submit"
        >
          {mutation.isPending ? "Perguntando..." : "Perguntar"}
        </button>
      </form>

      {mutation.isError && <p className="rounded-md border border-[var(--danger)] p-4 text-[var(--danger)]">{mutation.error.message}</p>}
      {!history.length && !mutation.isPending && (
        <p className="text-[var(--muted)]">
          Pergunte sobre tecnologias NVIDIA (NIM, TensorRT-LLM, Triton, RAPIDS, Riva, MONAI, etc.) com base no conhecimento ja ingerido.
        </p>
      )}

      <div className="space-y-4">
        {history.map((entry, index) => (
          <article className="rounded-xl border border-[var(--surface-border)] bg-[var(--surface)] p-5" key={index}>
            <p className="text-sm font-semibold text-[var(--muted)]">Pergunta</p>
            <p className="mt-1">{entry.query}</p>
            <p className="mt-4 text-sm font-semibold text-[var(--muted)]">Resposta</p>
            <MarkdownContent className="[&_p]:mt-1" content={entry.answer.answer} />
            {entry.answer.citations.length > 0 && (
              <div className="mt-4 space-y-1 border-t border-[var(--surface-border)] pt-3">
                <p className="text-xs font-semibold uppercase tracking-wide text-[var(--muted)]">Citacoes</p>
                {entry.answer.citations.map((citation) => (
                  <a className="block text-sm text-[var(--accent)] underline" href={citation.source_url} key={citation.chunk_id} rel="noreferrer" target="_blank">
                    {citation.source_url}
                  </a>
                ))}
              </div>
            )}
          </article>
        ))}
      </div>
    </div>
  );
}
