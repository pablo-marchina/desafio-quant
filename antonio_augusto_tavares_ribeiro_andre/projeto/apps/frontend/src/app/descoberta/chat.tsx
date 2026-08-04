"use client";

// Chat de descoberta da coorte (F5.12): pergunta em PT-BR -> `GET /discover` (F3.10) -> empresas.
// O backend faz dois estagios (packages/agents/cohort_rag.py): (1) traduz a pergunta nos filtros
// estruturados que a lista ja entende (tech NVIDIA / classe / AIMI) e (2) se houver texto livre
// (setor/dominio que o vocabulario nao cobre, ex.: "fraude", "agro") re-ordena por similaridade
// semantica e cita a evidencia de cada match (§8). A tela desenha como conversa: balao da pergunta
// -> resumo + chip do entendido + chip do modo -> cartoes de empresa (cada um abre o detalhe AIMI em
// /radar/[id], F5.5) com a fonte que sustenta o match logo abaixo.

import { useEffect, useRef, useState } from "react";

import Link from "next/link";

import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import {
  discoverCohort,
  type CompanyOut,
  type DiscoverHit,
  type DiscoverResult,
  type EvidenceOut,
} from "@/lib/api";

// Exemplos que exercitam o parser (discovery.py): intencao de inferencia -> NIM, classe + "maduras"
// -> AIMI>=50, termo NVIDIA -> tag, piso de AIMI. Setor/regiao nao sao parseados (o parser cobre
// tech/classe/AIMI), entao os exemplos ficam nesses eixos para o `entendido` casar com o resultado.
const EXEMPLOS: readonly string[] = [
  "Quais startups tem gap de inferencia?",
  "AI-native maduras",
  "Startups de deteccao de fraude", // texto livre -> busca semantica + citacao
  "AIMI acima de 40",
];

// Um turno da conversa: a pergunta + o estado da resposta (carregando / pronta / erro).
type Turn = {
  id: number;
  pergunta: string;
  status: "loading" | "done" | "error";
  result?: DiscoverResult;
  error?: string;
};

export function DiscoveryChat() {
  const [input, setInput] = useState("");
  const [turns, setTurns] = useState<Turn[]>([]);
  const [busy, setBusy] = useState(false);
  const nextId = useRef(1);
  const bottomRef = useRef<HTMLDivElement>(null);

  // Rola para a ultima resposta quando a conversa cresce (scroll, nao set-state — ok em effect).
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [turns]);

  // Faz a pergunta: cria o turno (carregando), consulta o `/discover` e atualiza o turno no lugar.
  async function ask(question: string) {
    const q = question.trim();
    if (!q || busy) return;
    const id = nextId.current++;
    setInput("");
    setBusy(true);
    setTurns((prev) => [...prev, { id, pergunta: q, status: "loading" }]);
    try {
      const result = await discoverCohort(q);
      setTurns((prev) => prev.map((t) => (t.id === id ? { ...t, status: "done", result } : t)));
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Erro ao consultar a coorte.";
      setTurns((prev) => prev.map((t) => (t.id === id ? { ...t, status: "error", error: msg } : t)));
    } finally {
      setBusy(false);
    }
  }

  function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    ask(input);
  }

  return (
    <div className="flex flex-col gap-6">
      {turns.length === 0 ? (
        <EmptyState onPick={ask} disabled={busy} />
      ) : (
        <ol className="flex flex-col gap-8">
          {turns.map((turn) => (
            <li key={turn.id} className="flex flex-col gap-3">
              {/* Pergunta do usuario (balao a direita). */}
              <div className="flex justify-end">
                <p className="max-w-[85%] rounded-2xl rounded-br-sm bg-primary px-4 py-2 text-sm text-primary-foreground">
                  {turn.pergunta}
                </p>
              </div>
              {/* Resposta da coorte (alinhada a esquerda). */}
              {turn.status === "loading" && (
                <p className="text-sm text-muted-foreground">Consultando a coorte...</p>
              )}
              {turn.status === "error" && (
                <p className="rounded-lg border border-border bg-card px-4 py-3 text-sm text-destructive">
                  {turn.error}
                </p>
              )}
              {turn.status === "done" && turn.result && <Answer result={turn.result} />}
            </li>
          ))}
          <div ref={bottomRef} />
        </ol>
      )}

      {/* Caixa de pergunta — fica acessivel ao final da conversa enquanto se rola (sticky). */}
      <form
        onSubmit={onSubmit}
        className="sticky bottom-4 flex flex-col gap-2 rounded-lg bg-background/80 py-2 backdrop-blur sm:flex-row"
      >
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Pergunte sobre a coorte (ex.: quem tem gap de inferencia?)"
          disabled={busy}
          className="h-10 flex-1 rounded-lg border border-border bg-background px-3 text-sm text-foreground shadow-sm outline-none placeholder:text-muted-foreground focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50 disabled:opacity-50"
        />
        <Button type="submit" variant="brand" size="lg" disabled={busy || input.trim() === ""}>
          {busy ? "Buscando..." : "Perguntar"}
        </Button>
      </form>
    </div>
  );
}

// Resposta da coorte a uma pergunta: o resumo + chip de como foi interpretada + chip do modo
// (filtro x semantico) + os cartoes de empresa, cada um com a fonte que sustenta o match.
function Answer({ result }: { result: DiscoverResult }) {
  const { resumo, entendido, modo, resultados } = result;
  return (
    <div className="flex flex-col gap-3">
      <p className="text-sm text-foreground">{resumo}</p>
      <div className="flex flex-wrap gap-2">
        {entendido && (
          <span className="inline-flex w-fit items-center gap-1.5 rounded-full border border-border px-3 py-1 text-xs text-muted-foreground">
            <span className="font-medium text-foreground">Entendi:</span> {entendido}
          </span>
        )}
        {modo === "semantico" && (
          <span className="inline-flex w-fit items-center rounded-full border border-brand/40 px-3 py-1 text-xs text-brand-ink">
            busca semantica
          </span>
        )}
      </div>
      {resultados.length > 0 ? (
        <ol className="flex flex-col gap-3">
          {resultados.map((hit, i) => (
            <li key={hit.empresa.id} className="flex flex-col gap-1.5">
              <CompanyCard rank={i + 1} hit={hit} semantico={modo === "semantico"} />
              {hit.citacao && <Citation citacao={hit.citacao} />}
            </li>
          ))}
        </ol>
      ) : (
        <p className="rounded-lg border border-border bg-card px-4 py-3 text-sm text-muted-foreground">
          Nenhuma startup da coorte casou com esses criterios. Tente afrouxar o filtro (ex.: sem o
          piso de AIMI) ou pergunte por outra tecnologia.
        </p>
      )}
    </div>
  );
}

// Cartao de empresa no resultado: espelha a linha do radar (F5.4) e destaca as techs NVIDIA
// recomendadas (F4.3). No modo semantico mostra a relevancia (similaridade a busca). Abre o detalhe
// AIMI da startup (radar dos 4 pilares + evidencias, F5.5).
function CompanyCard({
  rank,
  hit,
  semantico,
}: {
  rank: number;
  hit: DiscoverHit;
  semantico: boolean;
}) {
  const company: CompanyOut = hit.empresa;
  return (
    <Link
      href={`/radar/${company.id}`}
      className="flex items-center gap-4 rounded-lg border border-border bg-card p-4 text-card-foreground transition-colors hover:border-brand/40 focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50 focus-visible:outline-none"
    >
      <span className="w-6 shrink-0 text-center font-mono text-sm text-muted-foreground">{rank}</span>
      <div className="flex min-w-0 flex-1 flex-col gap-1.5">
        <div className="flex flex-wrap items-center gap-2">
          <h3 className="font-semibold">{company.nome}</h3>
          {company.classificacao && <ClasseBadge classe={company.classificacao} />}
        </div>
        <p className="truncate text-sm text-muted-foreground">
          {company.setor ?? "Setor nao informado"}
        </p>
        {company.nvidia_techs.length > 0 && (
          <div className="flex flex-wrap gap-1">
            {company.nvidia_techs.map((t) => (
              <span
                key={t}
                className="rounded-full bg-brand/10 px-2 py-0.5 text-[11px] font-medium text-brand-ink"
              >
                {t}
              </span>
            ))}
          </div>
        )}
      </div>
      {semantico && hit.similaridade != null && (
        <Metric label="Relevancia" value={Math.round(hit.similaridade * 100)} />
      )}
      <Metric label="AIMI" value={company.aimi_total} />
      <Metric label="Inception" value={company.inception_priority} highlight />
    </Link>
  );
}

// Fonte que sustenta o match (§8: nada sem evidencia rastreavel): snippet citado + link externo a
// fonte. Fica FORA do <Link> do cartao (um <a> nao pode aninhar outro) — abre em nova aba.
function Citation({ citacao }: { citacao: EvidenceOut }) {
  return (
    <a
      href={citacao.url}
      target="_blank"
      rel="noopener noreferrer"
      className="ml-10 flex flex-col gap-0.5 rounded-md border border-dashed border-border px-3 py-1.5 text-xs text-muted-foreground transition-colors hover:border-brand/40 hover:text-foreground"
    >
      <span className="line-clamp-2 italic">&ldquo;{citacao.snippet}&rdquo;</span>
      <span className="truncate font-medium text-brand-ink">
        {citacao.source_title ?? citacao.url}
      </span>
    </a>
  );
}

// Estado inicial: explica o que a descoberta entende e oferece exemplos que casam com o parser.
function EmptyState({ onPick, disabled }: { onPick: (q: string) => void; disabled: boolean }) {
  return (
    <div className="flex flex-col gap-4 rounded-lg border border-dashed border-border bg-card/40 px-5 py-8">
      <div className="flex flex-col gap-1">
        <h2 className="text-base font-semibold">Comece por uma pergunta</h2>
        <p className="text-sm text-muted-foreground">
          A descoberta entende tecnologia NVIDIA (ex.: NIM, TensorRT), classe (AI-native / AI-enabled)
          e piso de maturidade (AIMI) — e tambem <span className="text-foreground">texto livre</span>{" "}
          (ex.: setor ou dominio), buscando por similaridade semantica e citando a evidencia. Toque em
          um exemplo ou escreva o seu.
        </p>
      </div>
      <div className="flex flex-wrap gap-2">
        {EXEMPLOS.map((ex) => (
          <Button
            key={ex}
            type="button"
            variant="outline"
            size="sm"
            disabled={disabled}
            onClick={() => onPick(ex)}
          >
            {ex}
          </Button>
        ))}
      </div>
    </div>
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
      <span className={cn("font-mono text-sm", highlight && "font-semibold text-brand-ink")}>
        {value ?? "—"}
      </span>
    </div>
  );
}
