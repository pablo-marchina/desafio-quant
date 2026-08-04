import { Fragment, useEffect, useState } from "react";
import {
  getStartup,
  labelClass,
  listStartups,
  StartupDetail,
  StartupRow,
} from "../api";

// Página Qualificadas (ux.md §6.5): o FUNIL acumulado. Diferente da Pipeline
// (que roda os agentes), aqui só LEMOS as startups já qualificadas e salvas no
// banco. Cada linha EXPANDE num dropdown com: sobre a empresa, os produtos
// NVIDIA recomendados e o briefing executivo — carregado sob demanda.

// Renderiza **negrito** dentro de um parágrafo (sem lib de markdown).
function renderInline(texto: string) {
  return texto.split(/(\*\*[^*]+\*\*)/g).map((parte, i) =>
    parte.startsWith("**") && parte.endsWith("**") ? (
      <strong key={i}>{parte.slice(2, -2)}</strong>
    ) : (
      <span key={i}>{parte}</span>
    ),
  );
}

// Briefing curto formatado: parágrafos + negrito. Tolera markdown antigo
// (linhas com #) removendo os hashes de cabeçalho.
function BriefingText({ text }: { text: string }) {
  const paragrafos = text
    .split(/\n\n+/)
    .map((p) => p.replace(/^#+\s*/gm, "").trim())
    .filter(Boolean);
  return (
    <div className="briefing">
      {paragrafos.map((p, i) => (
        <p key={i}>{renderInline(p)}</p>
      ))}
    </div>
  );
}

// Painel do dropdown: sobre + produtos recomendados + briefing.
function DetailPanel({
  detail,
  loading,
  error,
}: {
  detail: StartupDetail | undefined;
  loading: boolean;
  error: string | undefined;
}) {
  if (loading) return <div className="qual-detail muted">Carregando detalhe…</div>;
  if (error) return <div className="qual-detail alert">Erro: {error}</div>;
  if (!detail) return null;

  const techs = detail.recommendations?.technologies ?? [];
  return (
    <div className="qual-detail">
      <div className="section-lbl">Sobre a empresa</div>
      <p className="desc">{detail.description ?? "Sem descrição registrada."}</p>

      <div className="section-lbl">Produtos NVIDIA recomendados</div>
      {techs.length === 0 && (
        <div className="muted">Nenhum produto NVIDIA aderente a este perfil.</div>
      )}
      {techs.map((t) => (
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
        </div>
      ))}
      {detail.recommendations?.notes?.map((n) => (
        <div className="note" key={n}>
          ⚠ {n}
        </div>
      ))}

      <div className="section-lbl">Briefing de recomendação NVIDIA</div>
      {detail.briefing ? (
        <BriefingText text={detail.briefing} />
      ) : (
        <div className="muted">Briefing não disponível para esta startup.</div>
      )}
    </div>
  );
}

export default function Qualificadas() {
  const [rows, setRows] = useState<StartupRow[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  // Estado do dropdown: qual linha está aberta + cache/loading/erro por nome.
  const [expanded, setExpanded] = useState<string | null>(null);
  const [details, setDetails] = useState<Record<string, StartupDetail>>({});
  const [detailLoading, setDetailLoading] = useState<string | null>(null);
  const [detailError, setDetailError] = useState<Record<string, string>>({});

  async function load() {
    setLoading(true);
    setError(null);
    try {
      setRows(await listStartups());
    } catch (e) {
      setError(e instanceof Error ? e.message : "falha ao carregar");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
  }, []);

  async function toggle(name: string) {
    // Fecha se já estava aberta.
    if (expanded === name) {
      setExpanded(null);
      return;
    }
    setExpanded(name);
    // Busca o detalhe só na primeira vez (cache simples por nome).
    if (details[name] || detailLoading === name) return;
    setDetailLoading(name);
    setDetailError((e) => ({ ...e, [name]: "" }));
    try {
      const d = await getStartup(name);
      setDetails((m) => ({ ...m, [name]: d }));
    } catch (e) {
      setDetailError((er) => ({
        ...er,
        [name]: e instanceof Error ? e.message : "falha ao carregar detalhe",
      }));
    } finally {
      setDetailLoading(null);
    }
  }

  return (
    <div className="page">
      <div className="qual-head">
        <p className="hint">
          Startups já qualificadas e persistidas (acumuladas entre execuções do
          pipeline), das mais recentes para as mais antigas. Clique numa linha
          para ver o detalhe.
        </p>
        <button className="btn-primary" onClick={load} disabled={loading}>
          {loading ? "Atualizando…" : "Atualizar"}
        </button>
      </div>

      {error && <div className="alert">Erro: {error}</div>}

      {rows && rows.length === 0 && (
        <div className="placeholder">
          Nenhuma startup persistida ainda. Rode o pipeline na aba Pipeline para
          popular o funil.
        </div>
      )}

      {rows && rows.length > 0 && (
        <table className="qual-table">
          <thead>
            <tr>
              <th>Startup</th>
              <th>Setor</th>
              <th>Estágio</th>
              <th>Classificação</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((s) => {
              const aberta = expanded === s.name;
              return (
                <Fragment key={s.name}>
                  <tr
                    className={`qual-row ${aberta ? "open" : ""}`}
                    onClick={() => toggle(s.name)}
                  >
                    <td className="strong">
                      <span className="caret">{aberta ? "▾" : "▸"}</span> {s.name}
                    </td>
                    <td>{s.sector ?? "—"}</td>
                    <td>{s.stage ?? "—"}</td>
                    <td>
                      <span className={`badge ${labelClass(s.classification)}`}>
                        {s.classification}
                      </span>
                    </td>
                  </tr>
                  {aberta && (
                    <tr className="qual-detail-row">
                      <td colSpan={4}>
                        <DetailPanel
                          detail={details[s.name]}
                          loading={detailLoading === s.name}
                          error={detailError[s.name] || undefined}
                        />
                      </td>
                    </tr>
                  )}
                </Fragment>
              );
            })}
          </tbody>
        </table>
      )}
    </div>
  );
}
