"use client";

import { useMutation, useQuery } from "@tanstack/react-query";
import { BarChart3, ExternalLink, LoaderCircle, RotateCcw, Scale } from "lucide-react";
import { useMemo, useState } from "react";

import { ApiErrorState, InsufficientData } from "@/components/feedback";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { getJob, getStartups, getStartup, startCompetitiveAnalysis } from "@/lib/api";
import type { CompetitiveAnalysisResult, Startup } from "@/lib/types";

export function BigTechsPage() {
  const [startupId, setStartupId] = useState("");
  const [jobId, setJobId] = useState<string>();
  const approvedStartupsQuery = useQuery({
    queryKey: ["startups", "big-techs-selector", "APPROVED"],
    queryFn: ({ signal }) =>
      getStartups({ page: 1, pageSize: 100, validationStatus: "APPROVED" }, signal)
  });
  const reviewStartupsQuery = useQuery({
    queryKey: ["startups", "big-techs-selector", "REVIEW"],
    queryFn: ({ signal }) =>
      getStartups({ page: 1, pageSize: 100, validationStatus: "REVIEW" }, signal)
  });
  const selectableStartups = useMemo(
    () => uniqueStartups([
      ...(approvedStartupsQuery.data?.items || []),
      ...(reviewStartupsQuery.data?.items || [])
    ]),
    [approvedStartupsQuery.data?.items, reviewStartupsQuery.data?.items]
  );
  const startupsLoading = approvedStartupsQuery.isLoading || reviewStartupsQuery.isLoading;
  const startupsError = approvedStartupsQuery.error || reviewStartupsQuery.error;
  const selectedId = startupId || firstId(selectableStartups);
  const startupQuery = useQuery({
    queryKey: ["startup", selectedId],
    queryFn: ({ signal }) => getStartup(selectedId, signal),
    enabled: Boolean(selectedId)
  });
  const mutation = useMutation({
    mutationFn: () => startCompetitiveAnalysis(selectedId),
    onSuccess: (job) => setJobId(job.job_id)
  });
  const jobQuery = useQuery({
    queryKey: ["competitive-analysis-job", jobId],
    queryFn: ({ signal }) => getJob<CompetitiveAnalysisResult>(jobId!, signal),
    enabled: Boolean(jobId),
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      return status === "completed" || status === "failed" ? false : 1500;
    }
  });

  const job = jobQuery.data;
  const processing =
    mutation.isPending || job?.status === "queued" || job?.status === "running";
  const result =
    job?.status === "completed"
      ? job.result
      : startupQuery.data?.competitive_analysis;
  const error =
    mutation.error instanceof Error
      ? mutation.error.message
      : job?.status === "failed"
        ? job.error || "A comparacao falhou."
        : jobQuery.error instanceof Error
          ? jobQuery.error.message
          : undefined;

  function start() {
    if (!selectedId) return;
    setJobId(undefined);
    mutation.reset();
    mutation.mutate();
  }

  if (approvedStartupsQuery.isError || reviewStartupsQuery.isError) {
    return (
      <ApiErrorState
        message={
          startupsError instanceof Error
            ? startupsError.message
            : "Falha ao consultar startups."
        }
        onRetry={() => {
          void approvedStartupsQuery.refetch();
          void reviewStartupsQuery.refetch();
        }}
      />
    );
  }

  return (
    <main className="mx-auto w-full min-w-0 max-w-[1500px] px-4 py-6 lg:px-8">
      <div className="mb-5 flex flex-col justify-between gap-4 lg:flex-row lg:items-end">
        <div>
          <p className="text-xs font-medium text-primary">Comparacao competitiva</p>
          <h1 className="mt-1 text-2xl font-semibold tracking-tight">
            VS Big Techs
          </h1>
          <p className="mt-1 max-w-2xl text-sm text-muted-foreground">
            Compare a startup com um servico equivalente de big tech e salve o
            resultado no banco para reuso em relatorios.
          </p>
        </div>
        <StartupSelect
          items={selectableStartups}
          loading={startupsLoading}
          value={selectedId}
          onChange={(value) => {
            setStartupId(value);
            setJobId(undefined);
          }}
        />
      </div>

      <Card className="p-4">
        <div className="flex flex-col justify-between gap-3 md:flex-row md:items-center">
          <div className="flex items-start gap-3">
            <div className="grid size-10 shrink-0 place-items-center rounded-md bg-primary/10 text-primary">
              <Scale className="size-5" />
            </div>
            <div>
              <p className="text-sm font-medium">
                {startupQuery.data?.company_name || "Selecione uma startup"}
              </p>
              <p className="mt-1 text-xs text-muted-foreground">
                Gerar novamente atualiza o campo competitive_analysis.
              </p>
            </div>
          </div>
          <Button disabled={!selectedId || processing} onClick={start}>
            {processing ? (
              <LoaderCircle className="mr-2 size-4 animate-spin" />
            ) : result ? (
              <RotateCcw className="mr-2 size-4" />
            ) : (
              <BarChart3 className="mr-2 size-4" />
            )}
            {processing ? "Comparando" : result ? "Atualizar comparacao" : "Gerar comparacao"}
          </Button>
        </div>
        {processing && <Progress value={job?.progress ?? 0} />}
        {error && (
          <div className="mt-4 rounded-md border border-destructive/30 bg-destructive/5 p-3 text-sm text-destructive">
            {error}
          </div>
        )}
      </Card>

      <div className="mt-4">
        {startupQuery.isLoading || startupsLoading ? (
          <Card className="p-6 text-sm text-muted-foreground">
            Carregando dados...
          </Card>
        ) : result ? (
          <CompetitiveResult result={result} />
        ) : (
          <Card>
            <InsufficientData message="Nenhuma comparacao salva para esta startup." />
          </Card>
        )}
      </div>
    </main>
  );
}

function StartupSelect({
  items,
  loading,
  value,
  onChange
}: {
  items: Startup[];
  loading: boolean;
  value: string;
  onChange: (value: string) => void;
}) {
  return (
    <label className="min-w-0 text-xs text-muted-foreground lg:w-[360px]">
      Startup
      <select
        className="mt-2 h-10 w-full rounded-md border border-border bg-background px-3 text-sm text-foreground outline-none focus:border-primary/50"
        disabled={loading || items.length === 0}
        value={value}
        onChange={(event) => onChange(event.target.value)}
      >
        {items.map((item) => {
          const id = String(item.id || item.candidate_id || "");
          return (
            <option key={id} value={id}>
              {item.company_name || id}
            </option>
          );
        })}
      </select>
    </label>
  );
}

function CompetitiveResult({ result }: { result: CompetitiveAnalysisResult }) {
  const structured = useMemo(
    () => (result.structured_output || {}) as Record<string, unknown>,
    [result]
  );
  const comparison = objectValue(structured.comparacao_competitiva);
  const current = objectValue(comparison.comparacao_estado_atual);
  const summary = objectValue(comparison.comparacao_bigtechs_resumida);
  const validated = objectValue(comparison.servico_bigtech_validado);
  const pricing = objectValue(structured.pricing);
  const equivalents = equivalentItems(summary.equivalentes_big_tech);

  return (
    <div className="space-y-3">
      {result.generated_at && (
        <Badge className="border-primary/20 bg-primary/10 text-primary">
          Salvo em {new Date(result.generated_at).toLocaleString("pt-BR")}
        </Badge>
      )}
      <InfoCard
        title="Categoria funcional"
        rows={[
          ["Categoria", stringValue(summary.categoria_funcional)]
        ]}
      />
      <EquivalentsCard items={equivalents} />
      <div className="grid gap-3 lg:grid-cols-3">
        <InfoCard
          title="Onde a big tech vence"
          rows={[["Vantagem", stringValue(summary.vantagem_bigtech)]]}
        />
        <InfoCard
          title="Onde a startup vence"
          rows={[["Vantagem", stringValue(summary.vantagem_startup)]]}
        />
        <InfoCard
          title="Risco de substituicao"
          rows={[["Risco", stringValue(summary.risco_substituicao)]]}
        />
      </div>
      <InfoCard
        title="Servico big tech validado"
        rows={[
          ["Empresa", stringValue(validated.candidato_empresa)],
          ["Servico", stringValue(validated.titulo_produto || validated.candidato_titulo)],
          ["Status", stringValue(comparison.status_validacao)]
        ]}
        url={stringValue(validated.candidato_url)}
      />
      <div className="grid gap-3 lg:grid-cols-2">
        <ListCard title="Pontos fortes da startup" items={pointTexts(current.pontos_fortes_startup)} />
        <ListCard title="Pontos fortes da big tech" items={pointTexts(current.pontos_fortes_bigtech)} />
        <ListCard title="Pontos fracos da startup" items={pointTexts(current.pontos_fracos_startup)} />
        <ListCard title="Pontos fracos da big tech" items={pointTexts(current.pontos_fracos_bigtech)} />
      </div>
      <InfoCard
        title="Preco e custo-beneficio"
        rows={[
          ["Startup", priceText(objectValue(pricing.startup))],
          ["Big tech", priceText(objectValue(pricing.bigtech))],
          ["Analise", stringValue(pricing.analise_custo_beneficio)]
        ]}
      />
    </div>
  );
}

function Progress({ value }: { value: number }) {
  return (
    <div className="mt-4">
      <div className="mb-2 flex items-center justify-between text-[11px] text-muted-foreground">
        <span>Buscando e validando servico equivalente</span>
        <span>{value}%</span>
      </div>
      <div className="h-1.5 overflow-hidden rounded-full bg-white/[0.06]">
        <div className="h-full rounded-full bg-primary" style={{ width: `${Math.max(4, value)}%` }} />
      </div>
    </div>
  );
}

function InfoCard({ title, rows, url }: { title: string; rows: Array<[string, string]>; url?: string }) {
  return (
    <Card className="p-4">
      <div className="flex items-center justify-between gap-3">
        <h3 className="text-sm font-semibold">{title}</h3>
        {url && (
          <a className="text-primary hover:underline" href={url} rel="noreferrer" target="_blank">
            <ExternalLink className="size-4" />
          </a>
        )}
      </div>
      <div className="mt-3 space-y-2">
        {rows.map(([label, item]) => (
          <div className="grid gap-2 text-xs sm:grid-cols-[130px_minmax(0,1fr)]" key={label}>
            <span className="text-muted-foreground">{label}</span>
            <span className="break-words">{item || "Dados insuficientes"}</span>
          </div>
        ))}
      </div>
    </Card>
  );
}

function ListCard({ title, items }: { title: string; items: string[] }) {
  return (
    <Card className="p-4">
      <h3 className="text-sm font-semibold">{title}</h3>
      {items.length ? (
        <ul className="mt-3 space-y-2 text-xs leading-5 text-muted-foreground">
          {items.map((item, index) => (
            <li key={`${item}-${index}`}>{item}</li>
          ))}
        </ul>
      ) : (
        <p className="mt-3 text-xs text-muted-foreground">Dados insuficientes.</p>
      )}
    </Card>
  );
}

function EquivalentsCard({
  items
}: {
  items: Array<{ empresa: string; produto: string; como_resolve: string }>;
}) {
  return (
    <Card className="p-4">
      <h3 className="text-sm font-semibold">Equivalentes big tech</h3>
      {items.length ? (
        <div className="mt-3 grid gap-3 lg:grid-cols-2">
          {items.map((item, index) => (
            <div className="rounded-md border border-border p-3" key={`${item.empresa}-${item.produto}-${index}`}>
              <p className="text-xs font-medium">{item.empresa}</p>
              <p className="mt-1 text-sm">{item.produto}</p>
              <p className="mt-2 text-xs leading-5 text-muted-foreground">
                {item.como_resolve}
              </p>
            </div>
          ))}
        </div>
      ) : (
        <p className="mt-3 text-xs text-muted-foreground">
          Sem equivalente direto relevante em big tech, vantagem estrutural por especializacao.
        </p>
      )}
    </Card>
  );
}

function firstId(items?: Startup[]) {
  const item = items?.[0];
  return item ? String(item.id || item.candidate_id || "") : "";
}

function uniqueStartups(items: Startup[]) {
  const seen = new Set<string>();
  return items.filter((item) => {
    const id = String(item.id || item.candidate_id || "");
    if (!id || seen.has(id)) return false;
    seen.add(id);
    return true;
  });
}

function objectValue(value: unknown): Record<string, unknown> {
  return value && typeof value === "object" && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : {};
}

function stringValue(value: unknown) {
  return typeof value === "string" ? value : "";
}

function stringArray(value: unknown) {
  return Array.isArray(value)
    ? value.filter((item): item is string => typeof item === "string")
    : [];
}

function pointTexts(value: unknown) {
  return Array.isArray(value)
    ? value
        .map((item) => objectValue(item))
        .map((item) => [stringValue(item.aspecto), stringValue(item.evidencia)].filter(Boolean).join(": "))
        .filter(Boolean)
    : [];
}

function priceText(value: Record<string, unknown>) {
  return [stringValue(value.valor), stringValue(value.fonte_url)].filter(Boolean).join(" | ");
}

function equivalentItems(value: unknown) {
  return Array.isArray(value)
    ? value
        .map((item) => objectValue(item))
        .map((item) => ({
          empresa: stringValue(item.empresa),
          produto: stringValue(item.produto),
          como_resolve: stringValue(item.como_resolve)
        }))
        .filter((item) => item.empresa || item.produto || item.como_resolve)
    : [];
}
