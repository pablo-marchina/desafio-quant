"use client";

import Link from "next/link";
import { useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";

import { createDiscoveryRun, getDiscoveryRun } from "@/lib/api/radar-client";
import type { DiscoveryRun, DiscoveryRunStatus } from "@/lib/api/radar-types";

const STATUS_LABELS: Record<DiscoveryRunStatus, string> = {
  pending: "Aguardando",
  running: "Descobrindo startups...",
  completed: "Concluído",
  failed: "Falhou",
};

const HUB_NAMES = ["InovAtiva Brasil", "Abstartups", "100 Open Startups"];

function RunResult({ run }: { run: DiscoveryRun }) {
  const isTerminal = run.status === "completed" || run.status === "failed";
  const isRunning = run.status === "running" || run.status === "pending";

  return (
    <div className="mt-6 rounded-xl border border-[var(--surface-border)] bg-[var(--surface)] p-6">
      <div className="flex items-center gap-3">
        {isRunning && (
          <span className="inline-block h-3 w-3 animate-pulse rounded-full bg-yellow-400" />
        )}
        {run.status === "completed" && (
          <span className="inline-block h-3 w-3 rounded-full bg-[var(--accent)]" />
        )}
        {run.status === "failed" && (
          <span className="inline-block h-3 w-3 rounded-full bg-red-400" />
        )}
        <p className="font-semibold">{STATUS_LABELS[run.status]}</p>
      </div>

      {isRunning && (
        <p className="mt-2 text-sm text-[var(--muted)]">
          Buscando startups nos hubs públicos. Isso pode levar até 30 segundos.
        </p>
      )}

      {isTerminal && (
        <dl className="mt-4 grid gap-4 sm:grid-cols-3">
          <div>
            <dt className="text-xs font-semibold uppercase tracking-wide text-[var(--muted)]">Hubs consultados</dt>
            <dd className="mt-1 text-2xl font-semibold">{run.hubs_processed}</dd>
          </div>
          <div>
            <dt className="text-xs font-semibold uppercase tracking-wide text-[var(--muted)]">URLs encontradas</dt>
            <dd className="mt-1 text-2xl font-semibold">{run.urls_found}</dd>
          </div>
          <div>
            <dt className="text-xs font-semibold uppercase tracking-wide text-[var(--muted)]">Jobs submetidos</dt>
            <dd className="mt-1 text-2xl font-semibold">{run.jobs_submitted}</dd>
          </div>
        </dl>
      )}

      {run.status === "completed" && run.jobs_submitted > 0 && (
        <p className="mt-4 text-sm text-[var(--muted)]">
          Cada URL foi enfileirada para análise completa (scraping → extração → recomendações).{" "}
          <Link className="text-[var(--accent)] underline" href="/jobs?source_type=startup_evidence">
            Ver jobs no histórico
          </Link>
        </p>
      )}

      {run.status === "completed" && run.jobs_submitted === 0 && (
        <p className="mt-4 text-sm text-[var(--muted)]">
          Nenhuma nova URL encontrada nos hubs nesta rodada.
        </p>
      )}

      {run.status === "failed" && (
        <p className="mt-4 text-sm text-red-400">
          {run.error_message ?? "Falha ao descobrir startups. Tente novamente."}
        </p>
      )}
    </div>
  );
}

function PollingResult({ runId }: { runId: string }) {
  const query = useQuery({
    queryKey: ["discovery-run", runId],
    queryFn: () => getDiscoveryRun(runId),
    refetchInterval: (q) => {
      const s = q.state.data?.status;
      return s === "completed" || s === "failed" ? false : 3000;
    },
  });

  if (query.isLoading) return <p className="mt-6 text-[var(--muted)]">Iniciando descoberta...</p>;
  if (query.isError) return <p className="mt-6 text-red-400">{(query.error as Error).message}</p>;
  if (!query.data) return null;

  return <RunResult run={query.data} />;
}

export function StartupDiscovery() {
  const [runId, setRunId] = useState<string | null>(null);

  const mutation = useMutation({
    mutationFn: createDiscoveryRun,
    onSuccess: (run) => setRunId(run.id),
  });

  const isIdle = !runId && !mutation.isPending;

  return (
    <div className="mx-auto max-w-3xl px-6 py-12">
      <h1 className="text-3xl font-semibold">Descoberta de Startups</h1>
      <p className="mt-3 text-[var(--muted)]">
        Busca automaticamente startups em ecossistemas públicos brasileiros e enfileira cada uma para
        análise completa pelo pipeline do Radar.
      </p>

      <div className="mt-8 rounded-xl border border-[var(--surface-border)] bg-[var(--surface)] p-6">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-[var(--muted)]">Fontes consultadas</h2>
        <ul className="mt-3 space-y-2">
          {HUB_NAMES.map((hub) => (
            <li className="flex items-center gap-2 text-sm" key={hub}>
              <span className="h-1.5 w-1.5 rounded-full bg-[var(--accent)]" />
              {hub}
            </li>
          ))}
        </ul>

        <button
          className="mt-6 rounded-md bg-[var(--accent)] px-5 py-2.5 text-sm font-semibold text-[#07111f] disabled:opacity-50"
          disabled={mutation.isPending || !!runId}
          onClick={() => mutation.mutate()}
          type="button"
        >
          {mutation.isPending ? "Iniciando..." : isIdle ? "Descobrir startups" : "Descoberta em andamento"}
        </button>

        {mutation.isError && (
          <p className="mt-3 text-sm text-red-400">{(mutation.error as Error).message}</p>
        )}
      </div>

      {runId && <PollingResult runId={runId} />}
    </div>
  );
}
