import { useEffect, useRef, useState } from "react";
import { labelClass, PipelineResult, StageInfo, streamPipeline } from "../api";

// Página Pipeline (ux.md §6.5): o gestor digita uma consulta, dispara o
// pipeline multi-agente no backend (POST /api/pipeline/stream) e acompanha, em
// tempo real, o stepper de estágios — depois vê as startups qualificadas com os
// produtos NVIDIA recomendados e a aderência.

type StageStatus = "pending" | "running" | "done";
interface StepState extends StageInfo {
  status: StageStatus;
  message: string | null;
}

// mm:ss a partir de segundos.
function fmtTempo(seg: number): string {
  const m = Math.floor(seg / 60);
  const s = seg % 60;
  return `${m}:${s.toString().padStart(2, "0")}`;
}

// As mensagens dos nós vêm como "[nó] detalhe…"; no stepper o nó já é o rótulo,
// então tiramos o prefixo redundante e mostramos só o detalhe.
function limparMsg(msg: string): string {
  return msg.replace(/^\[[^\]]+]\s*/, "");
}

export default function Pipeline() {
  const [query, setQuery] = useState("startups de IA jurídica no Brasil");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<PipelineResult | null>(null);
  const [steps, setSteps] = useState<StepState[]>([]);
  const [elapsed, setElapsed] = useState(0);
  const startRef = useRef<number>(0);

  // Cronômetro: roda enquanto `loading`, mostrando o tempo decorrido.
  useEffect(() => {
    if (!loading) return;
    const id = setInterval(
      () => setElapsed(Math.floor((Date.now() - startRef.current) / 1000)),
      1000,
    );
    return () => clearInterval(id);
  }, [loading]);

  async function run() {
    setLoading(true);
    setError(null);
    setResult(null);
    setSteps([]);
    setElapsed(0);
    startRef.current = Date.now();
    try {
      await streamPipeline(query, (ev) => {
        if (ev.type === "start") {
          // Desenha todos os estágios; o primeiro já entra como "rodando".
          setSteps(
            ev.stages.map((s, i) => ({
              ...s,
              status: i === 0 ? "running" : "pending",
              message: null,
            })),
          );
        } else if (ev.type === "node") {
          // O nó `ev.node` ACABOU de rodar: marca concluído (com sua mensagem)
          // e promove o próximo estágio pendente para "rodando".
          setSteps((prev) => {
            const next = prev.map((s) =>
              s.node === ev.node
                ? { ...s, status: "done" as StageStatus, message: ev.message }
                : s,
            );
            const i = next.findIndex((s) => s.node === ev.node);
            if (i >= 0 && i + 1 < next.length && next[i + 1].status === "pending") {
              next[i + 1] = { ...next[i + 1], status: "running" };
            }
            return next;
          });
        } else if (ev.type === "done") {
          setSteps((prev) => prev.map((s) => ({ ...s, status: "done" })));
          setResult(ev.result);
        } else if (ev.type === "error") {
          setError(ev.error);
        }
      });
    } catch (e) {
      setError(e instanceof Error ? e.message : "falha ao executar o pipeline");
    } finally {
      setLoading(false);
    }
  }

  // Junta o retrato classificado à recomendação, por nome.
  const porNome = new Map(result?.classified_startups.map((c) => [c.startup.name, c]));

  return (
    <div className="page">
      <div className="pipeline-form">
        <input
          className="pipeline-input"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && !loading && run()}
          placeholder="Descreva as startups que você procura…"
        />
        <button className="btn-primary" onClick={run} disabled={loading}>
          {loading ? "Executando…" : "Executar pipeline"}
        </button>
      </div>

      <p className="hint">
        Executa os 11 agentes de verdade (busca → coleta → classificação → RAG
        NVIDIA → recomendação → briefing). Pode levar alguns segundos e depende
        das fontes públicas no ar.
      </p>

      {steps.length > 0 && (
        <div className="stepper">
          <div className="step-head">
            <span className="section-lbl">
              {loading ? "Executando pipeline…" : "Pipeline concluído"}
            </span>
            <span className="step-elapsed">{fmtTempo(elapsed)}</span>
          </div>
          {steps.map((s) => (
            <div className={`step ${s.status}`} key={s.node}>
              <span className={`step-ico ${s.status}`}>
                {s.status === "done" ? (
                  "✓"
                ) : s.status === "running" ? (
                  <span className="spinner" />
                ) : (
                  "○"
                )}
              </span>
              <span className="step-lbl">{s.label}</span>
              {s.message && <span className="step-msg">{limparMsg(s.message)}</span>}
            </div>
          ))}
        </div>
      )}

      {error && <div className="alert">Erro: {error}</div>}

      {result && result.recommendations.length === 0 && (
        <div className="placeholder">
          Nenhuma startup qualificada para “{result.query}”. Veja o trace abaixo
          para entender o que cada agente fez.
        </div>
      )}

      {result?.recommendations.map((rec) => {
        const c = porNome.get(rec.name);
        return (
          <div className="card" key={rec.name}>
            <div className="card-head">
              <h2>{rec.name}</h2>
              <span className={`badge ${labelClass(rec.label)}`}>{rec.label}</span>
            </div>

            {c && (
              <div className="meta">
                {c.startup.sector ?? "—"} · {c.startup.stage ?? "—"} ·{" "}
                {c.startup.funding ?? "—"}
              </div>
            )}
            {c?.startup.description && <p className="desc">{c.startup.description}</p>}
            {c?.rationale && <p className="rationale">{c.rationale}</p>}

            <div className="section-lbl">Produtos NVIDIA recomendados</div>

            {rec.technologies.length === 0 && (
              <div className="muted">Nenhuma tecnologia aderente ao perfil.</div>
            )}
            {rec.technologies.map((t) => (
              <div className="tech" key={t.tech}>
                <div className="tech-head">
                  <a href={t.url} target="_blank" rel="noreferrer" className="tech-name">
                    {t.tech}
                  </a>
                </div>
                <div className="tech-summary">{t.summary}</div>
                <div className="tech-growth">↗ {t.growth}</div>
                {t.matched_signals.length > 0 && (
                  <div className="tech-signals">
                    {t.matched_signals.map((s) => (
                      <span className="chip" key={s}>
                        {s}
                      </span>
                    ))}
                  </div>
                )}
                {t.snippet && <div className="snippet">{t.snippet}</div>}
              </div>
            ))}

            {rec.notes.map((n) => (
              <div className="note" key={n}>
                ⚠ {n}
              </div>
            ))}
          </div>
        );
      })}

      {result && (
        <details className="trace">
          <summary>Trace do grafo ({result.trace.length} passos)</summary>
          {result.trace.map((m, i) => (
            <div className="trace-line" key={i}>
              {m}
            </div>
          ))}
        </details>
      )}
    </div>
  );
}
