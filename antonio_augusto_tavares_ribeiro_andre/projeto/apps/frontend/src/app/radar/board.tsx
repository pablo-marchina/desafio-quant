"use client";

// Radar de startups (F5.4/F5.11): a lista filtravel por setor, classe de maturidade, AIMI minimo
// e tecnologia — a tech que a startup usa e a tech NVIDIA recomendada — ja ordenada por
// inception_priority (a fila de outreach do gerente, F6.13). Consome o `GET /companies` (F5.2);
// os filtros combinam em AND e a ordenacao vem do backend. As tags de tech vem do vocabulario
// controlado (`GET /companies/facets`, F5.11), entao os selects so oferecem tags que existem.
// Cada linha abre o detalhe AIMI da startup (radar dos 4 pilares + evidencias, F5.5).

import { useEffect, useState } from "react";

import Link from "next/link";

import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { listCompanies, listTechFacets, type CompanyOut, type TechFacets } from "@/lib/api";

// Classes de maturidade (Classification, packages/schemas/enums.py — §5.1). null = sem filtro.
const CLASSES: ReadonlyArray<{ value: string | null; label: string }> = [
  { value: null, label: "Todas" },
  { value: "AI-native", label: "AI-native" },
  { value: "AI-enabled", label: "AI-enabled" },
  { value: "non-AI", label: "non-AI" },
];

type Phase = "loading" | "ready" | "error";

export function RadarBoard() {
  const [setor, setSetor] = useState("");
  const [classe, setClasse] = useState<string | null>(null);
  const [minAimi, setMinAimi] = useState(0);
  const [tech, setTech] = useState("");
  const [nvidiaTech, setNvidiaTech] = useState("");
  const [facets, setFacets] = useState<TechFacets>({ tech: [], nvidia_tech: [] });
  const [companies, setCompanies] = useState<CompanyOut[]>([]);
  const [phase, setPhase] = useState<Phase>("loading");
  const [error, setError] = useState<string | null>(null);

  // Vocabulario controlado das facetas de tech (F5.11) — carregado uma vez; alimenta os selects.
  // Falha silenciosa: sem facetas os selects ficam vazios, a lista (abaixo) ainda funciona.
  useEffect(() => {
    let alive = true;
    listTechFacets()
      .then((f) => alive && setFacets(f))
      .catch(() => {});
    return () => {
      alive = false;
    };
  }, []);

  // Recarrega quando um filtro muda; debounce curto para nao buscar a cada tecla do setor.
  useEffect(() => {
    let alive = true;
    const timer = setTimeout(() => {
      setPhase("loading");
      listCompanies({
        setor,
        classificacao: classe ?? undefined,
        minAimi,
        tech: tech || undefined,
        nvidiaTech: nvidiaTech || undefined,
      })
        .then((rows) => {
          if (!alive) return;
          setCompanies(rows);
          setPhase("ready");
        })
        .catch((err) => {
          if (!alive) return;
          setError(err instanceof Error ? err.message : "Erro ao carregar as startups.");
          setPhase("error");
        });
    }, 300);
    return () => {
      alive = false;
      clearTimeout(timer);
    };
  }, [setor, classe, minAimi, tech, nvidiaTech]);

  return (
    <div className="flex flex-col gap-8">
      <div className="flex flex-col gap-4">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-end">
          <label className="flex flex-1 flex-col gap-1">
            <span className="text-xs font-medium text-muted-foreground">Setor</span>
            <input
              value={setor}
              onChange={(e) => setSetor(e.target.value)}
              placeholder="ex.: healthtech"
              className="h-9 rounded-lg border border-border bg-background px-3 text-sm text-foreground outline-none placeholder:text-muted-foreground focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50"
            />
          </label>
          <label className="flex w-full flex-col gap-1 sm:w-56">
            <span className="text-xs font-medium text-muted-foreground">
              AIMI minimo: <span className="font-mono text-foreground">{minAimi}</span>
            </span>
            <input
              type="range"
              min={0}
              max={100}
              step={5}
              value={minAimi}
              onChange={(e) => setMinAimi(Number(e.target.value))}
              className="h-9 w-full accent-primary"
            />
          </label>
        </div>

        {/* Facetas de tech (F5.11): vocabulario controlado vindo de `listTechFacets`. */}
        <div className="flex flex-col gap-3 sm:flex-row sm:items-end">
          <TechSelect
            label="Tecnologia que usa"
            value={tech}
            onChange={setTech}
            options={facets.tech}
          />
          <TechSelect
            label="Tech NVIDIA recomendada"
            value={nvidiaTech}
            onChange={setNvidiaTech}
            options={facets.nvidia_tech}
          />
        </div>

        <div className="inline-flex w-fit flex-wrap gap-1 rounded-lg border border-border p-1">
          {CLASSES.map((c) => (
            <Button
              key={c.label}
              type="button"
              size="sm"
              variant={classe === c.value ? "default" : "ghost"}
              onClick={() => setClasse(c.value)}
            >
              {c.label}
            </Button>
          ))}
        </div>
      </div>

      <section className="flex flex-col gap-3">
        <div className="flex items-center justify-between gap-4">
          <h2 className="text-base font-semibold">
            {phase === "ready"
              ? `${companies.length} ${companies.length === 1 ? "startup" : "startups"}`
              : "Startups"}
          </h2>
          <span className="text-xs text-muted-foreground">ordenadas por Inception Priority</span>
        </div>

        {phase === "loading" && (
          <p className="rounded-lg border border-border bg-card px-4 py-6 text-sm text-muted-foreground">
            Carregando...
          </p>
        )}

        {phase === "error" && error && (
          <p className="rounded-lg border border-border bg-card px-4 py-6 text-sm text-destructive">
            {error}
          </p>
        )}

        {phase === "ready" && companies.length === 0 && (
          <p className="rounded-lg border border-border bg-card px-4 py-6 text-sm text-muted-foreground">
            Nenhuma startup para os filtros atuais.
          </p>
        )}

        {phase === "ready" && companies.length > 0 && (
          <ol className="flex flex-col gap-2">
            {companies.map((c, i) => (
              <li key={c.id}>
                <Link
                  href={`/radar/${c.id}`}
                  className="flex items-center gap-4 rounded-lg border border-border bg-card p-4 text-card-foreground transition-colors hover:border-brand/40 focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50 focus-visible:outline-none"
                >
                  <span className="w-6 shrink-0 text-center font-mono text-sm text-muted-foreground">
                    {i + 1}
                  </span>
                  <div className="flex min-w-0 flex-1 flex-col gap-1">
                    <div className="flex flex-wrap items-center gap-2">
                      <h3 className="font-semibold">{c.nome}</h3>
                      {c.classificacao && <ClasseBadge classe={c.classificacao} />}
                    </div>
                    <p className="truncate text-sm text-muted-foreground">
                      {c.setor ?? "Setor nao informado"}
                    </p>
                  </div>
                  <Metric label="AIMI" value={c.aimi_total} />
                  <Metric label="Inception" value={c.inception_priority} highlight />
                </Link>
              </li>
            ))}
          </ol>
        )}

        {phase === "ready" && companies.length > 0 && (
          <p className="text-xs text-muted-foreground">
            Clique em uma startup para ver o radar AIMI dos 4 pilares e as evidencias citadas.
          </p>
        )}
      </section>
    </div>
  );
}

// Faceta de tech (F5.11): select do vocabulario controlado. "" = sem filtro ("Todas"); as opcoes
// sao as tags normalizadas que o backend (`/companies/facets`) garante existirem na coorte. Some
// quando nao ha tag (ex.: coorte sem recomendacao ainda) — nada de filtro vazio na tela.
function TechSelect({
  label,
  value,
  onChange,
  options,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  options: string[];
}) {
  if (options.length === 0) return null;
  return (
    <label className="flex w-full flex-col gap-1 sm:w-56">
      <span className="text-xs font-medium text-muted-foreground">{label}</span>
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="h-9 rounded-lg border border-border bg-background px-3 text-sm text-foreground outline-none focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50"
      >
        <option value="">Todas</option>
        {options.map((tag) => (
          <option key={tag} value={tag}>
            {tag}
          </option>
        ))}
      </select>
    </label>
  );
}

// Classe de maturidade (§5.1): AI-native ganha destaque (o alvo do Inception); o resto e neutro.
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

// Numero do diagnostico (AIMI / Inception Priority); "—" quando a empresa ainda nao foi pontuada.
function Metric({
  label,
  value,
  highlight = false,
}: {
  label: string;
  value: number | null;
  highlight?: boolean;
}) {
  return (
    <div className="flex w-16 shrink-0 flex-col items-end gap-0.5 text-right">
      <span className="text-xs text-muted-foreground">{label}</span>
      <span
        className={cn("font-mono text-sm", highlight && "font-semibold text-brand-ink")}
      >
        {value ?? "—"}
      </span>
    </div>
  );
}
