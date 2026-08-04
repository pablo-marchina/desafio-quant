"use client";

import { useMutation, useQuery } from "@tanstack/react-query";
import { BarChart3, ExternalLink, LoaderCircle } from "lucide-react";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { getJob, startCompetitiveAnalysis } from "@/lib/api";
import type { CompetitiveAnalysisResult } from "@/lib/types";

type Props = {
  startupId: string;
  companyName: string;
};

export function CompetitiveAnalysis({ startupId, companyName }: Props) {
  const [active, setActive] = useState(false);
  const [jobId, setJobId] = useState<string>();
  const mutation = useMutation({
    mutationFn: () => startCompetitiveAnalysis(startupId),
    onSuccess: (job) => {
      setJobId(job.job_id);
      setActive(true);
    }
  });
  const jobQuery = useQuery({
    queryKey: ["competitive-analysis-job", jobId],
    queryFn: ({ signal }) => getJob<CompetitiveAnalysisResult>(jobId as string, signal),
    enabled: Boolean(jobId),
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      return status === "completed" || status === "failed" ? false : 1_500;
    }
  });

  function start() {
    setActive(true);
    setJobId(undefined);
    mutation.reset();
    mutation.mutate();
  }

  const job = jobQuery.data;
  const processing =
    mutation.isPending || job?.status === "queued" || job?.status === "running";
  const result = job?.status === "completed" ? job.result : undefined;
  const error =
    mutation.error instanceof Error
      ? mutation.error.message
      : job?.status === "failed"
        ? job.error || "A comparação competitiva falhou."
        : jobQuery.error instanceof Error
          ? jobQuery.error.message
          : undefined;

  return (
    <div className="mt-3">
      <Button className="w-full" variant={active ? "default" : "outline"} onClick={start}>
        <BarChart3 className="mr-2 size-4" />
        Abrir guia de comparação com big tech
      </Button>
      {active && (
        <Card className="mt-3 overflow-hidden">
            <div className="border-b border-border p-5">
              <div>
                <p className="text-xs font-medium text-primary">Comparação competitiva</p>
                <h2 className="mt-1 text-xl font-semibold">
                  {companyName} versus big tech semelhante
                </h2>
              </div>
            </div>
            <div className="p-5">
              {processing ? (
                <Processing progress={job?.progress ?? 0} />
              ) : error ? (
                <div className="rounded-md border border-destructive/30 bg-destructive/5 p-4 text-sm text-destructive">
                  {error}
                </div>
              ) : result ? (
                <CompetitiveResult result={result} />
              ) : (
                <Processing progress={0} />
              )}
            </div>
          </Card>
      )}
    </div>
  );
}

function Processing({ progress }: { progress: number }) {
  return (
    <div className="py-10">
      <div className="flex items-center gap-3 text-sm">
        <LoaderCircle className="size-5 animate-spin text-primary" />
        Buscando e validando serviço equivalente de big tech...
      </div>
      <div className="mt-4 h-1.5 overflow-hidden rounded-full bg-white/[0.06]">
        <div className="h-full rounded-full bg-primary" style={{ width: `${Math.max(4, progress)}%` }} />
      </div>
    </div>
  );
}

function CompetitiveResult({ result }: { result: CompetitiveAnalysisResult }) {
  const structured = (result.structured_output || {}) as Record<string, unknown>;
  const comparison = objectValue(structured.comparacao_competitiva);
  const current = objectValue(comparison.comparacao_estado_atual);
  const validated = objectValue(comparison.servico_bigtech_validado);
  const pricing = objectValue(structured.pricing);
  const insufficient = stringArray(structured.dados_insuficientes);

  return (
    <div className="space-y-3">
      <div className="grid gap-3 lg:grid-cols-2">
        <InfoCard
          title="Serviço big tech validado"
          rows={[
            ["Empresa", stringValue(validated.candidato_empresa)],
            ["Serviço", stringValue(validated.titulo_produto || validated.candidato_titulo)],
            ["Status", stringValue(comparison.status_validacao)]
          ]}
          url={stringValue(validated.candidato_url)}
        />
        <InfoCard
          title="Quem entrega mais hoje"
          rows={[
            ["Resultado", stringValue(current.quem_entrega_mais_hoje)],
            ["Justificativa", stringValue(current.justificativa)]
          ]}
        />
      </div>
      <div className="grid gap-3 lg:grid-cols-2">
        <ListCard title="Pontos fortes da startup" items={pointTexts(current.pontos_fortes_startup)} />
        <ListCard title="Pontos fortes da big tech" items={pointTexts(current.pontos_fortes_bigtech)} />
        <ListCard title="Pontos fracos da startup" items={pointTexts(current.pontos_fracos_startup)} />
        <ListCard title="Pontos fracos da big tech" items={pointTexts(current.pontos_fracos_bigtech)} />
      </div>
      <InfoCard
        title="Preço e custo-benefício"
        rows={[
          ["Startup", priceText(objectValue(pricing.startup))],
          ["Big tech", priceText(objectValue(pricing.bigtech))],
          ["Análise", stringValue(pricing.analise_custo_beneficio)]
        ]}
      />
      {insufficient.length > 0 && (
        <ListCard title="Dados insuficientes" items={insufficient} />
      )}
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
        {rows.map(([label, value]) => (
          <div className="grid gap-2 text-xs sm:grid-cols-[130px_minmax(0,1fr)]" key={label}>
            <span className="text-muted-foreground">{label}</span>
            <span className="break-words">{value || "Dados insuficientes"}</span>
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
