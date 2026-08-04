"use client";

// Trace viewer (F5.7): os passos dos agentes de um run a partir do estado persistido (checkpoint,
// F2.2) via `GET /runs/{id}/trace`. Reusa os rotulos PT-BR da espinha (PIPELINE_STEPS, F5.3) e o
// rotulo de status do run (statusLabel). Degrada gracioso: run offline (sem LLM) esconde o rollup
// de custo; sem Langfuse no ar, sem o deep-link — o passo-a-passo vem todo do estado do grafo.

import { useEffect, useState } from "react";

import Link from "next/link";

import { cn } from "@/lib/utils";
import { getRunTrace, type RunTrace, type RunTraceStep } from "@/lib/api";
import { PIPELINE_STEPS, statusLabel } from "@/lib/pipeline";

// node -> rotulo PT-BR, reusando a espinha do console ao vivo (F5.3) — a chave tecnica vem da API.
const STEP_LABELS: Record<string, string> = Object.fromEntries(
  PIPELINE_STEPS.map((s) => [s.node, s.label]),
);

// Rotulo PT-BR do status de cada passo (TraceStepOut.status, F5.7).
const STEP_STATUS_LABELS: Record<RunTraceStep["status"], string> = {
  done: "Concluido",
  skipped: "Pulado",
  pending: "Pendente",
};

type Phase = "loading" | "ready" | "error";

export function RunTraceView({ runId }: { runId: string }) {
  const [trace, setTrace] = useState<RunTrace | null>(null);
  const [phase, setPhase] = useState<Phase>("loading");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let alive = true;
    getRunTrace(runId)
      .then((data) => {
        if (!alive) return;
        setTrace(data);
        setPhase("ready");
      })
      .catch((err) => {
        if (!alive) return;
        setError(err instanceof Error ? err.message : "Erro ao carregar o trace.");
        setPhase("error");
      });
    return () => {
      alive = false;
    };
  }, [runId]);

  return (
    <main className="flex flex-1 flex-col items-center bg-background text-foreground">
      <div className="w-full max-w-4xl px-6 py-16 sm:py-24">
        <header className="flex flex-col gap-3">
          <Link
            href="/consulta"
            className="w-fit text-sm text-muted-foreground hover:text-foreground"
          >
            ← Consulta
          </Link>
          <h1 className="text-3xl font-semibold tracking-tight sm:text-4xl">Trace do run</h1>
          <div className="flex flex-wrap items-center gap-3 text-sm text-muted-foreground">
            <span className="font-mono text-xs">run {runId}</span>
            {phase === "ready" && trace && (
              <>
                <span>·</span>
                <span>{statusLabel(trace.status)}</span>
                {trace.prompt_version && (
                  <span className="font-mono text-xs">prompts {trace.prompt_version}</span>
                )}
              </>
            )}
          </div>
        </header>

        <div className="mt-10">
          {phase === "loading" && <Card>Carregando...</Card>}
          {phase === "error" && error && <Card tone="error">{error}</Card>}
          {phase === "ready" && trace && <Body trace={trace} />}
        </div>
      </div>
    </main>
  );
}

function Body({ trace }: { trace: RunTrace }) {
  return (
    <div className="flex flex-col gap-10">
      {/* Rollup de custo (F2.9) + nota de orcamento (F2.11) — omitidos num run offline sem LLM. */}
      {(trace.usage || trace.budget_limited) && (
        <div className="flex flex-wrap items-center gap-3">
          {trace.usage && (
            <>
              <Metric label="Tokens" value={`${trace.usage.total_tokens}`} />
              <Metric label="Chamadas LLM" value={`${trace.usage.calls}`} />
              <Metric label="Custo" value={`US$ ${trace.usage.cost_usd.toFixed(4)}`} />
            </>
          )}
          {trace.budget_limited && (
            <span className="rounded-full border border-brand/40 px-3 py-1 text-xs text-brand-ink">
              Orcamento de LLM atingido (F2.11)
            </span>
          )}
        </div>
      )}

      {trace.langfuse_url && (
        <a
          href={trace.langfuse_url}
          target="_blank"
          rel="noopener noreferrer"
          className="w-fit rounded-lg border border-border px-4 py-2 text-sm text-brand-ink hover:bg-accent"
        >
          Abrir trace completo no Langfuse →
        </a>
      )}

      <section className="flex flex-col gap-4">
        <h2 className="text-base font-semibold">Passos dos agentes</h2>
        <ol className="flex flex-col">
          {trace.steps.map((step) => (
            <StepRow key={step.node} step={step} />
          ))}
        </ol>
        <p className="text-xs text-muted-foreground">
          Reconstruido do estado persistido do run (checkpoint, F2.2): cada passo e &quot;Concluido&quot;
          quando deixou seu artefato no estado, &quot;Pulado&quot; quando o run terminou sem passar por
          ele (ramo terminal ou etapa opcional sem saida) e &quot;Pendente&quot; quando o run pausou
          antes de chegar.
        </p>
      </section>

      {trace.errors.length > 0 && (
        <section className="flex flex-col gap-2">
          <h2 className="text-base font-semibold">Notas e erros rastreaveis</h2>
          <ul className="flex flex-col gap-1">
            {trace.errors.map((err, i) => (
              <li key={i} className="text-sm text-muted-foreground">
                — {err}
              </li>
            ))}
          </ul>
        </section>
      )}
    </div>
  );
}

// Uma linha da espinha: marcador por status + rotulo PT-BR + resumo do que o no produziu.
function StepRow({ step }: { step: RunTraceStep }) {
  const label = STEP_LABELS[step.node] ?? step.node;
  return (
    <li className="flex items-center gap-3 border-b border-border py-3 last:border-b-0">
      <StepMarker status={step.status} />
      <div className="flex flex-1 flex-col gap-0.5">
        <span
          className={cn(
            "text-sm",
            step.status === "done" ? "text-foreground" : "text-muted-foreground",
          )}
        >
          {label}
        </span>
        {step.summary && <span className="text-xs text-muted-foreground">{step.summary}</span>}
      </div>
      <span
        className={cn(
          "shrink-0 text-xs",
          step.status === "done" ? "text-brand-ink" : "text-muted-foreground",
        )}
      >
        {STEP_STATUS_LABELS[step.status]}
      </span>
    </li>
  );
}

// Marcador por status: check (done), tracinho (skipped) ou anel vazio (pending).
function StepMarker({ status }: { status: RunTraceStep["status"] }) {
  if (status === "done") {
    return (
      <span className="flex size-5 shrink-0 items-center justify-center rounded-full bg-primary text-[11px] font-bold text-primary-foreground">
        ✓
      </span>
    );
  }
  if (status === "skipped") {
    return (
      <span className="flex size-5 shrink-0 items-center justify-center rounded-full border-2 border-dashed border-muted text-[11px] text-muted-foreground">
        –
      </span>
    );
  }
  return <span className="size-5 shrink-0 rounded-full border-2 border-muted" />;
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex min-w-28 flex-col gap-1 rounded-lg border border-border bg-card p-4">
      <span className="text-xs text-muted-foreground">{label}</span>
      <span className="font-mono text-lg">{value}</span>
    </div>
  );
}

function Card({ children, tone }: { children: React.ReactNode; tone?: "error" }) {
  return (
    <p
      className={cn(
        "rounded-lg border border-border bg-card px-4 py-6 text-sm",
        tone === "error" ? "text-destructive" : "text-muted-foreground",
      )}
    >
      {children}
    </p>
  );
}
