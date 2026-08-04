"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ArrowRight,
  CheckCircle2,
  CircleAlert,
  Cpu,
  ExternalLink,
  LoaderCircle,
  RotateCcw,
  Sparkles
} from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import { createPortal } from "react-dom";

import { InsufficientData } from "@/components/feedback";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { getJob, startNvidiaRecommendation } from "@/lib/api";
import type {
  NvidiaRecommendationItem,
  NvidiaRecommendationResult
} from "@/lib/types";
import { cn } from "@/lib/utils";

type Props = {
  startupId: string;
  companyName: string;
  initialResult?: NvidiaRecommendationResult | null;
};

export function NvidiaRecommendations({ startupId, companyName, initialResult }: Props) {
  const queryClient = useQueryClient();
  const [jobId, setJobId] = useState<string>();
  const [need, setNeed] = useState("");
  const [portalTarget, setPortalTarget] = useState<HTMLElement | null>(null);
  const sectionRef = useRef<HTMLElement>(null);

  const startMutation = useMutation({
    mutationFn: () => startNvidiaRecommendation(startupId, need.trim()),
    onSuccess: (job) => setJobId(job.job_id)
  });

  const jobQuery = useQuery({
    queryKey: ["nvidia-recommendation-job", jobId],
    queryFn: ({ signal }) => getJob(jobId as string, signal),
    enabled: Boolean(jobId),
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      return status === "completed" || status === "failed" ? false : 1_500;
    }
  });

  const job = jobQuery.data;
  const processing =
    startMutation.isPending || job?.status === "queued" || job?.status === "running";
  const result =
    job?.status === "completed" ? job.result : !jobId ? initialResult : undefined;
  const error =
    startMutation.error instanceof Error
      ? startMutation.error.message
      : job?.status === "failed"
        ? job.error || "O processamento das recomendações falhou."
        : jobQuery.error instanceof Error
          ? jobQuery.error.message
          : undefined;

  useEffect(() => {
    if ((result || error) && sectionRef.current) {
      sectionRef.current.scrollIntoView({ behavior: "smooth", block: "start" });
    }
  }, [result, error]);

  useEffect(() => {
    if (job?.status === "completed") {
      void queryClient.invalidateQueries({ queryKey: ["dashboard-summary"] });
      void queryClient.invalidateQueries({ queryKey: ["startup", startupId] });
    }
  }, [job?.status, queryClient, startupId]);

  useEffect(() => {
    setPortalTarget(document.getElementById("nvidia-recommendations"));
  }, []);

  function start() {
    setJobId(undefined);
    startMutation.reset();
    startMutation.mutate();
  }

  return (
    <>
      <Card className="p-4">
        <div className="flex items-start gap-3">
          <div className="grid size-10 shrink-0 place-items-center rounded-md bg-primary/10 text-primary">
            <Cpu className="size-5" />
          </div>
          <div className="min-w-0 flex-1">
            <p className="text-sm font-medium">Recomendações NVIDIA</p>
            <p className="mt-1 text-xs leading-5 text-muted-foreground">
              Analise gaps documentados e relacione produtos sustentados pelas
              evidências do RAG.
            </p>
          </div>
        </div>
        <label
          className="mt-4 block text-xs font-medium text-muted-foreground"
          htmlFor={`nvidia-need-${startupId}`}
        >
          Necessidade ou gap atual (opcional)
        </label>
        <Input
          className="mt-2"
          disabled={processing}
          id={`nvidia-need-${startupId}`}
          onChange={(event) => setNeed(event.target.value)}
          placeholder="Ex.: reduzir o tempo de inferência dos modelos preditivos"
          value={need}
        />
        <p className="mt-2 text-[10px] leading-4 text-muted-foreground">
          Sem um gap, a recomendação será feita por aderência ao serviço atual.
        </p>
        {processing && (
          <div className="mt-4">
            <div className="mb-2 flex items-center justify-between text-[11px] text-muted-foreground">
              <span>Processando recomendações</span>
              <span>{job?.progress ?? 0}%</span>
            </div>
            <div className="h-1.5 overflow-hidden rounded-full bg-white/[0.06]">
              <div
                className="h-full rounded-full bg-primary transition-[width]"
                style={{ width: `${job?.progress ?? 4}%` }}
              />
            </div>
          </div>
        )}
        <Button
          className="mt-4 w-full"
          disabled={processing}
          onClick={start}
        >
          {processing ? (
            <LoaderCircle className="mr-2 size-4 animate-spin" />
          ) : result || error ? (
            <RotateCcw className="mr-2 size-4" />
          ) : (
            <Sparkles className="mr-2 size-4" />
          )}
          {processing
            ? "Analisando"
            : result || error
              ? "Gerar novamente"
              : "Verificar recomendações"}
          {!processing && <ArrowRight className="ml-2 size-4" />}
        </Button>
      </Card>

      {portalTarget &&
        (processing || result || error) &&
        createPortal(
          <section
            ref={sectionRef}
            className="scroll-mt-24 pt-8"
            aria-live="polite"
          >
            <RecommendationContent
              companyName={companyName}
              startupId={startupId}
              error={error}
              processing={processing}
              progress={job?.progress ?? 0}
              result={result}
              onRetry={start}
            />
          </section>,
          portalTarget
        )}
    </>
  );
}

function RecommendationContent({
  companyName,
  startupId,
  error,
  processing,
  progress,
  result,
  onRetry
}: {
  companyName: string;
  startupId: string;
  error?: string;
  processing: boolean;
  progress: number;
  result?: NvidiaRecommendationResult | null;
  onRetry: () => void;
}) {
  const structured = useMemo(() => parseStructured(result), [result]);
  const recommendations = result?.recommendations || [];
  const sources = result?.sources || [];

  return (
    <div>
      <div className="flex flex-col justify-between gap-3 sm:flex-row sm:items-end">
        <div>
          <p className="text-xs font-medium text-primary">Análise sob demanda</p>
          <h2 className="mt-1 text-2xl font-semibold tracking-tight">
            Recomendações NVIDIA para {companyName}
          </h2>
          <p className="mt-1 text-sm text-muted-foreground">
            Recomendações fundamentadas nos gaps e evidências disponíveis no RAG.
          </p>
        </div>
        {result && (
          <Badge className="w-fit border-primary/20 bg-primary/10 text-primary">
            <CheckCircle2 className="mr-1 size-3.5" />
            Análise concluída
          </Badge>
        )}
      </div>

      {processing ? (
        <Card className="mt-4 p-6">
          <div className="flex items-center gap-3">
            <LoaderCircle className="size-5 animate-spin text-primary" />
            <div className="flex-1">
              <div className="flex justify-between text-xs">
                <span>Consultando contexto e catálogo NVIDIA</span>
                <span className="text-muted-foreground">{progress}%</span>
              </div>
              <div className="mt-3 h-1.5 overflow-hidden rounded-full bg-white/[0.06]">
                <div
                  className="h-full rounded-full bg-primary transition-[width]"
                  style={{ width: `${Math.max(4, progress)}%` }}
                />
              </div>
            </div>
          </div>
        </Card>
      ) : error ? (
        <Card className="mt-4 flex flex-col items-center p-8 text-center">
          <CircleAlert className="size-6 text-destructive" />
          <p className="mt-3 text-sm font-medium">
            Não foi possível gerar as recomendações
          </p>
          <p className="mt-1 max-w-xl text-xs text-muted-foreground">{error}</p>
          <Button className="mt-4" size="sm" variant="outline" onClick={onRetry}>
            Tentar novamente
          </Button>
        </Card>
      ) : result ? (
        <>
          <div className="mt-4 space-y-3">
            {recommendations.length ? (
              recommendations.map((recommendation, index) => (
                <RecommendationCard
                  index={index}
                  item={recommendation}
                  sources={sources}
                  key={`${recommendation.produto || "produto"}-${index}`}
                />
              ))
            ) : (
              <Card>
                <InsufficientData message="As evidências atuais não sustentam uma recomendação de produto NVIDIA." />
              </Card>
            )}
          </div>

          <div className="hidden">
            <ListCard
              title="Pontos a validar"
              items={structured.pointsToValidate}
              empty="Nenhum ponto de validação foi retornado."
            />
            <ListCard
              title="Trade-offs"
              items={structured.tradeoffs}
              empty="Dados insuficientes para avaliar trade-offs."
            />
          </div>

          <div className="hidden">
            <Card className="p-4">
              <h3 className="text-sm font-semibold">Roadmap resumido</h3>
              <InlineList
                items={structured.roadmap}
                empty="O resultado não inclui etapas suficientes para um roadmap."
              />
            </Card>
            <Card className="p-4">
              <h3 className="text-sm font-semibold">
                Comparação com big tech semelhante
              </h3>
              <InlineList
                items={structured.bigtechComparison}
                empty="O resultado não inclui comparação competitiva suficiente."
              />
            </Card>
          </div>

          {result.sources && result.sources.length > 0 && (
            <Card className="mt-3 p-4">
              <h3 className="text-sm font-semibold">Fontes consultadas</h3>
              <div className="mt-3 flex flex-wrap gap-2">
                {result.sources.map((source, index) => (
                  <Badge
                    className="max-w-full bg-white/[0.025] text-muted-foreground"
                    key={`${source}-${index}`}
                  >
                    <span className="truncate">{source}</span>
                  </Badge>
                ))}
              </div>
            </Card>
          )}
        </>
      ) : null}
    </div>
  );
}

function RecommendationCard({
  item,
  index,
  sources
}: {
  item: NvidiaRecommendationItem;
  index: number;
  sources: string[];
}) {
  return (
    <Card className="overflow-hidden">
      <div className="grid min-w-0 lg:grid-cols-[260px_1fr_1fr]">
        <div className="border-b border-border p-5 lg:border-b-0 lg:border-r">
          <div className="flex items-start gap-3">
            <div className="grid size-11 shrink-0 place-items-center rounded-lg border border-primary/30 bg-primary/10 text-primary">
              <Cpu className="size-6" />
            </div>
            <div className="min-w-0">
              <p className="text-[10px] uppercase tracking-wider text-muted-foreground">
                Recomendação {index + 1}
              </p>
              <h3 className="mt-1 break-words text-lg font-semibold">
                {item.produto || "Produto não informado"}
              </h3>
            </div>
          </div>
          <Badge className="mt-4 border-primary/20 bg-primary/10 text-primary">
            Fundamentada no RAG
          </Badge>
        </div>
        <div className="border-b border-border p-5 lg:border-b-0 lg:border-r">
          <p className="text-xs font-semibold text-primary">Gap identificado</p>
          <p className="mt-3 text-sm leading-6 text-muted-foreground">
            {item.gap || "Dados insuficientes."}
          </p>
        </div>
        <div className="p-5">
          <p className="text-xs font-semibold text-primary">
            Por que faz sentido
          </p>
          <p className="mt-3 text-sm leading-6 text-muted-foreground">
            {item.justificativa || "Dados insuficientes."}
          </p>
          {item.fontes && item.fontes.length > 0 && (
            <div className="mt-4 flex flex-wrap gap-2">
              {item.fontes.map((source) => {
                const resolved = resolveSource(source, sources);
                return resolved.url ? (
                  <a
                    className="inline-flex max-w-full items-center gap-1 rounded-md border border-border px-2 py-1 text-[10px] text-muted-foreground hover:border-primary/30 hover:text-primary"
                    href={resolved.url}
                    key={source}
                    rel="noreferrer"
                    target="_blank"
                  >
                    <span className="truncate">{resolved.label}</span>
                    <ExternalLink className="size-2.5 shrink-0" />
                  </a>
                ) : (
                  <Badge className="max-w-full text-muted-foreground" key={source}>
                    <span className="truncate">{resolved.label}</span>
                  </Badge>
                );
              })}
            </div>
          )}
        </div>
      </div>
    </Card>
  );
}

function ListCard({
  title,
  items,
  empty
}: {
  title: string;
  items: string[];
  empty: string;
}) {
  return (
    <Card className="p-4">
      <h3 className="text-sm font-semibold">{title}</h3>
      {items.length ? (
        <ul className="mt-3 space-y-2">
          {items.map((item, index) => (
            <li
              className="flex items-start gap-2 text-xs leading-5 text-muted-foreground"
              key={`${item}-${index}`}
            >
              <CheckCircle2 className="mt-0.5 size-3.5 shrink-0 text-primary" />
              {item}
            </li>
          ))}
        </ul>
      ) : (
        <p className="mt-3 text-xs text-muted-foreground">{empty}</p>
      )}
    </Card>
  );
}

function InlineList({ items, empty }: { items: string[]; empty: string }) {
  if (!items.length) {
    return <p className="mt-3 text-xs text-muted-foreground">{empty}</p>;
  }
  return (
    <ul className="mt-3 space-y-2">
      {items.map((item, index) => (
        <li
          className="flex items-start gap-2 text-xs leading-5 text-muted-foreground"
          key={`${item}-${index}`}
        >
          <CheckCircle2 className="mt-0.5 size-3.5 shrink-0 text-primary" />
          {item}
        </li>
      ))}
    </ul>
  );
}

function parseStructured(result?: NvidiaRecommendationResult | null) {
  let data: Record<string, unknown> = result?.structured_output || {};
  if (!Object.keys(data).length && result?.recommendation) {
    try {
      const parsed = JSON.parse(result.recommendation);
      if (parsed && typeof parsed === "object" && !Array.isArray(parsed)) {
        data = parsed as Record<string, unknown>;
      }
    } catch {
      // The raw recommendation can be prose; the typed fields remain authoritative.
    }
  }
  return {
    tradeoffs: toStringArray(data.tradeoffs),
    pointsToValidate: toStringArray(
      data.pontos_a_validar || data.points_to_validate
    ),
    roadmap: toStringArray(result?.roadmap || data.roadmap),
    bigtechComparison: toStringArray(
      result?.comparacao_bigtechs ||
        data.comparacao_bigtechs ||
        data.comparacao_com_bigtechs ||
        data.bigtech_comparison
    )
  };
}

function resolveSource(source: string, sources: string[]) {
  const citation = source.match(/\[Fonte\s+(\d+)\]/i);
  const indexedSource = citation ? sources[Number(citation[1]) - 1] : undefined;
  const value = indexedSource || source;
  if (/^https?:\/\//i.test(value)) {
    return { label: value, url: value };
  }
  return { label: value, url: undefined };
}

function toStringArray(value: unknown) {
  return Array.isArray(value)
    ? value.filter((item): item is string => typeof item === "string")
    : [];
}
