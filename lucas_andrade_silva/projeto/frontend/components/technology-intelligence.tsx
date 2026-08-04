"use client";

import { useMutation, useQuery } from "@tanstack/react-query";
import { BrainCircuit, ExternalLink, LoaderCircle, RefreshCw } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";

import { InsufficientData } from "@/components/feedback";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  getJob,
  getStartup,
  startTechnologyIntelligence
} from "@/lib/api";
import type {
  TechnologyFinding,
  TechnologyIntelligenceReport
} from "@/lib/types";
import { cn } from "@/lib/utils";

type Props = {
  startupId: string;
  initialReport?: TechnologyIntelligenceReport | null;
};

export function TechnologyIntelligence({ startupId, initialReport }: Props) {
  const [jobId, setJobId] = useState<string>();
  const [startedAt, setStartedAt] = useState<number>();
  const started = useRef(false);
  const mutation = useMutation({
    mutationFn: () => startTechnologyIntelligence(startupId),
    onSuccess: (job) => setJobId(job.job_id)
  });
  const jobQuery = useQuery({
    queryKey: ["technology-intelligence-job", jobId],
    queryFn: ({ signal }) =>
      getJob<TechnologyIntelligenceReport>(jobId as string, signal),
    enabled: Boolean(jobId),
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      return status === "completed" || status === "failed" ? false : 1_500;
    }
  });
  const persistedQuery = useQuery({
    queryKey: ["technology-intelligence-persisted", startupId, jobId],
    queryFn: ({ signal }) => getStartup(startupId, signal),
    enabled: Boolean(jobId),
    refetchInterval: (query) => {
      const report = query.state.data?.technology_intelligence;
      return isFreshReport(report, startedAt) ? false : 2_000;
    }
  });

  function start() {
    started.current = true;
    setStartedAt(Date.now());
    setJobId(undefined);
    mutation.reset();
    mutation.mutate();
  }

  useEffect(() => {
    if (!initialReport && startupId && !started.current) start();
    // Run once when the company profile is opened.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [startupId, initialReport]);

  const job = jobQuery.data;
  const persistedReport = persistedQuery.data?.technology_intelligence;
  const freshPersistedReport = isFreshReport(persistedReport, startedAt)
    ? persistedReport
    : undefined;
  const report =
    job?.status === "completed"
      ? job.result
      : freshPersistedReport || (!jobId ? initialReport : undefined);
  const processing =
    !report &&
    (mutation.isPending ||
      job?.status === "queued" ||
      job?.status === "running");
  const error =
    mutation.error instanceof Error
      ? mutation.error.message
      : job?.status === "failed"
        ? job.error || "A pesquisa de stack falhou."
        : jobQuery.error instanceof Error
          ? jobQuery.error.message
          : undefined;

  if (processing) {
    return (
      <div className="py-5">
        <div className="flex items-center gap-3 text-sm">
          <LoaderCircle className="size-5 animate-spin text-primary" />
          Enriquecendo dados...
        </div>
        <div className="mt-4 h-1.5 overflow-hidden rounded-full bg-white/[0.06]">
          <div
            className="h-full rounded-full bg-primary transition-[width]"
            style={{ width: `${Math.max(4, job?.progress || 4)}%` }}
          />
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div>
        <InsufficientData message={error} />
        <Button className="mt-3" size="sm" variant="outline" onClick={start}>
          <RefreshCw className="mr-2 size-3.5" />
          Tentar novamente
        </Button>
      </div>
    );
  }

  if (!report) return null;
  return <Report report={report} onRefresh={start} />;
}

function Report({
  report,
  onRefresh
}: {
  report: TechnologyIntelligenceReport;
  onRefresh: () => void;
}) {
  const evidence = useMemo(
    () => new Map(report.fontes.map((source) => [source.id, source])),
    [report.fontes]
  );
  return (
    <div>
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-sm leading-6 text-muted-foreground">
            {report.perfil_geral.resumo}
          </p>
          <Badge className={cn("mt-2", certaintyClass(report.nivel_certeza.classificacao))}>
            Evidência {report.nivel_certeza.classificacao}
          </Badge>
        </div>
        <Button aria-label="Refazer pesquisa" size="icon" variant="ghost" onClick={onRefresh}>
          <RefreshCw className="size-3.5" />
        </Button>
      </div>
      <FindingGroup title="Infraestrutura e backend" items={report.infraestrutura_backend} evidence={evidence} />
      <FindingGroup title="Frontend e mobile" items={report.frontend_mobile} evidence={evidence} />
      <FindingGroup title="IA operacional (interno)" items={report.ia_operacional_interna} evidence={evidence} />
      <FindingGroup title="IA no produto/serviço (core)" items={report.ia_produto_core} evidence={evidence} />
      <AiRelationScore report={report} />
      <p className="mt-4 text-[10px] leading-4 text-muted-foreground">
        {report.nivel_certeza.justificativa}
      </p>
    </div>
  );
}

function AiRelationScore({ report }: { report: TechnologyIntelligenceReport }) {
  const requirements = [
    {
      label: "IA operacional",
      found: report.ia_operacional_interna.length > 0
    },
    {
      label: "IA no produto",
      found: report.ia_produto_core.length > 0
    }
  ];
  const found = requirements.filter((item) => item.found).length;
  const score = Math.round((found / requirements.length) * 100);

  return (
    <div className="mt-4 rounded-md border border-border bg-white/[0.015] p-3">
      <div className="flex items-center justify-between gap-3">
        <p className="text-xs font-medium">Score de relação com IA</p>
        <Badge className="border-primary/20 bg-primary/10 text-primary">
          {score}%
        </Badge>
      </div>
      <div className="mt-3 h-1.5 overflow-hidden rounded-full bg-white/[0.06]">
        <div className="h-full rounded-full bg-primary" style={{ width: `${score}%` }} />
      </div>
      <div className="mt-3 flex flex-wrap gap-2">
        {requirements.map((item) => (
          <Badge
            className={item.found ? "border-primary/20 bg-primary/10 text-primary" : "text-muted-foreground"}
            key={item.label}
          >
            {item.label}: {item.found ? "achado" : "não achado"}
          </Badge>
        ))}
      </div>
    </div>
  );
}

function FindingGroup({
  title,
  items,
  evidence
}: {
  title: string;
  items: TechnologyFinding[];
  evidence: Map<string, TechnologyIntelligenceReport["fontes"][number]>;
}) {
  return (
    <div className="mt-5 border-t border-border pt-4">
      <h3 className="flex items-center gap-2 text-xs font-medium">
        <BrainCircuit className="size-3.5 text-primary" />
        {title}
      </h3>
      {items.length === 0 ? (
        <p className="mt-2 text-xs text-muted-foreground">Nenhuma evidência pública encontrada.</p>
      ) : (
        <div className="mt-2 space-y-2">
          {items.map((item, index) => (
            <div className="rounded-md border border-border bg-white/[0.015] p-3" key={`${item.tecnologia}-${index}`}>
              <div className="flex flex-wrap items-center gap-2">
                <span className="text-xs font-medium">{item.tecnologia}</span>
                <Badge className={certaintyClass(item.certeza)}>{item.certeza}</Badge>
              </div>
              <p className="mt-1 text-xs leading-5 text-muted-foreground">{item.uso_provavel}</p>
              <div className="mt-2 flex flex-wrap gap-2">
                {item.evidencias.map((id) => {
                  const source = evidence.get(id);
                  return source ? (
                    <a className="inline-flex items-center gap-1 text-[10px] text-primary hover:underline" href={source.url} key={id} rel="noreferrer" target="_blank" title={source.titulo}>
                      {id}<ExternalLink className="size-2.5" />
                    </a>
                  ) : null;
                })}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function certaintyClass(value: string) {
  if (value === "Alta") return "border-primary/30 bg-primary/10 text-primary";
  if (value === "Média") return "border-warning/30 bg-warning/10 text-warning";
  return "text-muted-foreground";
}

function isFreshReport(
  report: TechnologyIntelligenceReport | null | undefined,
  startedAt?: number
) {
  if (!report) return false;
  if (!startedAt) return true;
  const researchedAt = report.pesquisado_em
    ? Date.parse(report.pesquisado_em)
    : Number.NaN;
  return Number.isFinite(researchedAt) && researchedAt >= startedAt - 1_000;
}
