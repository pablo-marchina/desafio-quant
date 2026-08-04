import { useEffect, useState } from "react";
import { Analytics as AnalyticsData, getAnalytics, labelClass } from "../api";

// Página Analytics (ux.md §6.5): visão AGREGADA do ecossistema, lida do banco.
// Só existe porque os resultados do pipeline são persistidos — é a prova de que
// os dados acumulam e ganham valor entre execuções.

// Barras horizontais proporcionais ao maior valor da série.
function BarList({
  data,
  max,
  colorOf,
}: {
  data: { label: string; count: number }[];
  max: number;
  colorOf?: (label: string) => string;
}) {
  return (
    <div className="an-bars">
      {data.map((d) => (
        <div className="an-row" key={d.label}>
          <span className="an-lbl">{d.label}</span>
          <div className="an-track">
            <div
              className={`an-fill ${colorOf ? colorOf(d.label) : ""}`}
              style={{ width: `${max ? (d.count / max) * 100 : 0}%` }}
            />
          </div>
          <span className="an-val">{d.count}</span>
        </div>
      ))}
    </div>
  );
}

// classe de cor de fundo (a partir das badges) -> usada nas barras
function fillClass(badge: string): string {
  return badge.replace("badge-", "fill-");
}

export default function Analytics() {
  const [data, setData] = useState<AnalyticsData | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function load() {
    setLoading(true);
    setError(null);
    try {
      setData(await getAnalytics());
    } catch (e) {
      setError(e instanceof Error ? e.message : "falha ao carregar");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
  }, []);

  const maxClass = Math.max(1, ...(data?.by_classification.map((d) => d.count) ?? [1]));
  const maxSector = Math.max(1, ...(data?.by_sector.map((d) => d.count) ?? [1]));
  const maxTech = Math.max(1, ...(data?.by_nvidia_tech.map((d) => d.count) ?? [1]));

  // KPIs derivados da distribuição de maturidade (dados que já temos).
  const porLabel = Object.fromEntries(
    (data?.by_classification ?? []).map((d) => [d.classification, d.count]),
  );
  const aiNative = porLabel["AI-native"] ?? 0;
  const usamIA = (porLabel["AI-native"] ?? 0) + (porLabel["AI-enabled"] ?? 0);
  const pctIA = data && data.total ? Math.round((usamIA / data.total) * 100) : 0;

  return (
    <div className="page">
      <div className="qual-head">
        <p className="hint">Visão agregada das startups já qualificadas e persistidas.</p>
        <button className="btn-primary" onClick={load} disabled={loading}>
          {loading ? "Atualizando…" : "Atualizar"}
        </button>
      </div>

      {error && <div className="alert">Erro: {error}</div>}

      {data && data.total === 0 && (
        <div className="placeholder">
          Nenhum dado ainda. Rode o pipeline para popular as métricas.
        </div>
      )}

      {data && data.total > 0 && (
        <>
          <div className="kpis">
            <div className="kpi">
              <div className="kpi-num">{data.total}</div>
              <div className="kpi-lbl">startups qualificadas</div>
            </div>
            <div className="kpi">
              <div className="kpi-num">{aiNative}</div>
              <div className="kpi-lbl">AI-native</div>
            </div>
            <div className="kpi">
              <div className="kpi-num">{pctIA}%</div>
              <div className="kpi-lbl">usam IA (native + enabled)</div>
            </div>
            <div className="kpi">
              <div className="kpi-num">{data.with_reco}</div>
              <div className="kpi-lbl">com stack NVIDIA</div>
            </div>
          </div>

          <div className="an-card">
            <div className="section-lbl">Maturidade de IA</div>
            <BarList
              data={data.by_classification.map((d) => ({
                label: d.classification,
                count: d.count,
              }))}
              max={maxClass}
              colorOf={(l) => fillClass(labelClass(l))}
            />
          </div>

          <div className="an-card">
            <div className="section-lbl">Top setores</div>
            <BarList
              data={data.by_sector.map((d) => ({ label: d.sector, count: d.count }))}
              max={maxSector}
            />
          </div>

          <div className="an-card">
            <div className="section-lbl">Produtos NVIDIA mais recomendados</div>
            {data.by_nvidia_tech.length === 0 ? (
              <div className="muted">Nenhuma recomendação registrada ainda.</div>
            ) : (
              <BarList
                data={data.by_nvidia_tech.map((d) => ({ label: d.tech, count: d.count }))}
                max={maxTech}
                colorOf={() => "fill-green"}
              />
            )}
          </div>
        </>
      )}
    </div>
  );
}
