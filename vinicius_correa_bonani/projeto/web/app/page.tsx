import Link from "next/link";
import {
  ArrowElbowDownRightIcon,
  ArrowRightIcon,
  ArrowUUpLeftIcon,
  CaretRightIcon,
  CheckCircleIcon,
  DatabaseIcon,
  FileTextIcon,
  GlobeIcon,
  MagnifyingGlassIcon,
  ScalesIcon,
  SealCheckIcon,
  TableIcon,
  TerminalWindowIcon,
  TreeStructureIcon,
} from "@phosphor-icons/react/dist/ssr";
import Navbar from "./components/Navbar";
import ConstellationBg from "./components/ConstellationBg";
import SearchBox from "./components/SearchBox";
import Reveal from "./components/Reveal";

// Mesmo shape que a API devolve em GET /empresas (ver app/api.py).
type Empresa = {
  nome: string;
  setor: string | null;
  classificacao: string | null;
  score: number | null;
};

// Server Component: esta função roda NO SERVIDOR, revalidando a cada 30s.
// Se a API estiver fora do ar, devolvemos null e a página mostra um
// empty state em vez de quebrar.
async function getEmpresas(): Promise<Empresa[] | null> {
  try {
    const res = await fetch(`${process.env.NEXT_PUBLIC_API_URL}/empresas`, {
      next: { revalidate: 30 },
    });
    if (!res.ok) return null;
    return await res.json();
  } catch {
    return null;
  }
}

function Badge({ classificacao }: { classificacao: string | null }) {
  if (!classificacao) return null;
  const cores: Record<string, string> = {
    "ai-native": "text-nvidia border-nvidia/50",
    "ai-enabled": "text-amber border-amber/50",
  };
  const cor = cores[classificacao] ?? "text-ink-muted border-line";
  return (
    <span className={`rounded-full border px-2 py-0.5 text-xs ${cor}`}>
      {classificacao}
    </span>
  );
}

// Os 8 nós reais do grafo (app/graph.py), na ordem em que rodam.
const AGENTES = [
  {
    icone: MagnifyingGlassIcon,
    nome: "Search Planner",
    papel: "Transforma a consulta em plano de busca: termos e fontes.",
  },
  {
    icone: GlobeIcon,
    nome: "Scraper",
    papel: "Coleta conteúdo público e guarda a fonte de cada trecho.",
  },
  {
    icone: TableIcon,
    nome: "Extractor",
    papel: "Preenche a ficha da empresa com structured output.",
  },
  {
    icone: SealCheckIcon,
    nome: "Evidence Validator",
    papel: "Confere cada afirmação contra as fontes e corta o que não tem lastro.",
  },
  {
    icone: TreeStructureIcon,
    nome: "Classifier",
    papel: "Aplica os 3 eixos AI-native, com few-shot e self-consistency.",
  },
  {
    icone: DatabaseIcon,
    nome: "NVIDIA RAG",
    papel: "Recupera contexto técnico da base NVIDIA no Qdrant.",
  },
  {
    icone: ScalesIcon,
    nome: "Recommendation",
    papel: "Cruza os gaps com o portfólio e pontua com um painel de juízes.",
  },
  {
    icone: FileTextIcon,
    nome: "Briefing",
    papel: "Redige o relatório executivo e o revisa contra as fontes.",
  },
];

// O que torna o grafo um grafo: o loop e o desvio condicional.
const REGRAS = [
  {
    icone: ArrowUUpLeftIcon,
    badge: "4 → 2",
    titulo: "Loop de evidência",
    texto:
      "Faltou lastro? O Validator devolve o fluxo ao Scraper, com teto de tentativas.",
  },
  {
    icone: ArrowElbowDownRightIcon,
    badge: "5 → fim",
    titulo: "Desvio non-ai",
    texto:
      "Sem sinal de IA no produto, o grafo encerra antes das etapas caras.",
  },
];

const FASES_RAG = [
  {
    titulo: "Ingestão offline",
    quando: "roda uma vez",
    passos: [
      "Documentos do portfólio NVIDIA, 18 URLs",
      "Chunking por seção, guardando a fonte",
      "Embeddings com Gemini",
      "Índice híbrido no Qdrant",
    ],
  },
  {
    titulo: "Consulta online",
    quando: "a cada pergunta",
    passos: [
      "Busca híbrida, vetorial e BM25, traz cerca de 50 candidatos",
      "Cohere Rerank reordena por precisão",
      "Top-5 vira contexto enxuto, com citações",
      "O LLM escreve recomendação e briefing",
    ],
  },
];

const STACK = [
  { logo: "python", nome: "Python 3.13", papel: "A linguagem de todo o backend." },
  { logo: "langgraph", nome: "LangGraph", papel: "Orquestra o grafo dos 8 agentes." },
  { logo: "fastapi", nome: "FastAPI", papel: "Expõe a análise como API REST." },
  { logo: "pydantic", nome: "Pydantic", papel: "Schemas do State e da extração." },
  { logo: "qdrant", nome: "Qdrant", papel: "Banco vetorial com busca híbrida." },
  { logo: "sqlite", nome: "SQLite", papel: "Banco relacional, portável a PostgreSQL." },
  { logo: "nextdotjs", nome: "Next.js 16", papel: "Este frontend, com App Router." },
  { logo: "tailwindcss", nome: "Tailwind v4", papel: "Estilo utilitário sobre tokens." },
];

const MODELOS = [
  { logo: "nvidia", rotulo: "LLM", valor: "NVIDIA NIM, com fallback Groq" },
  { logo: "googlegemini", rotulo: "Embeddings", valor: "Gemini embedding-001" },
  { logo: null, rotulo: "Rerank", valor: "Cohere rerank-v3.5" },
];

const EIXOS = [
  {
    label: "AI-Native",
    peso: "0.30",
    descricao: "A IA é o core do produto, com dado ou modelo próprio.",
  },
  {
    label: "NVIDIA-Fit",
    peso: "0.30",
    descricao: "Tamanho do gap que o portfólio NVIDIA resolve.",
  },
  {
    label: "Tração",
    peso: "0.20",
    descricao: "Clientes, receita e histórico de captação com VCs.",
  },
  {
    label: "Time de IA",
    peso: "0.20",
    descricao: "Senioridade técnica do time que constrói o modelo.",
  },
];

const ENTREGAVEIS = [
  "Pipeline de scraping multiplataforma",
  "Sistema multiagente em LangGraph",
  "RAG da base NVIDIA com reranking",
  "Motor de recomendação: score e briefing",
  "Interface web: esta página e o Radar",
  "Diferencial: pesos ajustáveis e avaliação do RAG",
];

export default async function Landing() {
  const empresas = await getEmpresas();
  const top = (empresas ?? [])
    .filter((e) => e.score !== null)
    .sort((a, b) => (b.score ?? 0) - (a.score ?? 0))
    .slice(0, 5);

  return (
    <>
      <Navbar />
      <ConstellationBg brilho={0.35} />

      {/* brilho verde radial no topo, atrás da constelação */}
      <div className="pointer-events-none fixed inset-0 -z-20 bg-[radial-gradient(55%_40%_at_50%_0%,rgba(118,185,0,0.14),transparent_70%)]" />

      <main className="mx-auto w-full max-w-[1400px] px-6">
        {/* ── Hero de tela cheia: só a tese + um CTA para o dashboard ── */}
        <section className="flex min-h-[calc(100dvh-4rem)] flex-col items-center justify-center text-center">
          <Reveal immediate>
            <p className="mb-5 text-xs font-semibold uppercase tracking-[0.22em] text-nvidia">
              Inteli Academy × NVIDIA
            </p>
          </Reveal>
          <Reveal immediate delay={0.05}>
            <h1 className="max-w-[16ch] text-balance text-5xl font-bold tracking-tight md:text-7xl">
              O radar das startups brasileiras de IA.
            </h1>
          </Reveal>
          <Reveal immediate delay={0.1}>
            <p className="mt-6 max-w-2xl text-balance text-lg leading-relaxed text-ink-muted">
              Inteligência de mercado para a gerência de Startups &amp; VCs da
              NVIDIA: um sistema multiagente mapeia, qualifica e prioriza cada
              empresa.
            </p>
          </Reveal>
          <Reveal immediate delay={0.15}>
            <Link
              href="/radar"
              className="mt-10 inline-block rounded-lg border border-nvidia/70 px-5 py-2.5 text-sm font-semibold text-ink transition-colors hover:border-nvidia hover:bg-nvidia/10 active:translate-y-px"
            >
              Abrir o Radar
            </Link>
          </Reveal>
        </section>

        {/* marcador do fim do hero: a Navbar observa este ponto e só ganha
            fundo quando ele passa por baixo dela (rolou além da 1ª tela) */}
        <div id="hero-end" className="h-px w-full" aria-hidden />

        {/* ── Busca ao lado do ranking; as duas colunas entram juntas ── */}
        <section id="ranking" className="grid scroll-mt-24 gap-12 pb-24 pt-8 md:grid-cols-2">
          <Reveal>
            <h2 className="text-2xl font-semibold tracking-tight">
              Analise uma startup
            </h2>
            <p className="mt-1 text-sm text-ink-muted">
              Digite um nome ou um tema; o pipeline roda e o resultado entra no
              ranking.
            </p>
            <div className="mt-6">
              <SearchBox />
            </div>
            <Link
              href="/radar"
              className="group mt-4 flex items-center justify-between gap-6 rounded-xl border border-line bg-[#0C0C0C] shadow-[inset_0_1px_0_rgba(255,255,255,0.06)] px-6 py-5 transition-colors hover:border-nvidia/50"
            >
              <div>
                <h3 className="font-semibold">Pesos ajustáveis, ranking ao vivo</h3>
                <p className="mt-1 text-sm text-ink-muted">
                  Mova os sliders do score e veja a prioridade se reordenar na
                  hora.
                </p>
              </div>
              <ArrowRightIcon
                size={22}
                className="shrink-0 text-nvidia transition-transform group-hover:translate-x-1"
                aria-hidden
              />
            </Link>
          </Reveal>

          <Reveal>
            <h2 className="text-2xl font-semibold tracking-tight">
              Ranking ao vivo
            </h2>
            <p className="mt-1 text-sm text-ink-muted">
              As startups já analisadas, ordenadas pelo score composto.
            </p>

            {top.length > 0 ? (
              <>
                <ul className="mt-6 divide-y divide-line rounded-xl border border-line bg-[#0C0C0C] shadow-[inset_0_1px_0_rgba(255,255,255,0.06)]">
                  {top.map((empresa, i) => (
                    <li key={empresa.nome}>
                      <Link
                        href="/radar"
                        className="flex items-center gap-4 px-5 py-3.5 transition-colors hover:bg-surface-2/60"
                      >
                        <span className="w-5 font-mono text-sm text-ink-muted">
                          {i + 1}
                        </span>
                        <span className="min-w-0 flex-1">
                          <span className="block truncate font-medium">
                            {empresa.nome}
                          </span>
                          {empresa.setor && (
                            <span className="block truncate text-xs text-ink-muted">
                              {empresa.setor}
                            </span>
                          )}
                        </span>
                        <Badge classificacao={empresa.classificacao} />
                        <span className="w-12 text-right font-mono font-semibold text-nvidia">
                          {empresa.score?.toFixed(1)}
                        </span>
                      </Link>
                    </li>
                  ))}
                </ul>
                <Link
                  href="/radar"
                  className="mt-4 inline-flex items-center gap-1.5 rounded-lg border border-nvidia/70 px-4 py-2 text-sm font-medium text-ink transition-colors hover:border-nvidia hover:bg-nvidia/10 active:translate-y-px"
                >
                  Ranking completo
                  <CaretRightIcon size={14} className="text-nvidia" aria-hidden />
                </Link>
              </>
            ) : (
              <div className="mt-6 rounded-xl border border-line bg-[#0C0C0C] shadow-[inset_0_1px_0_rgba(255,255,255,0.06)] px-6 py-8 text-center">
                <TerminalWindowIcon
                  size={28}
                  className="mx-auto text-ink-muted"
                  aria-hidden
                />
                <p className="mt-3 text-sm text-ink-muted">
                  A API está fora do ar. Suba o backend para ver o ranking:
                </p>
                <code className="mt-3 inline-block rounded-lg bg-surface-2 px-3 py-1.5 font-mono text-xs text-ink">
                  uvicorn app.api:app --reload
                </code>
              </div>
            )}
          </Reveal>
        </section>

        {/* ── Como funciona: grid de agentes + regras do fluxo ────── */}
        <section id="como-funciona" className="scroll-mt-24 border-t border-line pb-24 pt-16">
          <Reveal>
            <h2 className="text-2xl font-semibold tracking-tight">
              Como funciona
            </h2>
            <p className="mt-1 max-w-2xl text-sm text-ink-muted">
              Uma ficha única viaja pelo grafo: cada agente lê campos, preenche
              outros e devolve só o que mudou.
            </p>
          </Reveal>

          <div className="mt-8 grid gap-4 lg:grid-cols-3">
            <div className="grid gap-4 sm:grid-cols-2 lg:col-span-2">
              {AGENTES.map((agente, i) => (
                <Reveal key={agente.nome} delay={(i % 2) * 0.05}>
                  <div className="h-full rounded-xl border border-line bg-[#0C0C0C] shadow-[inset_0_1px_0_rgba(255,255,255,0.06)] p-5">
                    <div className="flex items-center justify-between">
                      <agente.icone size={22} className="text-nvidia" aria-hidden />
                      <span className="font-mono text-xs text-ink-muted">
                        {i + 1}
                      </span>
                    </div>
                    <h3 className="mt-3 font-medium">{agente.nome}</h3>
                    <p className="mt-1 text-sm text-ink-muted">{agente.papel}</p>
                  </div>
                </Reveal>
              ))}
            </div>

            <Reveal delay={0.1} className="h-full">
              <aside className="flex h-full flex-col gap-4">
                <h3 className="font-medium text-ink-muted">Regras do fluxo</h3>
                {REGRAS.map((regra) => (
                  <div
                    key={regra.titulo}
                    className="flex-1 rounded-xl border border-dashed border-line bg-[#0C0C0C] p-5 shadow-[inset_0_1px_0_rgba(255,255,255,0.06)]"
                  >
                    <div className="flex items-center justify-between">
                      <regra.icone size={22} className="text-ink-muted" aria-hidden />
                      <span className="font-mono text-xs font-semibold text-nvidia">
                        {regra.badge}
                      </span>
                    </div>
                    <h4 className="mt-3 font-medium">{regra.titulo}</h4>
                    <p className="mt-1 text-sm text-ink-muted">{regra.texto}</p>
                  </div>
                ))}
              </aside>
            </Reveal>
          </div>
        </section>

        {/* ── RAG em duas fases ───────────────────────────────────── */}
        <section className="border-t border-line pb-24 pt-16">
          <Reveal>
            <h2 className="text-2xl font-semibold tracking-tight">
              RAG da base NVIDIA, em duas fases
            </h2>
            <p className="mt-1 max-w-2xl text-sm text-ink-muted">
              Recall largo no primeiro estágio, precisão no segundo: a
              recomendação nunca inventa spec.
            </p>
          </Reveal>

          <div className="mt-8 grid gap-4 md:grid-cols-2">
            {FASES_RAG.map((fase, f) => (
              <Reveal key={fase.titulo} delay={f * 0.08}>
                <div className="h-full rounded-xl border border-line bg-[#0C0C0C] shadow-[inset_0_1px_0_rgba(255,255,255,0.06)] p-6">
                  <div className="flex items-baseline justify-between gap-3">
                    <h3 className="font-semibold">{fase.titulo}</h3>
                    <span className="font-mono text-xs text-ink-muted">
                      {fase.quando}
                    </span>
                  </div>
                  <ol className="mt-4 space-y-3">
                    {fase.passos.map((passo, i) => (
                      <li key={passo} className="flex items-start gap-3">
                        <span className="mt-0.5 font-mono text-xs text-nvidia">
                          {i + 1}
                        </span>
                        <span className="text-sm text-ink-muted">{passo}</span>
                      </li>
                    ))}
                  </ol>
                </div>
              </Reveal>
            ))}
          </div>
        </section>

        {/* ── Stack técnica ───────────────────────────────────────── */}
        <section id="stack" className="scroll-mt-24 border-t border-line pb-24 pt-16">
          <Reveal>
            <h2 className="text-2xl font-semibold tracking-tight">
              Stack técnica
            </h2>
            <p className="mt-1 max-w-2xl text-sm text-ink-muted">
              Os componentes reais do repositório, da coleta ao ranking.
            </p>
          </Reveal>

          <div className="mt-8 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            {STACK.map((item, i) => (
              <Reveal key={item.nome} delay={(i % 4) * 0.05}>
                <div className="h-full rounded-xl border border-line bg-[#0C0C0C] shadow-[inset_0_1px_0_rgba(255,255,255,0.06)] px-5 py-4">
                  <div className="flex items-center gap-3">
                    <img
                      src={`/logos/${item.logo}.svg`}
                      alt=""
                      className="h-5 w-5"
                    />
                    <h3 className="font-medium">{item.nome}</h3>
                  </div>
                  <p className="mt-2 text-sm text-ink-muted">{item.papel}</p>
                </div>
              </Reveal>
            ))}
          </div>

          <Reveal delay={0.1}>
            <h3 className="mt-10 font-medium text-ink-muted">Modelos de IA</h3>
            <div className="mt-4 grid grid-cols-1 gap-4 sm:grid-cols-3">
              {MODELOS.map((modelo) => (
                <div
                  key={modelo.rotulo}
                  className="flex h-full items-center gap-3 rounded-xl border border-line bg-[#0C0C0C] shadow-[inset_0_1px_0_rgba(255,255,255,0.06)] px-5 py-4"
                >
                  {modelo.logo && (
                    <img
                      src={`/logos/${modelo.logo}.svg`}
                      alt=""
                      className="h-5 w-5 shrink-0"
                    />
                  )}
                  <div className="min-w-0">
                    <span className="block font-mono text-xs uppercase text-ink-muted">
                      {modelo.rotulo}
                    </span>
                    <span className="block text-sm">{modelo.valor}</span>
                  </div>
                </div>
              ))}
            </div>
          </Reveal>
        </section>

        {/* ── Metodologia: o score composto ───────────────────────── */}
        <section id="metodologia" className="scroll-mt-24 border-t border-line pb-24 pt-16">
          <Reveal>
            <h2 className="text-2xl font-semibold tracking-tight">
              Score composto, pesos ajustáveis
            </h2>
            <p className="mt-1 max-w-2xl text-sm text-ink-muted">
              Quatro notas de 0 a 10 entram numa soma ponderada. Os pesos abaixo
              são o padrão e podem ser recalibrados ao vivo no Radar.
            </p>
          </Reveal>

          <div className="mt-8 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            {EIXOS.map((eixo, i) => (
              <Reveal key={eixo.label} delay={i * 0.05}>
                <div className="h-full rounded-xl border border-line bg-[#0C0C0C] shadow-[inset_0_1px_0_rgba(255,255,255,0.06)] px-5 py-4">
                  <div className="flex items-baseline justify-between">
                    <h3 className="font-medium">{eixo.label}</h3>
                    <span className="font-mono text-sm font-semibold text-nvidia">
                      {eixo.peso}
                    </span>
                  </div>
                  <p className="mt-2 text-sm text-ink-muted">{eixo.descricao}</p>
                </div>
              </Reveal>
            ))}
          </div>
        </section>

        {/* ── Entregáveis: fechamento do escopo ───────────────────── */}
        <section className="border-t border-line pb-24 pt-16">
          <Reveal>
            <h2 className="text-2xl font-semibold tracking-tight">
              O que o projeto entrega
            </h2>
            <p className="mt-1 max-w-2xl text-sm text-ink-muted">
              O escopo combinado com a NVIDIA, fechado de ponta a ponta.
            </p>
          </Reveal>
          <Reveal delay={0.08}>
            <ul className="mt-6 flex flex-wrap gap-3">
              {ENTREGAVEIS.map((item) => (
                <li
                  key={item}
                  className="flex items-center gap-2 rounded-full border border-line bg-[#0C0C0C] shadow-[inset_0_1px_0_rgba(255,255,255,0.06)] px-4 py-2 text-sm"
                >
                  <CheckCircleIcon
                    size={16}
                    weight="fill"
                    className="shrink-0 text-nvidia"
                    aria-hidden
                  />
                  {item}
                </li>
              ))}
            </ul>
          </Reveal>
        </section>
      </main>

      <footer className="border-t border-line">
        <div className="mx-auto flex max-w-[1400px] flex-wrap items-center justify-between gap-4 px-6 py-6 text-sm text-ink-muted">
          <div className="flex items-center gap-2.5">
            <img src="/nvidia-logo.png" alt="NVIDIA" className="h-4 w-auto" />
            <span>Startup AI Radar</span>
          </div>
          <span>Inteli Academy × NVIDIA</span>
        </div>
      </footer>
    </>
  );
}
