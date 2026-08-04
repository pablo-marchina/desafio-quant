"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import type { ReactNode } from "react";

import { getUrlIngestionJob, listUrlIngestionJobs } from "@/lib/api/radar-client";
import type { UrlIngestionJob, UrlIngestionStatus } from "@/lib/api/radar-types";

import { ORDERED_STATUSES as orderedStatuses, STATUS_LABELS as labels } from "./job-status-labels";

export function JobStatusPanel({ jobId }: { jobId: string }) {
  const query = useQuery({
    queryKey: ["url-ingestion-job", jobId],
    queryFn: () => getUrlIngestionJob(jobId),
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      return status === "completed" || status === "failed" ? false : 3000;
    },
  });
  const relatedQuery = useQuery({
    enabled: Boolean(query.data),
    queryKey: ["url-ingestion-job-related", jobId, query.data?.startup_id],
    queryFn: () => listUrlIngestionJobs({ page: 1, page_size: 100, source_type: "startup_evidence" }),
    refetchInterval: (relatedQuery) => {
      const family = buildJobFamily(jobId, query.data, relatedQuery.state.data?.items ?? []);
      return hasRunningJob(family) ? 3000 : false;
    },
  });

  if (query.isLoading) return <p className="mt-8 text-[var(--muted)]">Carregando job...</p>;
  if (query.isError) return <p className="mt-8 rounded-md border border-[var(--danger)] p-4 text-[var(--danger)]">{query.error.message}</p>;

  const job = query.data;
  if (!job) return <p className="mt-8 text-[var(--muted)]">Nenhum job encontrado.</p>;
  const family = buildJobFamily(jobId, job, relatedQuery.data?.items ?? []);
  const displayJob = selectDisplayJob(job, family);
  const isRescuingFailedRoot = job.status === "failed" && displayJob.id !== job.id && displayJob.status !== "failed";
  const currentIndex = orderedStatuses.indexOf(displayJob.status);
  return (
    <div className="mt-8 space-y-6">
      <section className="rounded-xl border border-[var(--surface-border)] bg-[var(--surface)] p-6">
        <p className="break-all text-sm text-[var(--muted)]">{displayJob.url}</p>
        <p className="mt-2 text-xl font-semibold">{labels[displayJob.status]}</p>
        {isRescuingFailedRoot && (
          <p className="mt-3 rounded-md border border-[var(--surface-border)] bg-[#13233a] p-3 text-sm text-[var(--muted)]">
            A fonte inicial foi rejeitada, mas a analise continua com fontes de enriquecimento.
          </p>
        )}
        <ol className="mt-8 space-y-3">
          {orderedStatuses.map((status, index) => (
            <li className="flex items-center gap-3" key={status}>
              <span className={`grid h-6 w-6 place-items-center rounded-full text-xs font-bold ${index <= currentIndex ? "bg-[var(--accent)] text-[#07111f]" : "bg-[#20334d] text-[var(--muted)]"}`}>{index + 1}</span>
              <span className={index <= currentIndex ? "text-white" : "text-[var(--muted)]"}>{labels[status]}</span>
            </li>
          ))}
        </ol>
        {displayJob.status === "failed" && <p className="mt-6 rounded-md border border-[var(--danger)] p-4 text-[var(--danger)]">{displayJob.error_message ?? "A analise falhou sem uma mensagem detalhada."}</p>}
        {displayJob.status === "completed" && displayJob.startup_id && (
          <Link className="mt-8 inline-flex rounded-md bg-[var(--accent)] px-5 py-3 font-semibold text-[#07111f]" href={`/startups/${displayJob.startup_id}`}>
            Ver resultado da startup
          </Link>
        )}
      </section>
      <JobAuditPanel family={family} job={displayJob} rootJob={job} />
    </div>
  );
}

const RUNNING_STATUSES = new Set<UrlIngestionStatus>(["pending", "scraping", "ingesting", "embedding", "analyzing"]);

function buildJobFamily(rootJobId: string, rootJob: UrlIngestionJob | undefined, jobs: UrlIngestionJob[]): UrlIngestionJob[] {
  if (!rootJob) return [];
  return [rootJob, ...jobs.filter((job) => job.parent_job_id === rootJobId && job.id !== rootJob.id)];
}

function hasRunningJob(jobs: UrlIngestionJob[]): boolean {
  return jobs.some((job) => RUNNING_STATUSES.has(job.status));
}

function selectDisplayJob(rootJob: UrlIngestionJob, family: UrlIngestionJob[]): UrlIngestionJob {
  const children = family.filter((job) => job.parent_job_id === rootJob.id);
  const completedChild = children.find((job) => job.status === "completed");
  if (completedChild) return completedChild;

  const runningChildren = children.filter((job) => RUNNING_STATUSES.has(job.status));
  if (runningChildren.length) {
    return runningChildren.sort((a, b) => orderedStatuses.indexOf(b.status) - orderedStatuses.indexOf(a.status))[0];
  }

  if (rootJob.status === "failed" && children.length) {
    const lastChild = [...children].sort((a, b) => Date.parse(b.created_at) - Date.parse(a.created_at))[0];
    return lastChild ?? rootJob;
  }

  return rootJob;
}

function JobAuditPanel({ family, job, rootJob }: { family: UrlIngestionJob[]; job: UrlIngestionJob; rootJob: UrlIngestionJob }) {
  const langfuseHost = process.env.NEXT_PUBLIC_LANGFUSE_HOST;
  const children = family.filter((item) => item.parent_job_id === rootJob.id);
  const completedCount = family.filter((item) => item.status === "completed").length;
  const failedCount = family.filter((item) => item.status === "failed").length;
  const runningCount = family.filter((item) => RUNNING_STATUSES.has(item.status)).length;
  const duration = formatDuration(job.started_at ?? job.created_at, job.finished_at);
  const stageIds = [
    ["Scraping", job.scraping_job_id],
    ["Resultado", job.scraping_result_id],
    ["Ingestao", job.ingestion_job_id],
    ["Documento", job.document_id],
    ["Embedding", job.embedding_job_id],
  ] as const;

  return (
    <section className="rounded-xl border border-[var(--surface-border)] bg-[var(--surface)] p-6">
      <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
        <div>
          <p className="text-xs uppercase tracking-wide text-[var(--muted)]">Auditoria do job</p>
          <h2 className="mt-1 text-lg font-semibold">Sinais de execucao e observabilidade</h2>
        </div>
        <div className="flex flex-wrap gap-2">
          {job.startup_id ? <AuditLink href={`/startups/${job.startup_id}`}>Startup</AuditLink> : null}
          {langfuseHost ? <AuditLink href={langfuseHost}>Langfuse</AuditLink> : null}
        </div>
      </div>

      <div className="mt-5 grid gap-3 md:grid-cols-4">
        <Metric label="Duracao" value={duration} />
        <Metric label="Enriquecimentos" value={String(children.length)} />
        <Metric label="Concluidos" value={String(completedCount)} />
        <Metric label="Falhas" value={String(failedCount)} tone={failedCount ? "danger" : "default"} />
      </div>

      <div className="mt-5 grid gap-4 lg:grid-cols-[1.2fr_0.8fr]">
        <div className="rounded-lg border border-[var(--surface-border)] bg-[#0a1728] p-4">
          <p className="text-sm font-semibold">Familia do job</p>
          <div className="mt-3 space-y-2">
            {family.map((item) => (
              <Link className="block rounded-md border border-[var(--surface-border)] px-3 py-2 text-sm transition hover:border-[var(--accent)]" href={`/jobs/${item.id}`} key={item.id}>
                <span className="flex items-center justify-between gap-3">
                  <span className="min-w-0 truncate">{item.parent_job_id ? "Fonte enriquecida" : "Fonte inicial"}</span>
                  <span className={`shrink-0 rounded-full px-2 py-0.5 text-xs ${item.status === "failed" ? "bg-[#3a1414] text-[var(--danger)]" : item.status === "completed" ? "bg-[#183414] text-[var(--accent)]" : "bg-[#20334d] text-[var(--muted)]"}`}>
                    {labels[item.status]}
                  </span>
                </span>
                <span className="mt-1 block truncate text-xs text-[var(--muted)]">{item.url}</span>
              </Link>
            ))}
          </div>
        </div>

        <div className="space-y-4">
          <div className="rounded-lg border border-[var(--surface-border)] bg-[#0a1728] p-4">
            <p className="text-sm font-semibold">Tempos</p>
            <dl className="mt-3 space-y-2 text-sm">
              <AuditRow label="Criado" value={formatDate(job.created_at)} />
              <AuditRow label="Iniciado" value={formatDate(job.started_at)} />
              <AuditRow label="Finalizado" value={formatDate(job.finished_at)} />
              <AuditRow label="Rodando" value={runningCount ? `${runningCount} etapa(s)` : "nao"} />
            </dl>
          </div>
          <div className="rounded-lg border border-[var(--surface-border)] bg-[#0a1728] p-4">
            <p className="text-sm font-semibold">IDs tecnicos</p>
            <dl className="mt-3 space-y-2 text-sm">
              <AuditRow label="Job" value={job.id} />
              <AuditRow label="Parent" value={job.parent_job_id} />
              <AuditRow label="Startup" value={job.startup_id} />
              <AuditRow label="Briefing" value={job.briefing_id} />
              <AuditRow label="Recs" value={job.recommendation_count?.toString() ?? null} />
            </dl>
          </div>
        </div>
      </div>

      <div className="mt-5 rounded-lg border border-[var(--surface-border)] bg-[#0a1728] p-4">
        <p className="text-sm font-semibold">Pipeline</p>
        <div className="mt-3 grid gap-2 md:grid-cols-5">
          {stageIds.map(([label, value]) => (
            <div className="rounded-md border border-[var(--surface-border)] px-3 py-2" key={label}>
              <p className="text-xs text-[var(--muted)]">{label}</p>
              <p className="mt-1 truncate text-sm" title={value ?? undefined}>{value ? "registrado" : "pendente"}</p>
            </div>
          ))}
        </div>
      </div>

      <p className="mt-4 text-sm text-[var(--muted)]">
        {langfuseHost
          ? "Use o ID do job, da startup ou do briefing como filtro no Langfuse para cruzar esta execucao com os spans do backend."
          : "Para mostrar atalho do Langfuse aqui, configure NEXT_PUBLIC_LANGFUSE_HOST no frontend."}
      </p>
    </section>
  );
}

function AuditLink({ children, href }: { children: ReactNode; href: string }) {
  const external = href.startsWith("http");
  return (
    <Link className="rounded-md border border-[var(--surface-border)] px-3 py-2 text-sm font-medium text-[var(--muted)] transition hover:border-[var(--accent)] hover:text-white" href={href} target={external ? "_blank" : undefined}>
      {children}
    </Link>
  );
}

function Metric({ label, value, tone = "default" }: { label: string; value: string; tone?: "default" | "danger" }) {
  return (
    <div className="rounded-lg border border-[var(--surface-border)] bg-[#0a1728] p-4">
      <p className="text-xs uppercase tracking-wide text-[var(--muted)]">{label}</p>
      <p className={`mt-2 text-xl font-semibold ${tone === "danger" ? "text-[var(--danger)]" : "text-white"}`}>{value}</p>
    </div>
  );
}

function AuditRow({ label, value }: { label: string; value: string | null | undefined }) {
  return (
    <div className="grid grid-cols-[92px_minmax(0,1fr)] gap-3">
      <dt className="text-[var(--muted)]">{label}</dt>
      <dd className="truncate" title={value ?? undefined}>{value ?? "nao informado"}</dd>
    </div>
  );
}

function formatDate(value: string | null): string | null {
  if (!value) return null;
  return new Date(value).toLocaleString("pt-BR");
}

function formatDuration(startValue: string | null, endValue: string | null): string {
  if (!startValue) return "nao iniciado";
  const start = Date.parse(startValue);
  const end = endValue ? Date.parse(endValue) : Date.now();
  if (Number.isNaN(start) || Number.isNaN(end) || end < start) return "indisponivel";
  const seconds = Math.max(0, Math.round((end - start) / 1000));
  if (seconds < 60) return `${seconds}s`;
  const minutes = Math.floor(seconds / 60);
  const remainingSeconds = seconds % 60;
  if (minutes < 60) return `${minutes}m ${remainingSeconds}s`;
  const hours = Math.floor(minutes / 60);
  const remainingMinutes = minutes % 60;
  return `${hours}h ${remainingMinutes}m`;
}
