"use client";

import { useState, useEffect, useRef, Suspense } from "react";
import { useSearchParams, useRouter, usePathname } from "next/navigation";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import Link from "next/link";
import { motion, AnimatePresence, useReducedMotion } from "motion/react";
import {
  ArrowSquareOutIcon,
  CaretDownIcon,
  DownloadSimpleIcon,
  MagnifyingGlassIcon,
  SlidersHorizontalIcon,
  TerminalWindowIcon,
  XIcon,
} from "@phosphor-icons/react";
import GraficoRadar, { CORES_SERIES } from "./GraficoRadar";
import TabsRadar from "./TabsRadar";
import { useAnalise } from "./AnaliseProvider";

// descreve o formato de cada empresa que vem da API (GET /empresas)
type Empresa = {
  nome: string;
  setor: string | null;
  classificacao: string | null;
  score: number | null;
  notas: Record<string, number> | null;
  criado_em: string | null;
};

// janela do selo "nova" no ranking (recém-adicionada = análise entrou no
// banco há menos de X horas)
const HORAS_NOVA = 24;


function ehNova(e: Empresa): boolean {
  if (!e.criado_em) return false;
  // o backend grava em UTC mas o isoformat pode vir sem offset; o "Z"
  // garante que o navegador não interprete como horário local
  const iso =
    e.criado_em.includes("+") || e.criado_em.endsWith("Z")
      ? e.criado_em
      : e.criado_em + "Z";
  return Date.now() - new Date(iso).getTime() < HORAS_NOVA * 3600 * 1000;
}

type Detalhe = {
  briefing: string | null;
  recomendacao: {
    tecnologias?: string[];
    proxima_acao?: string;
    evidencias?: string[];
  } | null;
};

// O briefing gerado pelo pipeline termina numa seção "## Conclusão".
// Extraímos só esse trecho para o modal (a leitura completa fica na página).
function extrairConclusao(briefing: string | null): string | null {
  if (!briefing) return null;
  const m = briefing.match(/##\s*Conclus[aã]o[^\n]*\n([\s\S]*?)(?=\n##\s|$)/i);
  return m ? m[1].trim() : null;
}

const EIXOS = [
  { key: "ai_native", label: "AI-Native" },
  { key: "nvidia_fit", label: "NVIDIA-Fit" },
  { key: "tracao", label: "Tração" },
  { key: "time_ia", label: "Time de IA" },
];

// Presets de pesos: cada um é uma INTENÇÃO de gestor (o que ele está
// caçando), não um eixo isolado. Não precisam somar 1, o compor normaliza.
const PRESETS: { nome: string; pesos: Record<string, number> }[] = [
  {
    // visão equilibrada, o ponto de partida
    nome: "Padrão",
    pesos: { ai_native: 0.3, nvidia_fit: 0.3, tracao: 0.2, time_ia: 0.2 },
  },
  {
    // quem tem gap técnico que o portfólio NVIDIA resolve AGORA:
    // conversa comercial de curto prazo
    nome: "Adoção imediata",
    pesos: { ai_native: 0.35, nvidia_fit: 0.4, tracao: 0.15, time_ia: 0.1 },
  },
  {
    // early-stage promissora: produto AI-native e time técnico fortes,
    // tração ainda não importa (aposta de longo prazo)
    nome: "Aposta técnica",
    pesos: { ai_native: 0.35, nvidia_fit: 0.15, tracao: 0.1, time_ia: 0.4 },
  },
  {
    // quem já provou mercado (clientes, receita, captação): parceria com
    // menos risco, mesmo que o uso de IA seja menos profundo
    nome: "Mercado provado",
    pesos: { ai_native: 0.2, nvidia_fit: 0.25, tracao: 0.45, time_ia: 0.1 },
  },
];
const PESOS_PADRAO = PRESETS[0].pesos;

// compara dois conjuntos de pesos com tolerância (evita 0.30000000000000004)
function pesosIguais(a: Record<string, number>, b: Record<string, number>) {
  return EIXOS.every((e) => Math.abs((a[e.key] ?? 0) - (b[e.key] ?? 0)) < 0.001);
}

// Um campo de CSV seguro: SEMPRE entre aspas duplas, com aspas internas
// dobradas (""). Sem isso, um setor como "Finance, Health, Insurance"
// estouraria em 3 colunas e quebraria o arquivo.
function campoCsv(v: string | number | null | undefined): string {
  return `"${String(v ?? "").replace(/"/g, '""')}"`;
}

// "?w=0.40,0.35,0.10,0.15" -> pesos na ordem dos EIXOS; null se malformado
function parsearPesosDaUrl(w: string | null): Record<string, number> | null {
  if (!w) return null;
  const nums = w.split(",").map(Number);
  if (nums.length !== 4 || nums.some((n) => Number.isNaN(n))) return null;
  const clamp = (n: number) => Math.min(1, Math.max(0, n));
  return {
    ai_native: clamp(nums[0]),
    nvidia_fit: clamp(nums[1]),
    tracao: clamp(nums[2]),
    time_ia: clamp(nums[3]),
  };
}

// soma ponderada das 4 notas; é isso que faz o re-rank ao vivo dos sliders
function compor(
  notas: Record<string, number> | null,
  pesos: Record<string, number>
): number | null {
  if (!notas) return null; // empresa sem dados -> sem score
  const chaves = ["ai_native", "nvidia_fit", "tracao", "time_ia"];
  let totalPeso = 0;
  let soma = 0;
  for (const k of chaves) {
    totalPeso += pesos[k] ?? 0;
    soma += (pesos[k] ?? 0) * (notas[k] ?? 0);
  }
  if (totalPeso == 0) return 0;
  return Math.round((soma / totalPeso) * 100) / 100; // arredonda a 2 casas
}

function Badge({ classificacao }: { classificacao: string | null }) {
  const cores: Record<string, string> = {
    "ai-native": "text-nvidia border-nvidia/50",
    "ai-enabled": "text-amber border-amber/50",
  };
  const cor = cores[classificacao ?? ""] ?? "text-ink-muted border-line";
  return (
    <span className={`inline-block rounded-full border px-2 py-0.5 text-xs ${cor}`}>
      {classificacao ?? "n/d"}
    </span>
  );
}

// skeleton com a FORMA das linhas do ranking (não um spinner genérico):
// o usuário já vê a estrutura que vai receber
function SkeletonLista() {
  return (
    <div className="divide-y divide-line rounded-xl border border-line bg-[#0C0C0C]">
      {Array.from({ length: 6 }).map((_, i) => (
        <div
          key={i}
          className="flex animate-pulse items-center gap-4 px-5 py-4 motion-reduce:animate-none"
        >
          <div className="h-4 w-5 rounded bg-surface-2" />
          <div className="min-w-0 flex-1 space-y-2">
            <div className="h-4 w-40 rounded bg-surface-2" />
            <div className="h-3 w-24 rounded bg-surface-2" />
          </div>
          <div className="h-5 w-16 rounded-full bg-surface-2" />
          <div className="h-4 w-10 rounded bg-surface-2" />
        </div>
      ))}
    </div>
  );
}

function RadarApp() {
  // Lê o ?q= que a busca da landing manda (ex.: /radar?q=IA em saúde).
  // useSearchParams exige um <Suspense> por volta (ver export default).
  const searchParams = useSearchParams();
  const consultaInicial = searchParams.get("q") ?? "";
  const router = useRouter();
  const pathname = usePathname();

  const [empresas, setEmpresas] = useState<Empresa[]>([]);
  const [carregando, setCarregando] = useState(true);
  const [erroApi, setErroApi] = useState(false);

  // "URL como estado": os pesos nascem do ?w= se ele existir (link
  // compartilhado / reload) e caem no padrão caso contrário. O useState com
  // função só roda essa inicialização UMA vez, na montagem.
  const [pesos, setPesos] = useState<Record<string, number>>(
    () => parsearPesosDaUrl(searchParams.get("w")) ?? PESOS_PADRAO
  );

  // ...e toda mudança de pesos (slider ou preset) é escrita de volta no ?w=,
  // com debounce de 250ms (o slider dispara dezenas de mudanças por arrasto).
  // replace (não push) troca a URL sem empilhar histórico; a query preserva
  // o que já estiver lá (?q=). Pesos no padrão = URL limpa, sem ?w=.
  useEffect(() => {
    const t = setTimeout(() => {
      const params = new URLSearchParams(window.location.search);
      if (pesosIguais(pesos, PESOS_PADRAO)) {
        params.delete("w");
      } else {
        params.set(
          "w",
          EIXOS.map((e) => (pesos[e.key] ?? 0).toFixed(2)).join(",")
        );
      }
      const query = params.toString();
      router.replace(query ? `${pathname}?${query}` : pathname, {
        scroll: false,
      });
    }, 250);
    return () => clearTimeout(t);
  }, [pesos, pathname, router]);

  const [selecionada, setSelecionada] = useState<string | null>(null);
  const [detalhe, setDetalhe] = useState<Detalhe | null>(null);

  // seleção para COMPARAR (independente do modal de detalhe `selecionada`):
  // até 3 nomes; só empresas com as 4 notas entram
  const [comparar, setComparar] = useState<string[]>([]);
  const [comparadorAberto, setComparadorAberto] = useState(false);

  const alternarComparar = (nome: string) =>
    setComparar((atual) =>
      atual.includes(nome)
        ? atual.filter((n) => n !== nome)
        : atual.length >= 3
          ? atual // 4ª seleção bloqueada (o checkbox já vem desabilitado)
          : [...atual, nome]
    );

  // o texto digitado; já chega pré-preenchido com o termo vindo da landing
  const [nova, setNova] = useState(consultaInicial);
  const [analisando, setAnalisando] = useState(false);

  // progresso ao vivo da análise: vem do CONTEXTO (AnaliseProvider, no
  // layout), então uma análise sobrevive à troca de abas. O modal/mini-barra
  // são renderizados pelo provider, não aqui.
  const { progresso, analisar: rodarAnalise } = useAnalise();
  const emAnalise = progresso.aberto && !progresso.done;

  // filtros da sidebar: refinam a lista JÁ carregada, sem nenhum fetch novo.
  // (diferente do "Analisar nova startup" do topo, que roda o pipeline)
  const [filtroNome, setFiltroNome] = useState("");
  const [filtroClassificacao, setFiltroClassificacao] = useState<string[]>([]);
  const [filtroSetor, setFiltroSetor] = useState<string[]>([]);
  const [filtroNovas, setFiltroNovas] = useState(false);
  // no mobile a sidebar de filtros fica escondida atrás de um botão, para
  // não empurrar o ranking (o que importa) tela abaixo; no desktop (lg+)
  // ela é sempre visível
  const [filtrosAbertos, setFiltrosAbertos] = useState(false);
  // a lista de setores pode ser longa; fica num acordeão (fechado por padrão)
  const [setorAberto, setSetorAberto] = useState(false);

  const reduce = useReducedMotion();

  const carregarEmpresas = () => {
    setCarregando(true);
    fetch(`${process.env.NEXT_PUBLIC_API_URL}/empresas`)
      .then((res) => res.json())
      .then((data) => {
        setEmpresas(data);
        setErroApi(false);
      })
      .catch(() => setErroApi(true))
      .finally(() => setCarregando(false));
  };

  useEffect(() => {
    carregarEmpresas();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (!selecionada) {
      setDetalhe(null);
      return;
    }
    fetch(`${process.env.NEXT_PUBLIC_API_URL}/empresas/${selecionada}`)
      .then((res) => res.json())
      .then((data) => setDetalhe(data))
      .catch(() => setDetalhe(null));
  }, [selecionada]);

  // modal aberto: fecha no Esc e trava o scroll da página atrás
  useEffect(() => {
    if (!selecionada) return;
    const aoTeclar = (e: KeyboardEvent) => {
      if (e.key === "Escape") setSelecionada(null);
    };
    window.addEventListener("keydown", aoTeclar);
    document.body.style.overflow = "hidden";
    return () => {
      window.removeEventListener("keydown", aoTeclar);
      document.body.style.overflow = "";
    };
  }, [selecionada]);

  // mesmo tratamento para o comparador
  useEffect(() => {
    if (!comparadorAberto) return;
    const aoTeclar = (e: KeyboardEvent) => {
      if (e.key === "Escape") setComparadorAberto(false);
    };
    window.addEventListener("keydown", aoTeclar);
    document.body.style.overflow = "hidden";
    return () => {
      window.removeEventListener("keydown", aoTeclar);
      document.body.style.overflow = "";
    };
  }, [comparadorAberto]);

  const ranked = [...empresas].sort(
    (a, b) => (compor(b.notas, pesos) ?? -1) - (compor(a.notas, pesos) ?? -1)
  );

  // ── Estado derivado dos filtros ─────────────────────────────────
  // Nada disso vive em useState: é recalculado a cada render a partir de
  // `empresas` + filtros. Menos estado = menos chance de dessincronizar.

  // rótulo normalizado (null vira "sem-dados") para contar e filtrar
  const rotuloDe = (e: Empresa) => e.classificacao ?? "sem-dados";

  // opções de classificação presentes nos dados, em ordem fixa, com contador
  const opcoesClassificacao = ["ai-native", "ai-enabled", "non-ai", "sem-dados"]
    .map((rotulo) => ({
      rotulo,
      total: empresas.filter((e) => rotuloDe(e) === rotulo).length,
    }))
    .filter((o) => o.total > 0);

  // "Finance, Health, Insurance" vira 3 opções separadas; dedup + ordena
  const setoresDe = (e: Empresa) =>
    (e.setor ?? "").split(",").map((s) => s.trim()).filter(Boolean);
  const opcoesSetor = [...new Set(empresas.flatMap(setoresDe))]
    .sort((a, b) => a.localeCompare(b))
    .map((setor) => ({
      setor,
      total: empresas.filter((e) => setoresDe(e).includes(setor)).length,
    }));

  // total de recém-adicionadas (para o contador do filtro)
  const totalNovas = empresas.filter(ehNova).length;

  // texto E classificação E setor E novas; dentro de cada categoria é OU
  const filtroTexto = filtroNome.trim().toLowerCase();
  const visiveis = ranked.filter((e) => {
    const casaTexto =
      !filtroTexto ||
      e.nome.toLowerCase().includes(filtroTexto) ||
      (e.setor ?? "").toLowerCase().includes(filtroTexto);
    const casaClassificacao =
      filtroClassificacao.length === 0 ||
      filtroClassificacao.includes(rotuloDe(e));
    const casaSetor =
      filtroSetor.length === 0 ||
      setoresDe(e).some((s) => filtroSetor.includes(s));
    const casaNovas = !filtroNovas || ehNova(e);
    return casaTexto && casaClassificacao && casaSetor && casaNovas;
  });

  const temFiltro =
    filtroTexto !== "" ||
    filtroClassificacao.length > 0 ||
    filtroSetor.length > 0 ||
    filtroNovas;

  const limparFiltros = () => {
    setFiltroNome("");
    setFiltroClassificacao([]);
    setFiltroSetor([]);
    setFiltroNovas(false);
  };

  // marca/desmarca um valor numa lista de checkboxes
  const alternar = (
    lista: string[],
    setLista: (v: string[]) => void,
    valor: string
  ) =>
    setLista(
      lista.includes(valor)
        ? lista.filter((v) => v !== valor)
        : [...lista, valor]
    );

  const empresaSelecionada = empresas.find((x) => x.nome === selecionada);

  // as empresas escolhidas para comparar, na ordem da seleção (a cor da
  // série segue essa ordem: quem entrou primeiro é verde, depois azul...)
  const empresasComparar = comparar
    .map((nome) => empresas.find((x) => x.nome === nome))
    .filter((e): e is Empresa => Boolean(e && e.notas));

  // Exporta o ranking COMO ESTÁ NA TELA (já filtrado e ordenado pelos pesos
  // atuais), no cliente: monta o texto, embrulha num Blob (arquivo em
  // memória) e dispara o download, como o BaixarBriefing da página.
  const exportarCsv = () => {
    const cabecalho = [
      "posicao", "nome", "setor", "classificacao", "score",
      "ai_native", "nvidia_fit", "tracao", "time_ia",
    ];
    const linhas = visiveis.map((e, i) => {
      const s = compor(e.notas, pesos);
      return [
        i + 1,
        e.nome,
        e.setor ?? "",
        e.classificacao ?? "sem-dados",
        s === null ? "" : s.toFixed(2),
        e.notas?.ai_native ?? "",
        e.notas?.nvidia_fit ?? "",
        e.notas?.tracao ?? "",
        e.notas?.time_ia ?? "",
      ]
        .map(campoCsv)
        .join(",");
    });
    // ﻿ (BOM) faz o Excel reconhecer UTF-8 e abrir os acentos certos;
    // \r\n é o separador de linha que planilhas esperam
    const csv =
      "\uFEFF" + [cabecalho.map(campoCsv).join(","), ...linhas].join("\r\n");
    const blob = new Blob([csv], { type: "text/csv;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `radar-ranking-${new Date().toISOString().slice(0, 10)}.csv`;
    a.click();
    URL.revokeObjectURL(url); // libera a memória do Blob
  };

  // Analisa com progresso ao vivo: o hook cuida do SSE (e do footgun do
  // EventSource); aqui só esperamos a Promise e recarregamos a lista no fim.
  const analisar = async () => {
    const consulta = nova.trim();
    // emAnalise cobre análises disparadas em QUALQUER aba (estado global)
    if (!consulta || analisando || emAnalise) return;
    setAnalisando(true);
    const resultado = await rodarAnalise(consulta);
    setAnalisando(false);
    if (!resultado.erro) {
      setNova("");
      carregarEmpresas(); // a empresa nova entra na lista (com selo "nova")
    }
  };

  return (
    <main className="mx-auto w-full max-w-[1400px] px-6 py-8">
      <TabsRadar />

      {/* ── Barra de topo: título + contagem | analisar nova ─────────
          Empilha no mobile (flex-col) e vira linha no sm+. O input encolhe
          (min-w-0 flex-1) no mobile em vez de largura fixa, senão a barra
          estoura a tela e a página inteira ganha rolagem horizontal. */}
      <div className="mt-8 flex flex-col gap-4 sm:flex-row sm:flex-wrap sm:items-end sm:justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Radar</h1>
          <p className="mt-1 text-sm text-ink-muted">
            <span className="font-mono text-ink">{empresas.length}</span>{" "}
            startups analisadas
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <button
            onClick={exportarCsv}
            disabled={carregando || visiveis.length === 0}
            className="inline-flex shrink-0 items-center gap-1.5 rounded-lg border border-nvidia/70 px-4 py-2 text-sm font-medium text-ink transition-colors hover:border-nvidia hover:bg-nvidia/10 active:translate-y-px disabled:cursor-not-allowed disabled:opacity-50"
          >
            <DownloadSimpleIcon size={15} className="text-nvidia" aria-hidden />
            Exportar CSV
          </button>

        <form
          onSubmit={(e) => {
            e.preventDefault(); // evita o reload de página do submit clássico
            analisar();
          }}
          className="flex flex-1 items-center gap-2 sm:flex-none"
        >
          <input
            type="text"
            placeholder="Analisar nova startup..."
            aria-label="Analisar nova startup"
            value={nova}
            onChange={(e) => setNova(e.target.value)}
            className="min-w-0 flex-1 rounded-lg border border-line bg-[#0C0C0C] px-3 py-2 text-sm text-ink outline-none transition-colors placeholder:text-ink-muted/70 focus:border-nvidia/60 sm:w-80 sm:flex-none"
          />
          <button
            type="submit"
            disabled={analisando || emAnalise}
            className="shrink-0 rounded-lg bg-nvidia px-4 py-2 text-sm font-semibold text-black transition-colors hover:bg-nvidia-bright active:translate-y-px disabled:cursor-not-allowed disabled:opacity-60"
          >
            {analisando || emAnalise ? "Analisando..." : "Analisar"}
          </button>
        </form>
        </div>
      </div>

      {/* botão de filtros: só no mobile (lg:hidden); no desktop a sidebar
          já aparece sozinha */}
      <button
        onClick={() => setFiltrosAbertos((v) => !v)}
        aria-expanded={filtrosAbertos}
        className="mt-6 flex w-full items-center justify-between rounded-lg border border-line px-4 py-2.5 text-sm font-medium transition-colors hover:border-nvidia/50 lg:hidden"
      >
        <span className="flex items-center gap-2">
          <SlidersHorizontalIcon size={16} className="text-nvidia" aria-hidden />
          Filtros e pesos
        </span>
        <CaretDownIcon
          size={14}
          className={`text-ink-muted transition-transform ${filtrosAbertos ? "rotate-180" : ""}`}
          aria-hidden
        />
      </button>

      {/* ── 2 zonas: pesos à esquerda, ranking à direita ──────────── */}
      <div className="mt-4 grid grid-cols-1 items-start gap-6 lg:mt-8 lg:grid-cols-[280px_1fr]">
        {/* sem scroll próprio nem sticky: o painel rola junto com a página,
            como o painel de filtros do build.nvidia. No mobile só aparece
            quando o botão acima abre. */}
        <aside
          className={`${filtrosAbertos ? "block" : "hidden"} rounded-xl border border-line bg-[#0C0C0C] lg:block`}
        >
          {/* ── Buscar (filtra a lista; NÃO roda análise) ─────────── */}
          <div className="p-5">
            <h2 className="font-medium">Filtrar na lista</h2>
            <p className="mt-1 text-xs text-ink-muted">
              Refina quem já está no ranking; não roda análise nova.
            </p>
            <div className="mt-3 flex items-center gap-2 rounded-lg border border-line px-3 py-2 transition-colors focus-within:border-nvidia/60">
              <MagnifyingGlassIcon
                size={16}
                className="shrink-0 text-ink-muted"
                aria-hidden
              />
              <input
                type="text"
                value={filtroNome}
                onChange={(e) => setFiltroNome(e.target.value)}
                placeholder="Nome ou setor"
                aria-label="Filtrar na lista por nome ou setor"
                className="w-full bg-transparent text-sm text-ink outline-none placeholder:text-ink-muted/70"
              />
            </div>

            <label className="mt-3 flex cursor-pointer items-center justify-between gap-2 text-sm">
              <span className="flex items-center gap-2.5">
                <input
                  type="checkbox"
                  checked={filtroNovas}
                  onChange={() => setFiltroNovas((v) => !v)}
                  className="accent-nvidia"
                />
                Só recém-adicionadas ({HORAS_NOVA}h)
              </span>
              <span className="font-mono text-xs text-ink-muted">
                {totalNovas}
              </span>
            </label>
          </div>

          {/* ── Classificação ─────────────────────────────────────── */}
          {opcoesClassificacao.length > 0 && (
            <div className="border-t border-line p-5">
              <h3 className="text-sm font-medium">Classificação</h3>
              <div className="mt-3 space-y-2.5">
                {opcoesClassificacao.map((o) => (
                  <label
                    key={o.rotulo}
                    className="flex cursor-pointer items-center justify-between gap-2 text-sm"
                  >
                    <span className="flex items-center gap-2.5">
                      <input
                        type="checkbox"
                        checked={filtroClassificacao.includes(o.rotulo)}
                        onChange={() =>
                          alternar(
                            filtroClassificacao,
                            setFiltroClassificacao,
                            o.rotulo
                          )
                        }
                        className="accent-nvidia"
                      />
                      {o.rotulo}
                    </span>
                    <span className="font-mono text-xs text-ink-muted">
                      {o.total}
                    </span>
                  </label>
                ))}
              </div>
            </div>
          )}

          {/* ── Setor: acordeão (a lista pode ser longa; classificação não
                 precisa disso porque são sempre ~4) ──────────────────── */}
          {opcoesSetor.length > 0 && (
            <div className="border-t border-line p-5">
              {/* -m-2 p-2 aumenta a área de clique sem desalinhar o texto; o
                  hover cinza (bg-surface-2) deixa claro que é clicável */}
              <button
                onClick={() => setSetorAberto((v) => !v)}
                aria-expanded={setorAberto}
                className="-m-2 flex w-[calc(100%+1rem)] items-center justify-between gap-2 rounded-lg p-2 text-sm font-medium transition-colors hover:bg-surface-2"
              >
                <span className="flex items-center gap-2">
                  Setor
                  {/* quantos setores estão marcados, visível mesmo fechado */}
                  {filtroSetor.length > 0 && (
                    <span className="rounded-full bg-nvidia/15 px-2 py-0.5 text-xs text-nvidia">
                      {filtroSetor.length}
                    </span>
                  )}
                </span>
                <CaretDownIcon
                  size={14}
                  className={`shrink-0 text-ink-muted transition-transform ${setorAberto ? "rotate-180" : ""}`}
                  aria-hidden
                />
              </button>

              {/* grid 0fr->1fr anima a altura sem medir; a lista rola sozinha
                  se passar de max-h-56 */}
              <div
                className={`grid transition-[grid-template-rows] duration-300 ease-out motion-reduce:transition-none ${
                  setorAberto ? "grid-rows-[1fr]" : "grid-rows-[0fr]"
                }`}
              >
                <div className="overflow-hidden">
                  <div className="mt-3 max-h-56 space-y-2.5 overflow-y-auto pr-1">
                    {opcoesSetor.map((o) => (
                      <label
                        key={o.setor}
                        className="flex cursor-pointer items-center justify-between gap-2 text-sm"
                      >
                        <span className="flex min-w-0 items-center gap-2.5">
                          <input
                            type="checkbox"
                            checked={filtroSetor.includes(o.setor)}
                            onChange={() =>
                              alternar(filtroSetor, setFiltroSetor, o.setor)
                            }
                            className="shrink-0 accent-nvidia"
                          />
                          <span className="truncate">{o.setor}</span>
                        </span>
                        <span className="font-mono text-xs text-ink-muted">
                          {o.total}
                        </span>
                      </label>
                    ))}
                  </div>
                </div>
              </div>
            </div>
          )}

          {temFiltro && (
            <div className="border-t border-line p-5">
              <button
                onClick={limparFiltros}
                className="w-full rounded-lg border border-nvidia/70 px-4 py-2 text-sm font-medium text-ink transition-colors hover:border-nvidia hover:bg-nvidia/10 active:translate-y-px"
              >
                Limpar filtros
              </button>
            </div>
          )}

          {/* ── Pesos do score ────────────────────────────────────── */}
          <div className="border-t border-line p-5">
            <h3 className="text-sm font-medium">Pesos do score</h3>
            <p className="mt-1 text-xs text-ink-muted">
              Mova um slider e o ranking reordena na hora.
            </p>

            {/* presets: calibragens de um clique; o ativo acende verde */}
            <div className="mt-3 flex flex-wrap gap-2">
              {PRESETS.map((preset) => {
                const ativo = pesosIguais(pesos, preset.pesos);
                return (
                  <button
                    key={preset.nome}
                    onClick={() => setPesos(preset.pesos)}
                    aria-pressed={ativo}
                    className={`rounded-lg border px-3 py-1.5 text-xs font-medium transition-colors active:translate-y-px ${
                      ativo
                        ? "border-nvidia bg-nvidia/10 text-ink"
                        : "border-line text-ink-muted hover:border-nvidia hover:text-ink"
                    }`}
                  >
                    {preset.nome}
                  </button>
                );
              })}
            </div>

            {EIXOS.map((eixo) => (
              <div key={eixo.key} className="mt-5">
                <div className="flex items-baseline justify-between">
                  <label htmlFor={`peso-${eixo.key}`} className="text-sm">
                    {eixo.label}
                  </label>
                  <span className="font-mono text-xs text-nvidia">
                    {(pesos[eixo.key] ?? 0).toFixed(2)}
                  </span>
                </div>
                <input
                  id={`peso-${eixo.key}`}
                  type="range"
                  min={0}
                  max={1}
                  step={0.05}
                  value={pesos[eixo.key]}
                  onChange={(e) =>
                    setPesos({ ...pesos, [eixo.key]: Number(e.target.value) })
                  }
                  // preenchido verde até o valor (Chrome/WebKit não têm pseudo
                  // para o "progress"; o gradiente inline resolve nos dois)
                  style={{
                    background: `linear-gradient(to right, var(--color-nvidia) ${(pesos[eixo.key] ?? 0) * 100}%, var(--surface-2) ${(pesos[eixo.key] ?? 0) * 100}%)`,
                  }}
                  className="mt-2 w-full"
                />
              </div>
            ))}

            {!pesosIguais(pesos, PESOS_PADRAO) && (
              <button
                onClick={() => setPesos(PESOS_PADRAO)}
                className="mt-5 w-full rounded-lg border border-nvidia/70 px-4 py-2 text-sm font-medium text-ink transition-colors hover:border-nvidia hover:bg-nvidia/10 active:translate-y-px"
              >
                Restaurar padrão
              </button>
            )}
          </div>
        </aside>

        <section>
          {carregando ? (
            <SkeletonLista />
          ) : erroApi || empresas.length === 0 ? (
            <div className="rounded-xl border border-line bg-[#0C0C0C] px-6 py-10 text-center">
              <TerminalWindowIcon
                size={28}
                className="mx-auto text-ink-muted"
                aria-hidden
              />
              <p className="mt-3 text-sm text-ink-muted">
                {erroApi
                  ? "A API está fora do ar. Suba o backend:"
                  : "Nenhuma empresa analisada ainda. Suba o backend e analise a primeira:"}
              </p>
              <code className="mt-3 inline-block rounded-lg bg-surface-2 px-3 py-1.5 font-mono text-xs text-ink">
                uvicorn app.api:app --reload
              </code>
              <div className="mt-4">
                <button
                  onClick={carregarEmpresas}
                  className="rounded-lg border border-nvidia/70 px-4 py-2 text-sm font-medium text-ink transition-colors hover:border-nvidia hover:bg-nvidia/10 active:translate-y-px"
                >
                  Tentar de novo
                </button>
              </div>
            </div>
          ) : visiveis.length === 0 ? (
            // os filtros zeraram a lista (a API está de pé; é só refinamento)
            <div className="rounded-xl border border-line bg-[#0C0C0C] px-6 py-10 text-center">
              <p className="text-sm text-ink-muted">
                Nenhuma empresa com esses filtros.
              </p>
              <button
                onClick={limparFiltros}
                className="mt-4 rounded-lg border border-nvidia/70 px-4 py-2 text-sm font-medium text-ink transition-colors hover:border-nvidia hover:bg-nvidia/10 active:translate-y-px"
              >
                Limpar filtros
              </button>
            </div>
          ) : (
            <>
              <div className="mb-2 flex flex-wrap items-center justify-between gap-2 text-xs text-ink-muted">
                {/* dica de descobribilidade: a caixa de cada linha é para
                    comparar (antes só havia o tooltip) */}
                <span>Marque as caixas para comparar até 3 empresas.</span>
                {temFiltro && (
                  <span>
                    <span className="font-mono text-ink">{visiveis.length}</span>{" "}
                    de{" "}
                    <span className="font-mono text-ink">{empresas.length}</span>{" "}
                    empresas
                  </span>
                )}
              </div>
            <ul className="divide-y divide-line rounded-xl border border-line bg-[#0C0C0C]">
              {visiveis.map((empresa, i) => {
                const s = compor(empresa.notas, pesos);
                return (
                  // layout: quando o sort muda, o Motion anima a linha até a
                  // nova posição (FLIP, só transform) em vez de teleportar;
                  // é o feedback visual do re-rank ao vivo


                  <motion.li
                    key={empresa.nome}
                    layout={!reduce}
                    transition={{ type: "spring", duration: 0.35, bounce: 0 }}
                  >
                    {/* hover na LINHA toda (não só no botão), senão a coluna
                        do checkbox fica escura e a cor sai bicolor */}
                    <div className="flex items-stretch transition-colors hover:bg-surface-2">
                      {/* selecionar p/ comparar: separado do botão da linha,
                          senão marcar o checkbox abriria o modal de detalhe */}
                      <label
                        className="flex cursor-pointer items-center pl-5 pr-1"
                        title={
                          !empresa.notas
                            ? "Sem notas: não dá para comparar"
                            : comparar.length >= 3 &&
                                !comparar.includes(empresa.nome)
                              ? "Máximo de 3 empresas"
                              : `Comparar ${empresa.nome}`
                        }
                      >
                        <input
                          type="checkbox"
                          className="accent-nvidia disabled:cursor-not-allowed disabled:opacity-30"
                          checked={comparar.includes(empresa.nome)}
                          disabled={
                            !empresa.notas ||
                            (comparar.length >= 3 &&
                              !comparar.includes(empresa.nome))
                          }
                          onChange={() => alternarComparar(empresa.nome)}
                          aria-label={`Selecionar ${empresa.nome} para comparar`}
                        />
                      </label>
                    <button
                      onClick={() => setSelecionada(empresa.nome)}
                      className="flex min-w-0 flex-1 items-center gap-4 px-4 py-3.5 text-left"
                    >
                      <span className="w-6 font-mono text-sm text-ink-muted">
                        {i + 1}
                      </span>
                      <span className="min-w-0 flex-1">
                        <span className="flex items-center gap-2">
                          <span className="truncate font-medium">
                            {empresa.nome}
                          </span>
                          {ehNova(empresa) && (
                            // selo de estado: análise entrou há < HORAS_NOVA
                            <span className="shrink-0 rounded-full border border-nvidia/40 bg-nvidia/15 px-2 py-0.5 text-[11px] font-medium text-nvidia">
                              nova
                            </span>
                          )}
                        </span>
                        {empresa.setor && (
                          <span className="block truncate text-xs text-ink-muted">
                            {empresa.setor}
                          </span>
                        )}
                      </span>
                      <Badge classificacao={empresa.classificacao} />
                      <span className="w-12 text-right font-mono font-semibold text-nvidia">
                        {s === null ? (
                          <span className="text-ink-muted">n/d</span>
                        ) : (
                          s.toFixed(1)
                        )}
                      </span>
                    </button>
                    </div>
                  </motion.li>
                );
              })}
            </ul>
            </>
          )}
        </section>
      </div>

      {/* ── Barra de comparação: aparece com 1+ seleção ───────────── */}
      <AnimatePresence>
        {comparar.length > 0 && !comparadorAberto && (
          <motion.div
            key="barra-comparar"
            initial={reduce ? false : { y: 24, opacity: 0 }}
            animate={{ y: 0, opacity: 1 }}
            exit={reduce ? undefined : { y: 24, opacity: 0 }}
            transition={{ type: "spring", duration: 0.3, bounce: 0 }}
            style={{ x: "-50%" }}
            className="fixed bottom-6 left-1/2 z-40 flex max-w-[calc(100vw-2rem)] flex-wrap items-center gap-3 rounded-xl border border-line bg-[#0C0C0C] px-4 py-3"
          >
            <span className="text-sm text-ink-muted">
              <span className="font-mono text-ink">{comparar.length}</span> de 3
              selecionadas
            </span>
            <button
              onClick={() => setComparar([])}
              className="rounded-lg border border-nvidia/70 px-3 py-1.5 text-sm font-medium text-ink transition-colors hover:border-nvidia hover:bg-nvidia/10 active:translate-y-px"
            >
              Limpar
            </button>
            <button
              onClick={() => setComparadorAberto(true)}
              disabled={empresasComparar.length < 2}
              title={
                empresasComparar.length < 2
                  ? "Selecione pelo menos 2 empresas"
                  : undefined
              }
              className="rounded-lg bg-nvidia px-4 py-1.5 text-sm font-semibold text-black transition-colors hover:bg-nvidia-bright active:translate-y-px disabled:cursor-not-allowed disabled:opacity-60"
            >
              Comparar ({empresasComparar.length})
            </button>
          </motion.div>
        )}
      </AnimatePresence>

      {/* ── Modal comparador: colunas + gráfico de radar ──────────── */}
      <AnimatePresence>
        {comparadorAberto && empresasComparar.length >= 2 && (
          <motion.div
            key="backdrop-comparar"
            initial={reduce ? false : { opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={reduce ? undefined : { opacity: 0 }}
            transition={{ duration: 0.15 }}
            className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4 backdrop-blur-sm"
            onClick={() => setComparadorAberto(false)}
          >
            <motion.div
              key="card-comparar"
              role="dialog"
              aria-modal="true"
              aria-label="Comparar empresas"
              initial={reduce ? false : { opacity: 0, scale: 0.96, y: 8 }}
              animate={{ opacity: 1, scale: 1, y: 0 }}
              exit={reduce ? undefined : { opacity: 0, scale: 0.98 }}
              transition={{ type: "spring", duration: 0.3, bounce: 0 }}
              onClick={(e) => e.stopPropagation()}
              className="max-h-[88vh] w-full max-w-3xl overflow-y-auto rounded-xl border border-line bg-[#0C0C0C] p-6"
            >
              <div className="flex items-start justify-between gap-4">
                <h2 className="text-xl font-bold tracking-tight">
                  Comparar empresas
                </h2>
                <button
                  onClick={() => setComparadorAberto(false)}
                  autoFocus
                  aria-label="Fechar comparador"
                  className="rounded-lg border border-nvidia/70 p-2 text-ink transition-colors hover:border-nvidia hover:bg-nvidia/10 active:translate-y-px"
                >
                  <XIcon size={16} aria-hidden />
                </button>
              </div>

              <div className="mt-4">
                <GraficoRadar
                  series={empresasComparar.map((e, i) => ({
                    nome: e.nome,
                    cor: CORES_SERIES[i],
                    notas: e.notas!,
                  }))}
                />
              </div>

              {/* colunas lado a lado: também são a "visão tabela" dos dados */}
              <div
                className={`mt-6 grid gap-4 ${
                  empresasComparar.length === 3
                    ? "sm:grid-cols-3"
                    : "sm:grid-cols-2"
                }`}
              >
                {empresasComparar.map((e, i) => {
                  const s = compor(e.notas, pesos);
                  return (
                    <div
                      key={e.nome}
                      className="rounded-lg border border-line p-4"
                    >
                      <p className="flex items-center gap-2 font-medium">
                        <span
                          className="h-2.5 w-2.5 shrink-0 rounded-sm"
                          style={{ backgroundColor: CORES_SERIES[i] }}
                          aria-hidden
                        />
                        <span className="truncate">{e.nome}</span>
                      </p>
                      <p className="mt-2">
                        <Badge classificacao={e.classificacao} />
                      </p>
                      <p className="mt-3 font-mono text-2xl font-semibold text-nvidia">
                        {s === null ? "n/d" : s.toFixed(1)}
                      </p>
                      <p className="text-xs text-ink-muted">score composto</p>
                      <ul className="mt-3 space-y-1.5 border-t border-line pt-3">
                        {EIXOS.map((eixo) => (
                          <li
                            key={eixo.key}
                            className="flex items-center justify-between text-sm"
                          >
                            <span className="text-ink-muted">{eixo.label}</span>
                            <span className="font-mono">
                              {e.notas?.[eixo.key] ?? "n/d"}
                            </span>
                          </li>
                        ))}
                      </ul>
                    </div>
                  );
                })}
              </div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* ── Modal de detalhe: notas + briefing ────────────────────── */}
      <AnimatePresence>
        {empresaSelecionada && (
          <motion.div
            key="backdrop"
            initial={reduce ? false : { opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={reduce ? undefined : { opacity: 0 }}
            transition={{ duration: 0.15 }}
            className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4 backdrop-blur-sm"
            onClick={() => setSelecionada(null)}
          >
            <motion.div
              key="card"
              role="dialog"
              aria-modal="true"
              aria-label={`Detalhe de ${empresaSelecionada.nome}`}
              initial={reduce ? false : { opacity: 0, scale: 0.96, y: 8 }}
              animate={{ opacity: 1, scale: 1, y: 0 }}
              exit={reduce ? undefined : { opacity: 0, scale: 0.98 }}
              transition={{ type: "spring", duration: 0.3, bounce: 0 }}
              onClick={(e) => e.stopPropagation()} // clique dentro não fecha
              className="max-h-[85vh] w-full max-w-2xl overflow-y-auto rounded-xl border border-line bg-[#0C0C0C] p-6"
            >
              <div className="flex items-start justify-between gap-4">
                <div>
                  <h2 className="text-xl font-bold tracking-tight">
                    {empresaSelecionada.nome}
                  </h2>
                  <p className="mt-1 flex items-center gap-2 text-sm text-ink-muted">
                    {empresaSelecionada.setor ?? "setor n/d"}
                    <Badge classificacao={empresaSelecionada.classificacao} />
                  </p>
                </div>
                <div className="flex shrink-0 items-center gap-2">
                  {/* o modal é a espiada rápida; a página é a leitura completa,
                      com URL própria para compartilhar */}
                  <Link
                    href={`/radar/${encodeURIComponent(empresaSelecionada.nome)}`}
                    className="inline-flex items-center gap-1.5 rounded-lg border border-nvidia/70 px-3 py-2 text-sm font-medium text-ink transition-colors hover:border-nvidia hover:bg-nvidia/10 active:translate-y-px"
                  >
                    <ArrowSquareOutIcon size={15} className="text-nvidia" aria-hidden />
                    Página completa
                  </Link>
                  <button
                    onClick={() => setSelecionada(null)}
                    autoFocus
                    aria-label="Fechar detalhe"
                    className="rounded-lg border border-nvidia/70 p-2 text-ink transition-colors hover:border-nvidia hover:bg-nvidia/10 active:translate-y-px"
                  >
                    <XIcon size={16} aria-hidden />
                  </button>
                </div>
              </div>

              {/* espiada rápida: só as tecnologias (nomes) e a conclusão.
                  Notas, justificativas e o briefing inteiro ficam na página. */}
              <div className="mt-5 border-t border-line pt-5">
                {detalhe === null ? (
                  <div className="space-y-2">
                    {[24, 20, 16].map((w) => (
                      <div
                        key={w}
                        className="h-3 animate-pulse rounded bg-surface-2 motion-reduce:animate-none"
                        style={{ width: `${w * 4}%` }}
                      />
                    ))}
                  </div>
                ) : (
                  (() => {
                    const tecs = detalhe.recomendacao?.tecnologias ?? [];
                    const conclusao = extrairConclusao(detalhe.briefing);
                    const proximaAcao = detalhe.recomendacao?.proxima_acao;
                    if (!tecs.length && !conclusao && !proximaAcao) {
                      return (
                        <p className="text-sm text-ink-muted">
                          Sem recomendação registrada para esta empresa
                          (classificadas como non-ai encerram antes dessa etapa).
                        </p>
                      );
                    }
                    return (
                      <>
                        {tecs.length > 0 && (
                          <div>
                            <h3 className="font-semibold">
                              Tecnologias NVIDIA recomendadas
                            </h3>
                            <div className="mt-2 flex flex-wrap gap-2">
                              {tecs.map((t) => (
                                <span
                                  key={t}
                                  className="rounded-full border border-nvidia/50 px-3 py-1 text-sm text-nvidia"
                                >
                                  {t}
                                </span>
                              ))}
                            </div>
                          </div>
                        )}
                        {conclusao ? (
                          <div className={tecs.length > 0 ? "mt-5" : ""}>
                            <h3 className="font-semibold">Conclusão</h3>
                            <div className="prose prose-invert prose-sm mt-2 max-w-none">
                              <ReactMarkdown remarkPlugins={[remarkGfm]}>
                                {conclusao}
                              </ReactMarkdown>
                            </div>
                          </div>
                        ) : proximaAcao ? (
                          <div className={tecs.length > 0 ? "mt-5" : ""}>
                            <h3 className="font-semibold">Próxima ação</h3>
                            <p className="mt-2 text-sm leading-relaxed">
                              {proximaAcao}
                            </p>
                          </div>
                        ) : null}
                      </>
                    );
                  })()
                )}
              </div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </main>
  );
}

// O Next exige um limite de <Suspense> em volta de quem chama useSearchParams:
// no primeiro render o hook "suspende" e o fallback é mostrado no lugar.
export default function RadarPage() {
  return (
    <Suspense fallback={null}>
      <RadarApp />
    </Suspense>
  );
}
