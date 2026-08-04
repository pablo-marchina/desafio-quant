"use client";

// Console de consulta (F5.3): dois modos (lookup de uma empresa / descoberta por setor) e
// acompanhamento ao vivo do pipeline via SSE. Enfileira em `POST /runs`, abre um EventSource
// no `GET /runs/{id}` e desenha a espinha do grafo conforme os nos terminam (F2.10).
//
// HITL sync (F5.10): no single-company o grafo pausa no interrupt (F2.8) e o evento terminal
// chega com status `awaiting_review`. O console busca o payload de revisao (`GET /runs/{id}/
// review`) e mostra o painel de aprovacao (classe/AIMI/recs) para o gerente aprovar, editar ou
// rejeitar; a decisao vai em `POST /runs/{id}/resume` e o stream e reaberto para seguir os nos
// restantes (human_review -> briefing) ate o desfecho.

import { useEffect, useRef, useState } from "react";

import Link from "next/link";

import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import {
  briefingUrl,
  createRun,
  getRunReview,
  getRunStatus,
  getRunTrace,
  type ProgressEvent,
  type ResumeDecision,
  resumeRun,
  type RunMode,
  type RunReview,
  runStreamUrl,
} from "@/lib/api";
import { END_NODE, hasBriefing, PIPELINE_STEPS, statusLabel } from "@/lib/pipeline";

type Phase = "idle" | "starting" | "streaming" | "done" | "error";

const MODES: ReadonlyArray<{ mode: RunMode; titulo: string; placeholder: string }> = [
  {
    mode: "single_company",
    titulo: "Empresa",
    placeholder: "Nome ou dominio da empresa (ex.: minha-startup.ai)",
  },
  {
    mode: "discovery",
    titulo: "Descoberta",
    placeholder: "Setor / regiao (ex.: healthtech em Sao Paulo)",
  },
];

// Estado terminal do run que pausa (nao concluiu) p/ revisao humana (HITL sync, F2.8).
const PAUSED = "awaiting_review";

// Classes de maturidade (Classification, packages/schemas/enums.py — §5.1) p/ o select de edicao.
const CLASSES: ReadonlyArray<string> = ["AI-native", "AI-enabled", "non-AI"];

// --- Reconexao da consulta (F5.3+) -------------------------------------------
// O run roda no worker (F2.10) e SOBREVIVE a sair da tela; so a UI perdia o handle. Guardamos o
// run em andamento no localStorage (sobrevive a fechar a aba) e, ao reabrir a tela, reencontramos
// o run via GET /runs/{id}/status: rodando -> reabre o SSE; pausado/terminado -> hidrata do
// checkpoint (o pub/sub de progresso nao reentrega o que ja passou). TTL curto evita ressuscitar
// consulta antiga.
const ACTIVE_RUN_KEY = "tapi:consulta:active-run";
const ACTIVE_RUN_TTL_MS = 12 * 60 * 60 * 1000; // 12h

type StoredRun = { runId: string; mode: RunMode; query: string; ts: number };

function saveActiveRun(run: { runId: string; mode: RunMode; query: string }): void {
  try {
    localStorage.setItem(ACTIVE_RUN_KEY, JSON.stringify({ ...run, ts: Date.now() }));
  } catch {
    // localStorage indisponivel (modo privado) — degrada p/ o comportamento antigo, sem reconexao.
  }
}

function loadActiveRun(): StoredRun | null {
  try {
    const raw = localStorage.getItem(ACTIVE_RUN_KEY);
    if (!raw) return null;
    const run = JSON.parse(raw) as StoredRun;
    if (!run?.runId || Date.now() - run.ts > ACTIVE_RUN_TTL_MS) {
      localStorage.removeItem(ACTIVE_RUN_KEY);
      return null;
    }
    return run;
  } catch {
    return null;
  }
}

function clearActiveRun(): void {
  try {
    localStorage.removeItem(ACTIVE_RUN_KEY);
  } catch {
    // no-op
  }
}

// Evento terminal sintetico p/ hidratar o desfecho ao reconectar (o pub/sub nao o reentrega).
function endEvent(runId: string, status: string): ProgressEvent {
  return { run_id: runId, node: END_NODE, status, pct: 100, ts: new Date().toISOString(), extra: {} };
}

export function ConsultaConsole() {
  const [mode, setMode] = useState<RunMode>("single_company");
  const [query, setQuery] = useState("");
  const [phase, setPhase] = useState<Phase>("idle");
  const [runId, setRunId] = useState<string | null>(null);
  const [events, setEvents] = useState<ProgressEvent[]>([]);
  const [terminal, setTerminal] = useState<ProgressEvent | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [review, setReview] = useState<RunReview | null>(null);
  const [resuming, setResuming] = useState(false);
  const esRef = useRef<EventSource | null>(null);

  // Fecha o stream ao desmontar — o EventSource reconecta sozinho se nao for fechado.
  useEffect(() => () => esRef.current?.close(), []);

  // Reconexao ao montar (F5.3+): se ha um run guardado, reencontra a consulta longa em vez de
  // perde-la ao voltar a tela (o worker segue rodando, F2.10). Decide pela fase do run sem pendurar
  // no SSE: rodando -> reabre o stream; pausado/terminado -> hidrata do checkpoint (F2.2). setState
  // vive so no callback async (evita o set-state-in-effect do React 19, como na auth/F5.9), guardado
  // contra desmonte por `alive`. Roda uma vez no mount.
  useEffect(() => {
    const stored = loadActiveRun();
    if (!stored) return;
    let alive = true;
    getRunStatus(stored.runId)
      .then((info) => {
        if (!alive) return;
        if (info.phase === "unknown") {
          clearActiveRun(); // run orfao (job expirou do RQ + sem checkpoint) — descarta
          return;
        }
        setMode(stored.mode);
        setQuery(stored.query);
        setRunId(stored.runId);
        if (info.phase === "running") {
          setPhase("streaming");
          hydrateLadder(stored.runId); // historico ja concluido; o SSE anexa o que falta
          openStream(stored.runId);
        } else if (info.phase === "failed") {
          setPhase("error");
          setError("A consulta anterior falhou no servidor. Tente novamente.");
          clearActiveRun();
        } else {
          // done | awaiting_review: hidrata o desfecho do checkpoint (sem pendurar no SSE).
          const status =
            info.phase === "awaiting_review" ? PAUSED : (info.run_status ?? "completed");
          setTerminal(endEvent(stored.runId, status));
          setPhase("done");
          hydrateLadder(stored.runId);
          if (info.phase === "awaiting_review") loadReview(stored.runId);
        }
      })
      .catch(() => {
        // sem rede / API fora: nao apaga o run (pode estar so offline); fica idle ate o usuario agir.
      });
    return () => {
      alive = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps -- mount-only: reconecta a consulta uma vez
  }, []);

  const busy = phase === "starting" || phase === "streaming";

  // Busca o payload de revisao quando o run pausa no interrupt (F5.10). No callback (nao em
  // effect) — evita o `set-state-in-effect` do React 19, como na auth (F5.9).
  function loadReview(id: string) {
    getRunReview(id)
      .then((data) => setReview(data))
      .catch((err) =>
        setError(err instanceof Error ? err.message : "Erro ao carregar a revisao."),
      );
  }

  // Abre o SSE do run e liga os handlers. Reusado no inicio (start) e na retomada (resume): nao
  // reseta `events`, entao a espinha acumula os nos das duas passagens (pre-pausa + pos-resume).
  function openStream(id: string) {
    esRef.current?.close();
    const es = new EventSource(runStreamUrl(id));
    esRef.current = es;
    es.onmessage = (msg) => {
      const event = JSON.parse(msg.data) as ProgressEvent;
      if (event.node === END_NODE) {
        setTerminal(event);
        setPhase("done");
        es.close();
        // Pausou no HITL (F2.8): carrega o diagnostico p/ o painel de aprovacao (F5.10).
        if (event.status === PAUSED) loadReview(id);
        return;
      }
      setEvents((prev) => [...prev, event]);
    };
    es.onerror = () => {
      // O browser reconecta enquanto readyState != CLOSED; so e erro se ele desistiu
      // antes do evento terminal (queda de rede / API fora).
      if (es.readyState === EventSource.CLOSED) {
        es.close();
        setPhase("error");
        setError("Conexao de progresso encerrada antes do fim da consulta.");
      }
    };
  }

  // Reconstroi a escada de nos ja concluidos a partir do estado persistido (F2.2): o pub/sub de
  // progresso nao reentrega os eventos por no, entao ao reconectar buscamos o trace (F5.7) e
  // marcamos os done. Merge (nao clobber) p/ conviver com os eventos ao vivo que o SSE for
  // anexando no caso "running"; degrada limpo se o checkpoint ainda nao existir.
  function hydrateLadder(id: string) {
    getRunTrace(id)
      .then((trace) =>
        setEvents((prev) => {
          const seen = new Set(prev.map((ev) => ev.node));
          const hist: ProgressEvent[] = trace.steps
            .filter((s) => s.status === "done" && !seen.has(s.node))
            .map((s) => ({
              run_id: id,
              node: s.node,
              status: "running",
              pct: null,
              ts: new Date().toISOString(),
              extra: {},
            }));
          return [...hist, ...prev];
        }),
      )
      .catch(() => {
        // sem trace (checkpoint ainda nao escrito) — a escada fica sem historico; o desfecho aparece.
      });
  }

  async function start(e: React.FormEvent) {
    e.preventDefault();
    const q = query.trim();
    if (!q || busy) return;

    esRef.current?.close();
    setEvents([]);
    setTerminal(null);
    setError(null);
    setReview(null);
    setRunId(null);
    setPhase("starting");

    try {
      const accepted = await createRun(q, mode);
      setRunId(accepted.run_id);
      // Guarda o run em andamento p/ reencontra-lo se a tela fechar (o worker segue rodando, F2.10).
      saveActiveRun({ runId: accepted.run_id, mode, query: q });
      setPhase("streaming");
      openStream(accepted.run_id);
    } catch (err) {
      setPhase("error");
      setError(err instanceof Error ? err.message : "Erro ao iniciar a consulta.");
    }
  }

  // Retoma o run pausado com a decisao do gerente (F5.10) e reabre o stream p/ seguir ate o fim.
  async function resume(decision: ResumeDecision) {
    if (!runId || resuming) return;
    setResuming(true);
    setError(null);
    try {
      await resumeRun(runId, decision);
      setReview(null);
      setTerminal(null);
      setPhase("streaming");
      openStream(runId);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Erro ao retomar o run.");
    } finally {
      setResuming(false);
    }
  }

  const seen = new Set(events.map((ev) => ev.node));
  const pct = terminal?.pct ?? events.at(-1)?.pct ?? 0;
  // Primeiro no ainda nao visto = o que esta rodando agora (so durante o streaming).
  const activeIndex = PIPELINE_STEPS.findIndex((s) => !seen.has(s.node));
  const activeFinal = terminal?.status ?? null;
  const paused = activeFinal === PAUSED;

  return (
    <div className="flex flex-col gap-8">
      <form onSubmit={start} className="flex flex-col gap-4">
        <div className="inline-flex w-fit gap-1 rounded-lg border border-border p-1">
          {MODES.map((m) => (
            <Button
              key={m.mode}
              type="button"
              size="sm"
              variant={mode === m.mode ? "default" : "ghost"}
              onClick={() => setMode(m.mode)}
              disabled={busy}
            >
              {m.titulo}
            </Button>
          ))}
        </div>

        <div className="flex flex-col gap-2 sm:flex-row">
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder={MODES.find((m) => m.mode === mode)?.placeholder}
            disabled={busy}
            className="h-9 flex-1 rounded-lg border border-border bg-background px-3 text-sm text-foreground outline-none placeholder:text-muted-foreground focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50 disabled:opacity-50"
          />
          <Button type="submit" variant="brand" size="lg" disabled={busy || query.trim() === ""}>
            {busy ? "Consultando..." : "Consultar"}
          </Button>
        </div>
        <p className="text-xs text-muted-foreground">
          {mode === "single_company"
            ? "Diagnostica uma empresa e pausa para revisao (HITL sync, F2.8)."
            : "Descobre empresas por setor/regiao em lote, sem bloquear a fila (HITL auto)."}
        </p>
        <p className="text-xs text-muted-foreground">
          A consulta roda no servidor e continua mesmo se voce sair desta tela — ao voltar, ela e
          reencontrada automaticamente.
        </p>
      </form>

      {phase !== "idle" && (
        <section className="flex flex-col gap-4 rounded-lg border border-border bg-card p-5 text-card-foreground">
          <div className="flex items-center justify-between gap-4">
            <h2 className="text-base font-semibold">Pipeline</h2>
            {runId && (
              <span className="font-mono text-xs text-muted-foreground">run {runId}</span>
            )}
          </div>

          <div className="h-2 w-full overflow-hidden rounded-full bg-muted">
            <div
              className="h-full rounded-full bg-brand transition-all duration-300"
              style={{ width: `${pct}%` }}
            />
          </div>

          <ol className="flex flex-col gap-2">
            {PIPELINE_STEPS.map((step, i) => {
              const done = seen.has(step.node);
              const active = !done && i === activeIndex && phase === "streaming";
              return (
                <li key={step.node} className="flex items-center gap-3 text-sm">
                  <StepMarker done={done} active={active} />
                  <span
                    className={cn(
                      done
                        ? "text-foreground"
                        : active
                          ? "font-medium text-foreground"
                          : "text-muted-foreground",
                    )}
                  >
                    {step.label}
                  </span>
                </li>
              );
            })}
          </ol>

          {activeFinal && (
            <div className="rounded-md border border-border bg-background px-3 py-2 text-sm">
              <span className="font-medium">Desfecho:</span> {statusLabel(activeFinal)}
              {paused && (
                <p className="mt-1 text-xs text-muted-foreground">
                  O run pausou para revisao humana (HITL sync, F2.8) — aprove, edite ou rejeite o
                  diagnostico abaixo para retomar.
                </p>
              )}
            </div>
          )}

          {/* Painel de revisao HITL (F5.10): so na pausa do single-company; aprovar/editar/rejeitar. */}
          {paused && phase === "done" && (
            <ReviewPanel review={review} submitting={resuming} onResume={resume} error={error} />
          )}

          {/* Acoes ao concluir: trace dos agentes (F5.7) + export do briefing em PDF (F5.8). */}
          {phase === "done" && runId && (
            <div className="flex flex-wrap items-center gap-x-5 gap-y-2">
              <Link
                href={`/runs/${encodeURIComponent(runId)}/trace`}
                className="text-sm text-brand-ink hover:underline"
              >
                Ver passos do run (trace) →
              </Link>
              {/* So oferece o PDF quando o run chegou ao briefing (F5.8): completou ou caiu
                  num ramo terminal que salta ao briefing — nao em pausa HITL nem falha. */}
              {hasBriefing(activeFinal) && (
                <a
                  href={briefingUrl(runId, "pdf")}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-sm text-brand-ink hover:underline"
                >
                  Exportar briefing (PDF) ↓
                </a>
              )}
            </div>
          )}

          {phase === "error" && error && (
            <p className="text-sm text-destructive">{error}</p>
          )}
        </section>
      )}
    </div>
  );
}

// Painel de revisao humana (F5.10): mostra o diagnostico do run pausado (classe/AIMI/recs) e deixa
// o gerente aprovar, editar (classe + AIMI) ou rejeitar. A decisao vai ao `resume` e fica registrada
// em trace["human_review"] (auditavel, F2.8); aplicar as edicoes ao briefing e gancho futuro (F2.8/F4.4).
function ReviewPanel({
  review,
  submitting,
  onResume,
  error,
}: {
  review: RunReview | null;
  submitting: boolean;
  onResume: (decision: ResumeDecision) => void;
  error: string | null;
}) {
  const [editing, setEditing] = useState(false);
  const [classe, setClasse] = useState("");
  const [aimi, setAimi] = useState("");
  const [nota, setNota] = useState("");

  if (!review) {
    return <p className="text-sm text-muted-foreground">Carregando revisao...</p>;
  }
  // Race raro: o run ja seguiu/concluiu entre o evento terminal e o fetch — sem o que aprovar.
  if (!review.awaiting_review) {
    return (
      <p className="text-sm text-muted-foreground">
        Este run nao esta mais aguardando revisao (ja foi retomado).
      </p>
    );
  }

  // Liga o modo edicao pre-preenchendo com o diagnostico atual (o gerente corrige a partir dele).
  function toggleEditing() {
    if (!editing && review) {
      setClasse(review.classificacao ?? CLASSES[0]);
      setAimi(review.aimi_total != null ? String(review.aimi_total) : "");
    }
    setEditing((v) => !v);
  }

  function decide(approved: boolean) {
    const decision: ResumeDecision = { approved };
    const trimmed = nota.trim();
    if (trimmed) decision.nota = trimmed;
    if (approved && editing) {
      const aimiNum = Number(aimi);
      decision.edicoes = {
        classificacao: classe,
        ...(aimi !== "" && Number.isFinite(aimiNum) ? { aimi_total: aimiNum } : {}),
      };
    }
    onResume(decision);
  }

  return (
    <div className="flex flex-col gap-4 rounded-lg border border-brand/40 bg-background p-4">
      <div className="flex flex-col gap-1">
        <h3 className="text-sm font-semibold">Revisao humana (HITL)</h3>
        {review.empresa && (
          <p className="text-sm text-muted-foreground">{review.empresa}</p>
        )}
      </div>

      {/* Diagnostico que o gerente confere: classe (§5.1) + AIMI (0-100) + techs recomendadas. */}
      <dl className="flex flex-col gap-2 text-sm">
        <div className="flex items-center gap-2">
          <dt className="w-28 shrink-0 text-muted-foreground">Classe</dt>
          {editing ? (
            <select
              value={classe}
              onChange={(e) => setClasse(e.target.value)}
              disabled={submitting}
              className="h-8 rounded-md border border-border bg-background px-2 text-sm outline-none focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50"
            >
              {CLASSES.map((c) => (
                <option key={c} value={c}>
                  {c}
                </option>
              ))}
            </select>
          ) : (
            <dd>{review.classificacao ?? "—"}</dd>
          )}
        </div>
        <div className="flex items-center gap-2">
          <dt className="w-28 shrink-0 text-muted-foreground">AIMI</dt>
          {editing ? (
            <input
              type="number"
              min={0}
              max={100}
              value={aimi}
              onChange={(e) => setAimi(e.target.value)}
              disabled={submitting}
              className="h-8 w-24 rounded-md border border-border bg-background px-2 text-sm outline-none focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50"
            />
          ) : (
            <dd>{review.aimi_total != null ? `${review.aimi_total}/100` : "—"}</dd>
          )}
        </div>
        <div className="flex gap-2">
          <dt className="w-28 shrink-0 text-muted-foreground">Recomendacoes</dt>
          <dd className="flex-1">
            {review.recomendacoes.length > 0 ? review.recomendacoes.join(", ") : "—"}
          </dd>
        </div>
      </dl>

      <label className="flex flex-col gap-1 text-sm">
        <span className="text-muted-foreground">Nota (opcional — justifica a decisao)</span>
        <textarea
          value={nota}
          onChange={(e) => setNota(e.target.value)}
          disabled={submitting}
          rows={2}
          className="rounded-md border border-border bg-background px-2 py-1.5 text-sm outline-none focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50"
        />
      </label>

      {error && <p className="text-sm text-destructive">{error}</p>}

      <div className="flex flex-wrap items-center gap-2">
        <Button type="button" variant="brand" onClick={() => decide(true)} disabled={submitting}>
          {submitting ? "Retomando..." : editing ? "Salvar e aprovar" : "Aprovar e retomar"}
        </Button>
        <Button
          type="button"
          variant="outline"
          onClick={toggleEditing}
          disabled={submitting}
        >
          {editing ? "Cancelar edicao" : "Editar diagnostico"}
        </Button>
        <Button
          type="button"
          variant="destructive"
          onClick={() => decide(false)}
          disabled={submitting}
        >
          Rejeitar
        </Button>
      </div>
    </div>
  );
}

// Marcador de etapa: check (concluida), spinner (em execucao) ou anel vazio (pendente).
function StepMarker({ done, active }: { done: boolean; active: boolean }) {
  if (done) {
    return (
      <span className="flex size-4 items-center justify-center rounded-full bg-primary text-[10px] font-bold text-primary-foreground">
        ✓
      </span>
    );
  }
  if (active) {
    return (
      <span className="size-4 animate-spin rounded-full border-2 border-muted border-t-foreground" />
    );
  }
  return <span className="size-4 rounded-full border-2 border-muted" />;
}
