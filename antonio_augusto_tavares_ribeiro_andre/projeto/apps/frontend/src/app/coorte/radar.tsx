"use client";

// Radar de coorte (F6.5–F6.7): consome o `GET /cohort/clusters` (F5.2) e desenha o ecossistema
// agrupado por perfil. Scatter 2D em SVG puro (sem lib de chart): cada ponto e uma startup nas
// coords da projecao (PCA/UMAP no backend), colorida por cluster; alvos de graduacao ★ ganham anel.
// Abaixo, os clusters ja vem ordenados por prontidao de graduacao (share ★ + Inception medio) — a
// leitura de portfolio do gerente. Determinismo/proveniencia (numpy/cuml, hashing/nv) no rodape.

import { useEffect, useState } from "react";

import Link from "next/link";

import { cn } from "@/lib/utils";
import { getCohortClusters, type CohortClustering, type CohortClusterMember } from "@/lib/api";

// Paleta de clusters (cores fixas, alto contraste no tema). Cicla se houver mais clusters.
const PALETTE = ["#76b900", "#3b82f6", "#f59e0b", "#ec4899", "#8b5cf6", "#14b8a6"] as const;

type Phase = "loading" | "ready" | "error";

export function CohortRadar() {
  const [data, setData] = useState<CohortClustering | null>(null);
  const [phase, setPhase] = useState<Phase>("loading");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let alive = true;
    getCohortClusters()
      .then((d) => {
        if (!alive) return;
        setData(d);
        setPhase("ready");
      })
      .catch((err) => {
        if (!alive) return;
        setError(err instanceof Error ? err.message : "Erro ao carregar o radar.");
        setPhase("error");
      });
    return () => {
      alive = false;
    };
  }, []);

  if (phase === "loading") {
    return (
      <p className="rounded-lg border border-border bg-card px-4 py-6 text-sm text-muted-foreground">
        Carregando o radar da coorte...
      </p>
    );
  }
  if (phase === "error") {
    return (
      <p className="rounded-lg border border-border bg-card px-4 py-6 text-sm text-destructive">
        {error}
      </p>
    );
  }
  if (!data || data.n_companies === 0) {
    return (
      <p className="rounded-lg border border-border bg-card px-4 py-6 text-sm text-muted-foreground">
        Coorte vazia — rode a descoberta em lote (seed/cohort) para popular o radar.
      </p>
    );
  }

  return (
    <div className="flex flex-col gap-8">
      <Scatter data={data} />

      <section className="flex flex-col gap-3">
        <div className="flex items-center justify-between gap-4">
          <h2 className="text-base font-semibold">
            {data.clusters.length} {data.clusters.length === 1 ? "cluster" : "clusters"} ·{" "}
            {data.n_companies} startups
          </h2>
          <span className="text-xs text-muted-foreground">ordenados por prontidao de graduacao</span>
        </div>
        <ol className="flex flex-col gap-3">
          {data.clusters.map((c, i) => (
            <li
              key={c.id}
              className="flex flex-col gap-3 rounded-lg border border-border bg-card p-4 text-card-foreground"
            >
              <div className="flex flex-wrap items-center gap-2">
                <span
                  className="size-3 shrink-0 rounded-full"
                  style={{ backgroundColor: PALETTE[i % PALETTE.length] }}
                />
                <h3 className="font-semibold">{c.label}</h3>
                {c.graduation_ready && (
                  <span className="rounded-full border border-brand/40 px-2 py-0.5 text-xs font-medium text-brand-ink">
                    ★ alvo de graduacao
                  </span>
                )}
                {c.classe_dominante && (
                  <span className="text-xs text-muted-foreground">{c.classe_dominante}</span>
                )}
              </div>
              <div className="flex flex-wrap gap-x-6 gap-y-1 text-xs text-muted-foreground">
                <Stat label="Startups" value={String(c.size)} />
                <Stat label="AIMI medio" value={c.mean_aimi.toFixed(0)} />
                <Stat label="Inception medio" value={c.mean_inception.toFixed(0)} highlight />
                <Stat
                  label="Prontas (★)"
                  value={`${Math.round(c.graduation_ready_share * 100)}%`}
                />
              </div>
              <div className="flex flex-wrap gap-2">
                {c.members.map((m) => (
                  <Link
                    key={m.id}
                    href={`/radar/${m.id}`}
                    className="rounded-md border border-border px-2 py-1 text-xs hover:border-brand/40"
                  >
                    {m.nome}
                    {m.graduation_ready && <span className="ml-1 text-brand-ink">★</span>}
                  </Link>
                ))}
              </div>
            </li>
          ))}
        </ol>
      </section>

      <p className="text-xs text-muted-foreground">
        Clustering: <span className="font-mono">{data.method}</span> · embeddings:{" "}
        <span className="font-mono">{data.embedder}</span>. O default e offline/deterministico (numpy +
        hashing); cuML/nv-embedqa entram atras de flag.
      </p>
    </div>
  );
}

// Scatter 2D em SVG: mapeia as coords da projecao no viewBox e plota cada startup. Cor = cluster;
// alvo ★ ganha anel. Hover mostra o nome (title). Pontos linkam o detalhe AIMI da startup.
function Scatter({ data }: { data: CohortClustering }) {
  const pts: Array<{ m: CohortClusterMember; ci: number }> = data.clusters.flatMap((c, ci) =>
    c.members.map((m) => ({ m, ci })),
  );
  const xs = pts.map((p) => p.m.x);
  const ys = pts.map((p) => p.m.y);
  const minX = Math.min(...xs);
  const maxX = Math.max(...xs);
  const minY = Math.min(...ys);
  const maxY = Math.max(...ys);
  const pad = 6;
  const span = (lo: number, hi: number) => (hi - lo || 1);
  const sx = (x: number) => pad + ((x - minX) / span(minX, maxX)) * (100 - 2 * pad);
  const sy = (y: number) => pad + ((maxY - y) / span(minY, maxY)) * (100 - 2 * pad);

  return (
    <div className="rounded-lg border border-border bg-card p-4">
      <svg viewBox="0 0 100 100" className="h-72 w-full" role="img" aria-label="Radar da coorte">
        {pts.map(({ m, ci }) => {
          const color = PALETTE[ci % PALETTE.length];
          return (
            <a key={m.id} href={`/radar/${m.id}`}>
              <circle
                cx={sx(m.x)}
                cy={sy(m.y)}
                r={m.graduation_ready ? 2.6 : 1.8}
                fill={color}
                fillOpacity={0.85}
                stroke={m.graduation_ready ? "var(--brand)" : "transparent"}
                strokeWidth={m.graduation_ready ? 0.8 : 0}
              >
                <title>
                  {m.nome}
                  {m.classe ? ` · ${m.classe}` : ""}
                  {m.aimi != null ? ` · AIMI ${m.aimi}` : ""}
                  {m.graduation_ready ? " · ★ alvo de graduacao" : ""}
                </title>
              </circle>
            </a>
          );
        })}
      </svg>
      <p className="mt-2 text-center text-xs text-muted-foreground">
        Cada ponto e uma startup, posicionada por similaridade de perfil; cor = cluster, anel = alvo
        de graduacao ★.
      </p>
    </div>
  );
}

function Stat({
  label,
  value,
  highlight = false,
}: {
  label: string;
  value: string;
  highlight?: boolean;
}) {
  return (
    <span>
      {label}: <span className={cn("font-mono", highlight && "font-semibold text-brand-ink")}>{value}</span>
    </span>
  );
}
