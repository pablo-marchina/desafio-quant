"use client";

import { useMutation, useQuery } from "@tanstack/react-query";
import { CheckCircle2, Download, FileBarChart, LoaderCircle, RotateCcw, Send, Sparkles } from "lucide-react";
import { useState } from "react";

import { ApiErrorState, InsufficientData } from "@/components/feedback";
import { StartupLogo } from "@/components/startup-logo";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { getJob, getStartups, getStartup, startActionReport } from "@/lib/api";
import { exportActionReportPdf } from "@/lib/report-pdf";
import type { ActionReportResult, Startup } from "@/lib/types";
import { useUserSession } from "@/lib/user-session";

type ReportContext = {
  product?: string;
  sector?: string;
  stage?: string;
  size?: string;
  urgency?: string;
};

export function ReportsPage() {
  const { userName } = useUserSession();
  const [startupId, setStartupId] = useState("");
  const [answer, setAnswer] = useState("");
  const [reportContext, setReportContext] = useState<ReportContext>({
    product: "recomende você mesmo"
  });
  const [confirmed, setConfirmed] = useState(false);
  const [jobId, setJobId] = useState<string>();
  const startupsQuery = useQuery({
    queryKey: ["startups", "reports-selector"],
    queryFn: ({ signal }) => getStartups({ page: 1, pageSize: 100 }, signal)
  });
  const selectedId = startupId || firstId(startupsQuery.data?.items);
  const startupQuery = useQuery({
    queryKey: ["startup", selectedId],
    queryFn: ({ signal }) => getStartup(selectedId, signal),
    enabled: Boolean(selectedId)
  });
  const selectedStartup =
    startupsQuery.data?.items.find(
      (item) => String(item.id || item.candidate_id || "") === selectedId
    ) || startupQuery.data;
  const mutation = useMutation({
    mutationFn: () =>
      startActionReport(selectedId, contextSummary(reportContext), {
        produto_alvo: reportContext.product || "recomende você mesmo",
        analista_nome: userName,
        perfil_ideal: {
          setor: reportContext.sector,
          estagio: reportContext.stage,
          porte: reportContext.size,
          urgencia: reportContext.urgency
        },
        confirmado_pelo_usuario: true
      }),
    onSuccess: (job) => setJobId(job.job_id)
  });
  const jobQuery = useQuery({
    queryKey: ["action-report-job", jobId],
    queryFn: ({ signal }) => getJob<ActionReportResult>(jobId!, signal),
    enabled: Boolean(jobId),
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      return status === "completed" || status === "failed" ? false : 1500;
    }
  });

  const job = jobQuery.data;
  const processing =
    mutation.isPending || job?.status === "queued" || job?.status === "running";
  const report =
    job?.status === "completed" ? job.result : startupQuery.data?.action_report;
  const error =
    mutation.error instanceof Error
      ? mutation.error.message
      : job?.status === "failed"
        ? job.error || "A geracao do relatorio falhou."
        : jobQuery.error instanceof Error
          ? jobQuery.error.message
          : undefined;

  function start() {
    if (!selectedId || !confirmed) return;
    setJobId(undefined);
    mutation.reset();
    mutation.mutate();
  }

  function submitAnswer(value = answer) {
    const text = value.trim();
    if (!text) return;
    setReportContext((current) => mergeAnswer(current, text));
    setAnswer("");
    setConfirmed(false);
  }

  function chooseProduct(product: string) {
    setReportContext((current) => ({ ...current, product }));
    setConfirmed(false);
  }

  function resetContext() {
    setReportContext({ product: "recomende você mesmo" });
    setAnswer("");
    setConfirmed(false);
    setJobId(undefined);
  }

  if (startupsQuery.isError) {
    return (
      <ApiErrorState
        message={
          startupsQuery.error instanceof Error
            ? startupsQuery.error.message
            : "Falha ao consultar startups."
        }
        onRetry={() => startupsQuery.refetch()}
      />
    );
  }

  return (
    <main className="mx-auto w-full min-w-0 max-w-[1500px] px-4 py-6 lg:px-8">
      <div className="mb-5">
        <p className="text-xs font-medium text-primary">Relatorio acionavel</p>
        <h1 className="mt-1 text-2xl font-semibold tracking-tight">Relatorios</h1>
        <p className="mt-1 max-w-2xl text-sm text-muted-foreground">
          Gere proximas acoes com uma LLM gratuita da OpenRouter usando dados da
          startup, recomendacao NVIDIA e comparacao VS Big Techs salva.
        </p>
      </div>

      <Card className="p-4">
        <div className="grid gap-4 xl:grid-cols-[minmax(0,360px)_minmax(0,1fr)_auto] xl:items-end">
          <StartupSelect
            items={startupsQuery.data?.items || []}
            loading={startupsQuery.isLoading}
            selectedStartup={selectedStartup}
            value={selectedId}
            onChange={(value) => {
              setStartupId(value);
              setJobId(undefined);
            }}
          />
          <ContextNegotiation
            answer={answer}
            confirmed={confirmed}
            context={reportContext}
            disabled={processing}
            onAnswerChange={setAnswer}
            onChooseProduct={chooseProduct}
            onConfirm={() => setConfirmed(true)}
            onReset={resetContext}
            onSubmit={submitAnswer}
          />
          <Button disabled={!selectedId || processing || !confirmed} onClick={start}>
            {processing ? (
              <LoaderCircle className="mr-2 size-4 animate-spin" />
            ) : report ? (
              <RotateCcw className="mr-2 size-4" />
            ) : (
              <Sparkles className="mr-2 size-4" />
            )}
            {processing ? "Gerando" : report ? "Gerar novamente" : "Gerar relatorio"}
          </Button>
        </div>
        {!confirmed && (
          <div className="mt-4 rounded-md border border-warning/30 bg-warning/5 p-3 text-xs text-warning">
            Confirme o resumo final para liberar a geração do relatório.
          </div>
        )}
        {!startupQuery.data?.nvidia_recommendation && selectedId && (
          <div className="mt-4 rounded-md border border-warning/30 bg-warning/5 p-3 text-xs text-warning">
            Esta startup ainda nao tem recomendacao NVIDIA salva. Gere a
            recomendacao antes do relatorio.
          </div>
        )}
        {processing && <Progress value={job?.progress ?? 0} />}
        {error && (
          <div className="mt-4 rounded-md border border-destructive/30 bg-destructive/5 p-3 text-sm text-destructive">
            {error}
          </div>
        )}
      </Card>

      <div className="mt-4">
        {startupQuery.isLoading || startupsQuery.isLoading ? (
          <Card className="p-6 text-sm text-muted-foreground">
            Carregando dados...
          </Card>
        ) : report ? (
          <ReportResult currentUserName={userName} report={report} />
        ) : (
          <Card>
            <InsufficientData message="Nenhum relatorio salvo para esta startup." />
          </Card>
        )}
      </div>
    </main>
  );
}

function StartupSelect({
  items,
  loading,
  selectedStartup,
  value,
  onChange
}: {
  items: Startup[];
  loading: boolean;
  selectedStartup?: Startup;
  value: string;
  onChange: (value: string) => void;
}) {
  return (
    <div className="min-w-0">
      <div className="mb-3 flex justify-center xl:justify-start">
        <StartupLogo
          className="size-16 rounded-lg bg-white/[0.035]"
          imageClassName="p-2"
          name={selectedStartup?.company_name}
          website={selectedStartup?.validated_url || selectedStartup?.website}
        />
      </div>
      <label className="block text-xs text-muted-foreground">
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
    </div>
  );
}

function ContextNegotiation({
  answer,
  confirmed,
  context,
  disabled,
  onAnswerChange,
  onChooseProduct,
  onConfirm,
  onReset,
  onSubmit
}: {
  answer: string;
  confirmed: boolean;
  context: ReportContext;
  disabled: boolean;
  onAnswerChange: (value: string) => void;
  onChooseProduct: (product: string) => void;
  onConfirm: () => void;
  onReset: () => void;
  onSubmit: () => void;
}) {
  const next = nextQuestion(context);
  const complete = !next;
  const phase = complete ? 6 : next.phase;
  return (
    <div className="min-w-0 rounded-md border border-border bg-white/[0.015] p-3">
      <div className="flex flex-wrap items-center gap-2">
        <Badge className="border-primary/20 bg-primary/10 text-primary">
          Fase {phase}
        </Badge>
        {confirmed && (
          <Badge className="border-primary/20 bg-primary/10 text-primary">
            <CheckCircle2 className="mr-1 size-3" />
            Contexto confirmado
          </Badge>
        )}
      </div>
      {complete ? (
        <div className="mt-3">
          <p className="text-xs text-muted-foreground">Resumo para prosseguir</p>
          <p className="mt-1 text-sm leading-6">{contextSummary(context)}</p>
          <div className="mt-3 flex flex-wrap gap-2">
            <Button disabled={disabled || confirmed} size="sm" onClick={onConfirm}>
              Pode prosseguir
            </Button>
            <Button disabled={disabled} size="sm" variant="outline" onClick={onReset}>
              Refazer contexto
            </Button>
          </div>
        </div>
      ) : (
        <div className="mt-3">
          <p className="text-sm font-medium">{next.prompt}</p>
          {next.field === "product" && (
            <div className="mt-3 flex flex-wrap gap-2">
              {["NIM", "NeMo", "Triton", "Metropolis", "recomende você mesmo"].map((item) => (
                <Button
                  disabled={disabled}
                  key={item}
                  size="sm"
                  variant="outline"
                  onClick={() => onChooseProduct(item)}
                >
                  {item}
                </Button>
              ))}
            </div>
          )}
          <div className="mt-3 flex gap-2">
            <Input
              disabled={disabled}
              placeholder={next.placeholder}
              value={answer}
              onChange={(event) => onAnswerChange(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === "Enter") onSubmit();
              }}
            />
            <Button disabled={disabled || !answer.trim()} size="icon" onClick={onSubmit}>
              <Send className="size-4" />
            </Button>
          </div>
          <p className="mt-2 text-[11px] leading-5 text-muted-foreground">
            Pode responder tudo de uma vez; o sistema reaproveita setor, estágio,
            porte e urgência quando conseguir identificar.
          </p>
        </div>
      )}
    </div>
  );
}

function ReportResult({
  currentUserName,
  report
}: {
  currentUserName: string;
  report: ActionReportResult;
}) {
  const registeredAnalystName = analystNameFromReport(report);

  return (
    <div className="space-y-3">
      <Card className="border-primary/20 bg-primary/5 p-4">
        <p className="text-sm font-medium">
          {currentUserName}, aqui está o relatório que você pediu.
        </p>
        <p className="mt-1 text-xs text-muted-foreground">
          Responsável registrado para esta análise:{" "}
          {registeredAnalystName || "não registrado neste relatório"}.
        </p>
      </Card>
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex flex-wrap items-center gap-2">
          {report.generated_at && (
            <Badge className="border-primary/20 bg-primary/10 text-primary">
              Salvo em {new Date(report.generated_at).toLocaleString("pt-BR")}
            </Badge>
          )}
          {report.model && <Badge className="text-muted-foreground">{report.model}</Badge>}
        </div>
        <Button size="sm" variant="outline" onClick={() => exportActionReportPdf(report)}>
          <Download className="mr-2 size-4" />
          Exportar PDF
        </Button>
      </div>
      {report.markdown_report && (
        <Card className="p-5">
          <MarkdownReport content={report.markdown_report} />
        </Card>
      )}
      <Card className="p-5">
        <div className="flex items-start gap-3">
          <div className="grid size-10 shrink-0 place-items-center rounded-md bg-primary/10 text-primary">
            <FileBarChart className="size-5" />
          </div>
          <div>
            <h2 className="text-lg font-semibold">Resumo executivo</h2>
            <p className="mt-2 text-sm leading-6 text-muted-foreground">
              {report.executive_summary || report.raw_report || "Dados insuficientes."}
            </p>
          </div>
        </div>
      </Card>
      <div className="grid gap-3 xl:grid-cols-[minmax(0,1.4fr)_minmax(0,1fr)]">
        <Card className="p-4">
          <h3 className="text-sm font-semibold">Proximas acoes sugeridas</h3>
          {report.next_actions?.length ? (
            <div className="mt-3 space-y-3">
              {report.next_actions.map((item, index) => (
                <div className="rounded-md border border-border p-3" key={index}>
                  <div className="flex flex-wrap items-center gap-2">
                    <p className="text-sm font-medium">
                      {item.action || "Acao nao informada"}
                    </p>
                    {item.priority && <Badge>{item.priority}</Badge>}
                    {item.timeframe && (
                      <Badge className="text-muted-foreground">{item.timeframe}</Badge>
                    )}
                  </div>
                  <p className="mt-2 text-xs leading-5 text-muted-foreground">
                    {item.rationale || "Sem justificativa detalhada."}
                  </p>
                  <div className="mt-2 grid gap-2 text-[11px] text-muted-foreground sm:grid-cols-2">
                    <span>Responsavel: {item.owner || "nao informado"}</span>
                    <span>Metrica: {item.success_metric || "nao informada"}</span>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <p className="mt-3 text-xs text-muted-foreground">Dados insuficientes.</p>
          )}
        </Card>
        <div className="space-y-3">
          <ListCard title="Foco NVIDIA" items={report.nvidia_focus || []} />
          <ListCard
            title="Implicacoes VS Big Techs"
            items={report.bigtech_implications || []}
          />
          <ListCard title="Riscos" items={report.risks || []} />
          <ListCard title="Perguntas abertas" items={report.open_questions || []} />
        </div>
      </div>
    </div>
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

function MarkdownReport({ content }: { content: string }) {
  const lines = content.split(/\r?\n/);
  return (
    <div className="space-y-3">
      {lines.map((line, index) => {
        const text = line.trim();
        if (!text) return <div className="h-1" key={index} />;
        if (text.startsWith("### ")) {
          return (
            <h3 className="pt-2 text-base font-semibold" key={index}>
              {text.replace(/^###\s+/, "")}
            </h3>
          );
        }
        if (text.startsWith("- ")) {
          return (
            <p className="pl-3 text-sm leading-6 text-muted-foreground" key={index}>
              {text}
            </p>
          );
        }
        return (
          <p className="text-sm leading-6 text-muted-foreground" key={index}>
            {text}
          </p>
        );
      })}
    </div>
  );
}

function Progress({ value }: { value: number }) {
  return (
    <div className="mt-4">
      <div className="mb-2 flex items-center justify-between text-[11px] text-muted-foreground">
        <span>Chamando OpenRouter e estruturando relatorio</span>
        <span>{value}%</span>
      </div>
      <div className="h-1.5 overflow-hidden rounded-full bg-white/[0.06]">
        <div className="h-full rounded-full bg-primary" style={{ width: `${Math.max(4, value)}%` }} />
      </div>
    </div>
  );
}

function firstId(items?: Startup[]) {
  const item = items?.[0];
  return item ? String(item.id || item.candidate_id || "") : "";
}

function nextQuestion(context: ReportContext) {
  if (!context.sector) {
    return {
      phase: 2,
      field: "sector",
      prompt: "Qual setor a parceria deve priorizar?",
      placeholder: "Ex.: saúde, indústria, varejo, financeiro"
    };
  }
  if (!context.stage) {
    return {
      phase: 3,
      field: "stage",
      prompt: "Qual estágio de startup é ideal para este ciclo?",
      placeholder: "Ex.: early, growth ou scale"
    };
  }
  if (!context.size) {
    return {
      phase: 4,
      field: "size",
      prompt: "Qual porte de parceiro faz sentido?",
      placeholder: "Ex.: pequeno time técnico, mid-market, enterprise"
    };
  }
  if (!context.urgency) {
    return {
      phase: 5,
      field: "urgency",
      prompt: "Qual é a urgência da parceria?",
      placeholder: "Ex.: alta para piloto imediato, média, baixa"
    };
  }
  return null;
}

function mergeAnswer(current: ReportContext, text: string): ReportContext {
  const inferred = inferContext(text);
  const next = { ...current, ...inferred };
  const question = nextQuestion(current);
  if (question && !next[question.field as keyof ReportContext]) {
    next[question.field as keyof ReportContext] = text;
  }
  return next;
}

function inferContext(text: string): ReportContext {
  const lower = text.toLocaleLowerCase("pt-BR");
  const result: ReportContext = {};
  if (/\bnim\b/.test(lower)) result.product = "NIM";
  else if (/\bnemo\b|ne-mo/.test(lower)) result.product = "NeMo";
  else if (/\btriton\b/.test(lower)) result.product = "Triton";
  else if (/\bmetropolis\b/.test(lower)) result.product = "Metropolis";
  else if (/recomende|recomendar|decida|voc[eê]/.test(lower)) {
    result.product = "recomende você mesmo";
  }
  if (/\bearly\b|inicial|seed|pre-seed|pré-seed/.test(lower)) result.stage = "early";
  else if (/\bgrowth\b|crescimento|serie a|série a|serie b|série b/.test(lower)) {
    result.stage = "growth";
  } else if (/\bscale\b|scale-up|scaleup|madura|enterprise/.test(lower)) {
    result.stage = "scale";
  }
  if (/urg[eê]ncia alta|urgente|imediat|30 dias|agora/.test(lower)) {
    result.urgency = "alta";
  } else if (/urg[eê]ncia m[eé]dia|m[eé]dia|trimestre|90 dias/.test(lower)) {
    result.urgency = "média";
  } else if (/urg[eê]ncia baixa|baixa|sem pressa|explorat/.test(lower)) {
    result.urgency = "baixa";
  }
  const sector = text.match(/setor(?:es)?\s*[:=-]\s*([^.;,\n]+)/i);
  if (sector?.[1]) result.sector = sector[1].trim();
  const size = text.match(/porte\s*[:=-]\s*([^.;,\n]+)/i);
  if (size?.[1]) result.size = size[1].trim();
  return result;
}

function contextSummary(context: ReportContext) {
  return [
    `Produto-alvo: ${context.product || "não definido"}`,
    `setor: ${context.sector || "não definido"}`,
    `estágio: ${context.stage || "não definido"}`,
    `porte: ${context.size || "não definido"}`,
    `urgência: ${context.urgency || "não definida"}`
  ].join("; ");
}

function analystNameFromReport(report: ActionReportResult) {
  const context = report.context;
  if (!context || typeof context !== "object") return undefined;
  const name = context.analista_nome;
  return typeof name === "string" && name.trim() ? name.trim() : undefined;
}
