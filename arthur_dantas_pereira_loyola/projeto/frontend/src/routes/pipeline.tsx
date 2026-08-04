import { createFileRoute } from "@tanstack/react-router";
import { useState, useEffect, useRef, useMemo, useCallback } from "react";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { toast } from "sonner";
import { useSubmitRun, useRun } from "@/lib/hooks/use-runs";
import {
  PipelineStatus,
  type PipelineStepData,
} from "@/components/pipeline-status";
import { ApiErrorDisplay } from "@/components/api-error-display";
import { Sparkles, ArrowRight } from "lucide-react";
import type { PipelineStepRecord } from "@/lib/api";

type PipelineSearch = {
  query?: string;
  autoRun?: boolean;
};

export const Route = createFileRoute("/pipeline")({
  validateSearch: (search: Record<string, unknown>): PipelineSearch => ({
    query: typeof search.query === "string" ? search.query : undefined,
    autoRun: search.autoRun === true || search.autoRun === "true",
  }),
  head: () => ({ meta: [{ title: "Pipeline Multiagente - NVIDIA Toph" }] }),
  component: PipelinePage,
});

function formatDurationSeconds(seconds: number): string {
  const safeSeconds = Math.max(0, seconds);
  const m = Math.floor(safeSeconds / 60);
  return m > 0 ? `${m}m ${safeSeconds % 60}s` : `${safeSeconds}s`;
}

function parseRunTimestamp(value: string | null | undefined): number | null {
  if (!value) return null;
  const normalized = value.includes("T")
    ? value
    : `${value.replace(" ", "T")}Z`;
  const parsed = Date.parse(normalized);
  return Number.isNaN(parsed) ? null : parsed;
}

const STEP_KEYS = [
  "search_planner",
  "scraper",
  "extractor",
  "validator",
  "classifier",
  "nvidia_rag",
  "recommendation",
  "briefing",
];

function mapStepStatus(
  status: PipelineStepRecord["status"],
): PipelineStepData["status"] {
  if (status === "completed") return "done";
  if (status === "failed") return "error";
  if (status === "pending") return "idle";
  if (status === "idle" || status === "running" || status === "error")
    return status;
  return "idle";
}

function PipelinePage() {
  const search = Route.useSearch();
  const [query, setQuery] = useState("");
  const [startupName, setStartupName] = useState("");
  const [runId, setRunId] = useState<number | null>(null);
  const [startedAt, setStartedAt] = useState<number | null>(null);
  const [elapsed, setElapsed] = useState(0);
  const timerRef = useRef<ReturnType<typeof setInterval> | undefined>(
    undefined,
  );
  const autoRunRef = useRef<string | null>(null);

  const {
    mutate: execute,
    isPending: isSubmitting,
    error: submitError,
  } = useSubmitRun();
  const {
    data: runDetail,
    isLoading: isPolling,
    error: pollError,
  } = useRun(runId);

  const isRunning =
    isSubmitting ||
    runDetail?.status === "pending" ||
    runDetail?.status === "running";
  const hasResult = runDetail?.status === "completed";
  const hasError = runDetail?.status === "failed";

  // Tick timer while running
  useEffect(() => {
    if (runDetail?.status === "pending" || runDetail?.status === "running") {
      timerRef.current = setInterval(() => {
        setElapsed(Math.floor((Date.now() - (startedAt ?? Date.now())) / 1000));
      }, 1000);
    } else {
      clearInterval(timerRef.current);
    }
    return () => clearInterval(timerRef.current);
  }, [runDetail?.status, startedAt]);

  // Build step data from run state (real API steps when available)
  const steps = useMemo<PipelineStepData[]>(() => {
    if (!runId) return [];

    const apiSteps = runDetail?.steps;
    if (!apiSteps || apiSteps.length === 0) {
      // No steps yet - show all as idle while polling begins
      return STEP_KEYS.map((key) => ({
        key,
        status: (isRunning ? "idle" : hasResult ? "done" : "idle") as
          | "idle"
          | "running"
          | "done"
          | "error",
      }));
    }

    return STEP_KEYS.map((key) => {
      const api = apiSteps.find((s) => s.step_key === key);
      if (!api) {
        return { key, status: "idle" as const };
      }

      const status = mapStepStatus(api.status);
      const started = api.started_at
        ? new Date(api.started_at).getTime()
        : null;
      const completed = api.completed_at
        ? new Date(api.completed_at).getTime()
        : null;

      return {
        key,
        status,
        detail: api.detail ?? undefined,
        errorMessage: api.error_message ?? undefined,
        elapsedSeconds:
          status === "running" && started
            ? Math.floor((Date.now() - started) / 1000)
            : started && completed
              ? Math.floor((completed - started) / 1000)
              : undefined,
      };
    });
  }, [runDetail?.steps, runId, isRunning, hasResult]);

  const displayElapsed = useMemo(() => {
    const started = parseRunTimestamp(runDetail?.created_at);
    if (!started) return elapsed;
    const completed = parseRunTimestamp(runDetail?.completed_at);
    return Math.floor(((completed ?? Date.now()) - started) / 1000);
  }, [elapsed, runDetail?.completed_at, runDetail?.created_at]);

  const validationBlocked = Boolean(
    hasResult &&
    runDetail?.validation &&
    !runDetail.validation.has_minimum_evidence,
  );

  const displayError = submitError ?? pollError ?? null;

  const executePipeline = useCallback(
    (rawQuery: string, rawStartupName = startupName) => {
      const nextQuery = rawQuery.trim();
      if (!nextQuery) {
        toast.error("Digite uma consulta para executar o pipeline.");
        return;
      }
      const nextStartupName = rawStartupName.trim();
      setQuery(nextQuery);
      setStartupName(nextStartupName);
      setRunId(null);
      setStartedAt(Date.now());
      setElapsed(0);
      execute(
        { query: nextQuery, startupName: nextStartupName || undefined },
        {
          onSuccess: (res) => {
            setRunId(res.run_id);
            toast.success("Pipeline iniciado!");
          },
          onError: (err: unknown) => {
            const msg =
              err && typeof err === "object" && "message" in err
                ? String((err as { message: string }).message)
                : "Erro ao iniciar pipeline";
            toast.error(msg);
          },
        },
      );
    },
    [execute, startupName],
  );

  useEffect(() => {
    const incomingQuery = search.query?.trim();
    if (!incomingQuery) return;

    setQuery(incomingQuery);
    if (
      search.autoRun &&
      autoRunRef.current !== incomingQuery &&
      !isRunning &&
      !runId
    ) {
      autoRunRef.current = incomingQuery;
      executePipeline(incomingQuery);
    }
  }, [executePipeline, isRunning, runId, search.autoRun, search.query]);

  const handleSubmit = () => executePipeline(query);

  return (
    <div className="mx-auto w-full max-w-7xl space-y-5 p-4 md:p-6">
      <div>
        <h1 className="text-lg font-semibold text-foreground">
          Pipeline Multiagente
        </h1>
        <p className="text-xs text-muted-foreground">
          Executa o fluxo completo: busca, coleta, extracao, classificacao,
          validacao, RAG NVIDIA, recomendacao e briefing.
        </p>
      </div>

      {/* Search input */}
      <Card className="p-4">
        <div className="flex flex-col gap-3 sm:flex-row">
          <div className="flex flex-1 flex-col gap-2">
            <Input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && handleSubmit()}
              placeholder='Ex: "startups brasileiras de IA para saude", "agentes LLM em fintechs"...'
              className="h-10"
              disabled={isRunning}
            />
            <Input
              value={startupName}
              onChange={(e) => setStartupName(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && handleSubmit()}
              placeholder="Nome completo da startup (opcional)"
              className="h-10"
              disabled={isRunning}
            />
          </div>
          <Button
            size="default"
            className="h-10 gap-1.5"
            onClick={handleSubmit}
            disabled={isRunning || !query.trim()}
          >
            {isRunning ? (
              <>Processando...</>
            ) : (
              <>
                <Sparkles className="h-4 w-4" /> Executar Pipeline
              </>
            )}
          </Button>
        </div>
      </Card>

      {/* Pipeline status */}
      {(isRunning || hasResult || hasError) && (
        <Card className="p-4">
          <PipelineStatus
            steps={steps}
            elapsedSeconds={displayElapsed}
            overallStatus={
              hasResult ? "completed" : hasError ? "error" : "pending"
            }
          />
        </Card>
      )}

      {/* Error display */}
      {displayError && !isRunning && (
        <ApiErrorDisplay
          error={
            displayError &&
            typeof displayError === "object" &&
            "endpoint" in displayError
              ? (displayError as unknown as {
                  endpoint: string;
                  status: number;
                  message: string;
                })
              : {
                  endpoint: runId ? `GET /runs/${runId}` : "POST /runs",
                  status: 0,
                  message: String(displayError),
                }
          }
          onRetry={handleSubmit}
        />
      )}

      {/* Results */}
      {hasResult && runDetail && (
        <div className="space-y-4">
          <Card className="p-4">
            <div className="flex items-center justify-between">
              <div>
                <h2 className="text-sm font-semibold text-foreground">
                  Pipeline concluido
                </h2>
                <p className="text-xs text-muted-foreground">
                  Consulta: "{runDetail.query}" - Duracao:{" "}
                  {formatDurationSeconds(displayElapsed)}
                </p>
              </div>
              <Badge
                variant="outline"
                className="gap-1.5 border-green-500/30 bg-green-500/10 text-green-600"
              >
                Run #{runDetail.id}
              </Badge>
            </div>
          </Card>

          {/* Recommendations */}
          {runDetail.recommendations.length > 0 && (
            <Card className="p-4">
              <h3 className="mb-3 text-sm font-semibold text-foreground">
                Recomendacoes NVIDIA ({runDetail.recommendations.length})
              </h3>
              <div className="space-y-2">
                {runDetail.recommendations.map((r) => (
                  <div
                    key={r.id}
                    className="rounded-md border border-border p-3"
                  >
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="text-sm font-medium text-foreground">
                        {r.technology}
                      </span>
                      <Badge variant="outline" className="text-[10px]">
                        Prioridade {r.priority}
                      </Badge>
                      <Badge variant="outline" className="text-[10px]">
                        Complexidade {r.implementation_complexity}
                      </Badge>
                    </div>
                    <p className="mt-1 text-xs text-foreground">
                      <span className="font-medium">Gap alvo:</span>{" "}
                      {r.target_gap}
                    </p>
                    <p className="mt-0.5 text-xs text-muted-foreground">
                      <span className="font-medium">Tecnico:</span>{" "}
                      {r.technical_justification}
                    </p>
                    <p className="text-xs text-muted-foreground">
                      <span className="font-medium">Negocio:</span>{" "}
                      {r.business_justification}
                    </p>
                    <p className="mt-1 text-[11px] text-primary">
                      Proxima acao: {r.suggested_next_action}
                    </p>
                  </div>
                ))}
              </div>
            </Card>
          )}

          {/* No results */}
          {runDetail.recommendations.length === 0 && (
            <Card className="p-4">
              <div className="flex flex-col gap-3">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <h3 className="text-sm font-semibold text-foreground">
                    {validationBlocked
                      ? "Recomendacoes bloqueadas pela validacao"
                      : "Nenhuma recomendacao gerada"}
                  </h3>
                  {runDetail.validation && (
                    <Badge variant="outline" className="text-[10px]">
                      Evidencia {runDetail.validation.source_quality}
                    </Badge>
                  )}
                </div>
                {runDetail.validation?.caveats.length ? (
                  <ul className="space-y-1 text-xs text-muted-foreground">
                    {runDetail.validation.caveats.map((caveat) => (
                      <li key={caveat}>- {caveat}</li>
                    ))}
                  </ul>
                ) : (
                  <p className="text-sm text-muted-foreground">
                    Pipeline executou mas nao gerou recomendacoes. Verifique os
                    steps acima para detalhes.
                  </p>
                )}
              </div>
            </Card>
          )}

          <div className="flex justify-end">
            <Button
              variant="outline"
              size="sm"
              className="gap-1.5"
              onClick={handleSubmit}
            >
              <Sparkles className="h-3.5 w-3.5" /> Executar novamente
            </Button>
          </div>
        </div>
      )}

      {/* Rules card (always visible) */}
      <Card className="p-4">
        <h3 className="mb-2 text-sm font-semibold text-foreground">
          Regras do pipeline
        </h3>
        <ul className="grid gap-1.5 text-xs text-foreground sm:grid-cols-2">
          <li>
            - Coleta restrita a informacoes publicas, respeitando robots.txt.
          </li>
          <li>- URL e trecho original sempre preservados como evidencia.</li>
          <li>
            - Classificacao AI-Native / AI-Enabled / Non-AI com criterios
            explicitos.
          </li>
          <li>- Recomendacao NVIDIA exige ao menos uma evidencia validada.</li>
          <li>- Base NVIDIA consultada via RAG antes de toda recomendacao.</li>
          <li>
            - Briefing executivo agrega justificativa tecnica e de negocio.
          </li>
        </ul>
      </Card>
    </div>
  );
}
