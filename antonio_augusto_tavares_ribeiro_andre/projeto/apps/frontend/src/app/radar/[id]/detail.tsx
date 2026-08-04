"use client";

// Detalhe da startup (F5.5): radar AIMI dos 4 pilares + evidencias com link a fonte. Consome o
// `GET /companies/{id}` (F5.2) — perfil + breakdown do AIMI (sub-scores, faixas, justificativas e
// fontes citaveis por pilar). Degrada gracioso: empresa sem score chega sem `pilares`, e pilar
// sem evidencia persistida (a persistencia do AIMI ainda nao grava) mostra o sub-score sem link.

import { useEffect, useState } from "react";

import Link from "next/link";

import { cn } from "@/lib/utils";
import {
  getCompany,
  type CompanyDetail,
  type EvidenceOut,
  type PillarOut,
  type RecommendationOut,
  type ROIOut,
} from "@/lib/api";

// Rotulos PT-BR dos pilares (RUBRICA/F0.11) — espelham o texto do briefing (packages/agents/
// briefing.py). A chave tecnica (`AIMIPillar`) vem da API; o rotulo e da camada de apresentacao.
const PILLAR_LABELS: Record<string, string> = {
  data_moat: "Data Moat (dado proprietario)",
  workflow_depth: "Workflow Depth (profundidade de automacao)",
  technical_optimization: "Technical Optimization (inferencia propria)",
  distribution_moat: "Distribution & Moat (distribuicao/defensabilidade)",
};

// Rotulo curto para os eixos do radar (espaco apertado).
const PILLAR_SHORT: Record<string, string> = {
  data_moat: "Data Moat",
  workflow_depth: "Workflow",
  technical_optimization: "Tech Opt.",
  distribution_moat: "Distribution",
};

// Rotulos PT-BR de prioridade/complexidade (§5.5) — os valores vem em PT-BR sem acento da API
// (Priority/Complexity, enums.py); aqui so acentuamos para a apresentacao.
const PRIORITY_LABELS: Record<string, string> = { alta: "Alta", media: "Media", baixa: "Baixa" };
const COMPLEXITY_LABELS: Record<string, string> = { alta: "Alta", media: "Media", baixa: "Baixa" };

type Phase = "loading" | "ready" | "error";

export function CompanyDetailView({ id }: { id: number }) {
  const [company, setCompany] = useState<CompanyDetail | null>(null);
  const [phase, setPhase] = useState<Phase>("loading");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let alive = true;
    getCompany(id)
      .then((data) => {
        if (!alive) return;
        setCompany(data);
        setPhase("ready");
      })
      .catch((err) => {
        if (!alive) return;
        setError(err instanceof Error ? err.message : "Erro ao carregar a startup.");
        setPhase("error");
      });
    return () => {
      alive = false;
    };
  }, [id]);

  return (
    <main className="flex flex-1 flex-col items-center bg-background text-foreground">
      <div className="w-full max-w-4xl px-6 py-16 sm:py-24">
        <header className="flex flex-col gap-3">
          <Link
            href="/radar"
            className="w-fit text-sm text-muted-foreground hover:text-foreground"
          >
            ← Radar de startups
          </Link>
          <h1 className="text-3xl font-semibold tracking-tight sm:text-4xl">
            {company?.nome ?? "Detalhe da startup"}
          </h1>
          {phase === "ready" && company && <SubHeader company={company} />}
        </header>

        <div className="mt-10">
          {phase === "loading" && <Card>Carregando...</Card>}
          {phase === "error" && error && <Card tone="error">{error}</Card>}
          {phase === "ready" && company && <Body company={company} />}
        </div>
      </div>
    </main>
  );
}

// Linha de identidade abaixo do titulo: classe + setor + site.
function SubHeader({ company }: { company: CompanyDetail }) {
  return (
    <div className="flex flex-wrap items-center gap-3 text-sm text-muted-foreground">
      {company.classificacao && <ClasseBadge classe={company.classificacao} />}
      <span>{company.setor ?? "Setor nao informado"}</span>
      {company.website && (
        <a
          href={company.website}
          target="_blank"
          rel="noopener noreferrer"
          className="text-brand-ink hover:underline"
        >
          {company.website.replace(/^https?:\/\//, "")}
        </a>
      )}
    </div>
  );
}

function Body({ company }: { company: CompanyDetail }) {
  const pontuada = company.pilares.length > 0;

  return (
    <div className="flex flex-col gap-10">
      {company.descricao && (
        <p className="text-sm leading-relaxed text-muted-foreground">{company.descricao}</p>
      )}

      <div className="flex flex-wrap gap-3">
        <Metric label="AIMI total" value={company.aimi_total} suffix="/100" highlight />
        <Metric label="Inception Priority" value={company.inception_priority} highlight />
        <Metric label="Classe" text={company.classificacao} />
      </div>

      {!pontuada && (
        <Card>
          Esta startup ainda nao foi pontuada (sem diagnostico AIMI). Rode uma consulta para
          gerar o radar dos 4 pilares.
        </Card>
      )}

      {pontuada && (
        <section className="flex flex-col gap-6">
          <h2 className="text-lg font-semibold">Diagnostico AIMI</h2>
          <div className="grid gap-8 lg:grid-cols-[auto_1fr] lg:items-start">
            <AimiRadar pilares={company.pilares} />
            <ul className="flex flex-col gap-3">
              {company.pilares.map((p) => (
                <PillarRow key={p.pilar} pilar={p} />
              ))}
            </ul>
          </div>
        </section>
      )}

      {company.recomendacoes.length > 0 && (
        <section className="flex flex-col gap-4">
          <h2 className="text-lg font-semibold">Recomendacoes NVIDIA</h2>
          <p className="text-xs text-muted-foreground">
            Cada recomendacao traz evidencia dos dois lados (gap da startup + base NVIDIA) e, quando
            ha gap de inferencia, o ROI de migrar API → stack otimizada (GPU Graduation Engine).
          </p>
          <ul className="flex flex-col gap-4">
            {company.recomendacoes.map((rec) => (
              <RecommendationCard key={rec.tech} rec={rec} />
            ))}
          </ul>
        </section>
      )}
    </div>
  );
}

// Cartao de uma recomendacao (§5.5/F5.6): tech + prioridade/complexidade + pilar de origem +
// justificativas + proxima acao + ROI (opcional, degrada gracioso) + evidencia dos dois lados.
function RecommendationCard({ rec }: { rec: RecommendationOut }) {
  return (
    <li className="rounded-lg border border-border bg-card p-5 text-card-foreground">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h3 className="text-base font-semibold text-brand-ink">{rec.tech}</h3>
        <div className="flex flex-wrap items-center gap-2">
          <PriorityBadge prioridade={rec.prioridade} />
          <span className="text-xs text-muted-foreground">
            Complexidade {COMPLEXITY_LABELS[rec.complexidade] ?? rec.complexidade}
          </span>
        </div>
      </div>

      {rec.pilar_origem && (
        <p className="mt-1 text-xs text-muted-foreground">
          Fecha o gap em {PILLAR_LABELS[rec.pilar_origem] ?? rec.pilar_origem}
        </p>
      )}

      {rec.roi && <RoiStrip roi={rec.roi} />}

      <dl className="mt-3 flex flex-col gap-2 text-sm">
        <Field label="Justificativa tecnica">{rec.justificativa_tecnica}</Field>
        <Field label="Justificativa de negocio">{rec.justificativa_negocio}</Field>
        <Field label="Proxima acao">{rec.proxima_acao}</Field>
      </dl>

      <div className="mt-3 grid gap-3 sm:grid-cols-2">
        <EvidenceColumn label="Evidencia — gap da startup" itens={rec.evidencia_gap} />
        <EvidenceColumn label="Evidencia — base NVIDIA" itens={rec.evidencia_nvidia} />
      </div>
    </li>
  );
}

// Faixa de ROI (F6): so os numeros que existem (throughput / custo / p95), baseline→otimizado e a
// origem do dado (matriz ou medido ao vivo na GPU). Ausente quando nao ha ROI (cartao degrada).
function RoiStrip({ roi }: { roi: ROIOut }) {
  const numeros: { label: string; value: string }[] = [];
  if (roi.throughput_speedup != null) {
    numeros.push({ label: "Throughput", value: `${roi.throughput_speedup}x` });
  }
  if (roi.cost_delta_pct != null) {
    numeros.push({ label: "Custo", value: deltaPct(roi.cost_delta_pct) });
  }
  if (roi.latency_p95_delta_pct != null) {
    numeros.push({ label: "p95", value: deltaPct(roi.latency_p95_delta_pct) });
  }
  const migracao = roi.baseline && roi.optimized ? `${roi.baseline} → ${roi.optimized}` : null;

  return (
    <div className="mt-3 rounded-md border border-brand/40 bg-brand/5 p-3">
      <div className="flex flex-wrap items-center gap-2">
        <span className="text-xs font-medium text-brand-ink">ROI</span>
        <span className="rounded-full border border-brand/40 px-2 py-0.5 text-[10px] text-brand-ink">
          {roi.is_live_run ? "medido ao vivo na GPU" : "matriz de benchmark"}
        </span>
      </div>
      {numeros.length > 0 && (
        <div className="mt-2 flex flex-wrap gap-4">
          {numeros.map((n) => (
            <div key={n.label} className="flex flex-col">
              <span className="text-xs text-muted-foreground">{n.label}</span>
              <span className="font-mono text-sm font-semibold text-brand-ink">{n.value}</span>
            </div>
          ))}
        </div>
      )}
      {migracao && <p className="mt-2 text-xs text-muted-foreground">{migracao}</p>}
      {roi.benchmark_source && (
        <p className="mt-1 text-[10px] text-muted-foreground">Fonte: {roi.benchmark_source}</p>
      )}
    </div>
  );
}

// Delta percentual com sinal explicito; negativo = melhora (menos custo/latencia).
function deltaPct(pct: number): string {
  const signal = pct > 0 ? "+" : "";
  return `${signal}${pct}%`;
}

// Coluna de evidencia de um lado (gap/NVIDIA) com link a fonte; "sem fonte" quando vazia.
function EvidenceColumn({ label, itens }: { label: string; itens: EvidenceOut[] }) {
  return (
    <div className="rounded-md border border-border bg-background/40 p-3">
      <p className="text-xs font-medium text-muted-foreground">{label}</p>
      {itens.length === 0 ? (
        <p className="mt-1 text-xs text-muted-foreground">Sem fonte registrada ainda.</p>
      ) : (
        <ul className="mt-1 flex flex-col gap-1">
          {itens.map((ev, i) => (
            <li key={`${ev.url}-${i}`} className="text-xs">
              <a
                href={ev.url}
                target="_blank"
                rel="noopener noreferrer"
                className="text-brand-ink hover:underline"
              >
                {ev.source_title ?? ev.url}
              </a>
              {ev.snippet && <span className="text-muted-foreground"> — {ev.snippet}</span>}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

// Campo rotulado de um cartao (justificativa / proxima acao).
function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <dt className="text-xs font-medium text-muted-foreground">{label}</dt>
      <dd className="mt-0.5 leading-relaxed text-foreground">{children}</dd>
    </div>
  );
}

// Badge de prioridade: alta em destaque (cor primaria), demais neutras.
function PriorityBadge({ prioridade }: { prioridade: string }) {
  return (
    <span
      className={cn(
        "rounded-full border px-2 py-0.5 text-xs font-medium",
        prioridade === "alta"
          ? "border-brand/40 text-brand-ink"
          : "border-border text-muted-foreground",
      )}
    >
      Prioridade {PRIORITY_LABELS[prioridade] ?? prioridade}
    </span>
  );
}

// Radar dos 4 pilares (0-25 por eixo). SVG deterministico, sem dependencia de chart: os pilares
// vem na ordem canonica da API (Data Moat, Workflow, Tech Opt., Distribution) e mapeiam para os
// eixos topo/direita/baixo/esquerda. Cor via `currentColor` + classes de tema (oklch do globals).
function AimiRadar({ pilares }: { pilares: PillarOut[] }) {
  const SIZE = 240;
  const C = SIZE / 2;
  const R = 88;
  const MAX = 25;
  const ANGLES = [-90, 0, 90, 180]; // topo, direita, baixo, esquerda

  const point = (value: number, angleDeg: number): [number, number] => {
    const a = (angleDeg * Math.PI) / 180;
    const r = (Math.max(0, Math.min(MAX, value)) / MAX) * R;
    return [C + r * Math.cos(a), C + r * Math.sin(a)];
  };
  const ring = (t: number) =>
    ANGLES.map((ang) => point(MAX * t, ang).join(",")).join(" ");
  const dataPoly = pilares
    .map((p, i) => point(p.score, ANGLES[i] ?? 0).join(","))
    .join(" ");

  // Posicao do rotulo por eixo (topo/direita/baixo/esquerda).
  const labels = [
    { x: C, y: C - R - 12, anchor: "middle" as const },
    { x: C + R + 12, y: C + 4, anchor: "start" as const },
    { x: C, y: C + R + 20, anchor: "middle" as const },
    { x: C - R - 12, y: C + 4, anchor: "end" as const },
  ];

  return (
    <svg
      viewBox={`0 0 ${SIZE} ${SIZE}`}
      className="h-60 w-60 shrink-0"
      role="img"
      aria-label="Radar dos 4 pilares do AIMI"
    >
      <g className="text-border" stroke="currentColor" fill="none">
        {[0.25, 0.5, 0.75, 1].map((t) => (
          <polygon key={t} points={ring(t)} strokeOpacity={0.4} />
        ))}
        {ANGLES.map((ang) => {
          const [x, y] = point(MAX, ang);
          return <line key={ang} x1={C} y1={C} x2={x} y2={y} strokeOpacity={0.4} />;
        })}
      </g>

      <polygon
        points={dataPoly}
        className="text-brand"
        fill="currentColor"
        fillOpacity={0.18}
        stroke="currentColor"
        strokeWidth={2}
      />
      {pilares.map((p, i) => {
        const [x, y] = point(p.score, ANGLES[i] ?? 0);
        return <circle key={p.pilar} cx={x} cy={y} r={3} className="fill-brand" />;
      })}

      <g className="fill-muted-foreground text-[10px]">
        {pilares.map((p, i) => {
          const l = labels[i];
          return (
            <text key={p.pilar} x={l.x} y={l.y} textAnchor={l.anchor}>
              {PILLAR_SHORT[p.pilar] ?? p.pilar}
            </text>
          );
        })}
      </g>
    </svg>
  );
}

// Uma linha de pilar: rotulo + sub-score/faixa + justificativa + evidencias com link a fonte.
function PillarRow({ pilar }: { pilar: PillarOut }) {
  return (
    <li className="rounded-lg border border-border bg-card p-4 text-card-foreground">
      <div className="flex items-baseline justify-between gap-3">
        <h3 className="text-sm font-semibold">{PILLAR_LABELS[pilar.pilar] ?? pilar.pilar}</h3>
        <span className="shrink-0 font-mono text-sm">
          {pilar.score}<span className="text-muted-foreground">/25</span>
          <span className="ml-2 text-xs text-muted-foreground">{pilar.band}</span>
        </span>
      </div>
      {/* Barra do sub-score (0-25) para leitura rapida ao lado do radar. */}
      <div className="mt-2 h-1.5 w-full overflow-hidden rounded-full bg-muted">
        <div
          className="h-full rounded-full bg-brand"
          style={{ width: `${(pilar.score / 25) * 100}%` }}
        />
      </div>
      {pilar.justificativa && (
        <p className="mt-2 text-sm text-muted-foreground">{pilar.justificativa}</p>
      )}
      {pilar.evidencias.length > 0 && (
        <ul className="mt-2 flex flex-col gap-1">
          {pilar.evidencias.map((ev, i) => (
            <li key={`${ev.url}-${i}`} className="text-xs">
              <a
                href={ev.url}
                target="_blank"
                rel="noopener noreferrer"
                className="text-brand-ink hover:underline"
              >
                {ev.source_title ?? ev.url}
              </a>
              {ev.snippet && (
                <span className="text-muted-foreground"> — {ev.snippet}</span>
              )}
            </li>
          ))}
        </ul>
      )}
    </li>
  );
}

function ClasseBadge({ classe }: { classe: string }) {
  return (
    <span
      className={cn(
        "rounded-full border px-2 py-0.5 text-xs font-medium",
        classe === "AI-native"
          ? "border-brand/40 text-brand-ink"
          : "border-border text-muted-foreground",
      )}
    >
      {classe}
    </span>
  );
}

// Metrica do cabecalho (numero ou texto); "—" quando ausente (empresa nao pontuada).
function Metric({
  label,
  value,
  text,
  suffix = "",
  highlight = false,
}: {
  label: string;
  value?: number | null;
  text?: string | null;
  suffix?: string;
  highlight?: boolean;
}) {
  const display = text ?? (value != null ? `${value}${suffix}` : "—");
  return (
    <div className="flex min-w-28 flex-col gap-1 rounded-lg border border-border bg-card p-4">
      <span className="text-xs text-muted-foreground">{label}</span>
      <span className={cn("font-mono text-lg", highlight && "font-semibold text-brand-ink")}>
        {display}
      </span>
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
