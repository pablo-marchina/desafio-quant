"use client";

import Link from "next/link";
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";

import { listUrlIngestionJobs } from "@/lib/api/radar-client";
import type { UrlIngestionStatus } from "@/lib/api/radar-types";
import { STATUS_LABELS } from "@/features/analysis/job-status-labels";

const PAGE_SIZE = 15;
const STATUS_OPTIONS: UrlIngestionStatus[] = ["pending", "scraping", "ingesting", "embedding", "analyzing", "completed", "failed"];

export function JobHistory() {
  const [page, setPage] = useState(1);
  const [status, setStatus] = useState<UrlIngestionStatus | "">("");
  const [sourceType, setSourceType] = useState("");
  const params = { page, page_size: PAGE_SIZE, status, source_type: sourceType };
  const jobsQuery = useQuery({
    queryKey: ["url-ingestion-jobs", params],
    queryFn: () => listUrlIngestionJobs(params),
  });

  function updateFilter<T>(setter: (value: T) => void, value: T) {
    setPage(1);
    setter(value);
  }

  const results = jobsQuery.data;
  const totalPages = results ? Math.max(1, Math.ceil(results.total / PAGE_SIZE)) : 1;

  return (
    <div className="mt-8 space-y-5">
      <div className="grid gap-3 rounded-xl border border-[var(--surface-border)] bg-[var(--surface)] p-4 md:grid-cols-4">
        <select
          aria-label="Filtrar por status"
          className="rounded-md border border-[var(--surface-border)] bg-[var(--surface)] px-3 py-2"
          onChange={(event) => updateFilter(setStatus, event.target.value as UrlIngestionStatus | "")}
          value={status}
        >
          <option value="">Todos os status</option>
          {STATUS_OPTIONS.map((option) => <option key={option} value={option}>{STATUS_LABELS[option]}</option>)}
        </select>
        <input
          aria-label="Filtrar por tipo de fonte"
          className="rounded-md border border-[var(--surface-border)] bg-transparent px-3 py-2 md:col-span-2"
          onChange={(event) => updateFilter(setSourceType, event.target.value)}
          placeholder="Tipo de fonte (ex: startup_evidence)"
          value={sourceType}
        />
      </div>

      {jobsQuery.isLoading ? <p className="text-[var(--muted)]">Carregando historico...</p> : null}
      {jobsQuery.isError ? <p className="rounded-md border border-[var(--danger)] p-4 text-[var(--danger)]">{jobsQuery.error.message}</p> : null}
      {!jobsQuery.isLoading && !jobsQuery.isError && !results?.items.length ? <p className="rounded-xl border border-[var(--surface-border)] bg-[var(--surface)] p-6 text-[var(--muted)]">Nenhum job corresponde aos filtros atuais.</p> : null}

      {results?.items.length ? <>
        <p className="text-sm text-[var(--muted)]">{results.total} job{results.total === 1 ? "" : "s"} no historico</p>
        <div className="space-y-3">
          {results.items.map((job) => (
            <Link className="flex items-center justify-between gap-4 rounded-xl border border-[var(--surface-border)] bg-[var(--surface)] p-4 transition hover:border-[var(--accent)]" href={`/jobs/${job.id}`} key={job.id}>
              <div className="min-w-0">
                <p className="truncate text-sm font-medium">{job.url}</p>
                <p className="mt-1 text-xs uppercase tracking-wide text-[var(--muted)]">{job.source_type} · {new Date(job.created_at).toLocaleString("pt-BR")}</p>
              </div>
              <span className={`shrink-0 rounded-full px-3 py-1 text-xs font-semibold ${job.status === "failed" ? "bg-[#3a1414] text-[var(--danger)]" : job.status === "completed" ? "bg-[#183414] text-[var(--accent)]" : "bg-[#20334d] text-[var(--muted)]"}`}>
                {STATUS_LABELS[job.status]}
              </span>
            </Link>
          ))}
        </div>
        {totalPages > 1 ? <nav aria-label="Paginacao do historico" className="flex items-center justify-between"><button className="rounded-md border border-[var(--surface-border)] px-3 py-2 disabled:opacity-50" disabled={page === 1} onClick={() => setPage((current) => current - 1)} type="button">Anterior</button><span className="text-sm text-[var(--muted)]">Pagina {page} de {totalPages}</span><button className="rounded-md border border-[var(--surface-border)] px-3 py-2 disabled:opacity-50" disabled={page === totalPages} onClick={() => setPage((current) => current + 1)} type="button">Proxima</button></nav> : null}
      </> : null}
    </div>
  );
}
