import Link from "next/link";
import type { Metadata } from "next";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { ArrowLeftIcon } from "@phosphor-icons/react/dist/ssr";
import BaixarBriefing from "./BaixarBriefing";
import Colapsavel from "./Colapsavel";

// ── Rota dinâmica ────────────────────────────────────────────────────
// A pasta [nome] captura o segmento da URL: /radar/Tractian responde aqui
// com params.nome = "Tractian". No Next 16, `params` é uma Promise, por
// isso o `await params` logo no começo.
//
// Esta página é um SERVER COMPONENT (sem "use client"): o fetch roda no
// servidor, o HTML chega pronto e a URL é compartilhável. O header e a
// constelação vêm herdados de radar/layout.tsx, sem recriar nada.

// shape do GET /empresas/{nome} (ver app/api.py)
type Detalhe = {
  nome: string;
  setor: string | null;
  descricao: string | null;
  dados: {
    founders?: string[];
    funding?: string | null;
    clientes?: string[];
    tecnologias?: string[];
  } | null;
  classificacao: string | null;
  score: number | null;
  notas: Record<string, number> | null;
  recomendacao: {
    tecnologias?: string[];
    justificativa_tecnica?: string;
    justificativa_negocio?: string;
    prioridade?: string | null;
    complexidade?: string | null;
    proxima_acao?: string;
    evidencias?: string[];
  } | null;
  briefing: string | null;
  fontes: string[] | null;
};

const EIXOS = [
  { key: "ai_native", label: "AI-Native" },
  { key: "nvidia_fit", label: "NVIDIA-Fit" },
  { key: "tracao", label: "Tração" },
  { key: "time_ia", label: "Time de IA" },
];

// A tabela "Visão Geral" do briefing tem uma linha "| **Fontes** | urls |".
// Como já temos a seção Fontes dedicada e clicável no fim da página, tiramos
// essa linha antes de renderizar. A regex mira só a linha cujo PRIMEIRO campo
// é "Fontes" (com ou sem negrito), sem tocar na coluna "Fonte" da tabela de
// tecnologias, que é outra tabela.
function limparBriefing(briefing: string): string {
  return briefing.replace(
    /^[ \t]*\|[ \t]*\*{0,2}[ \t]*Fontes[ \t]*\*{0,2}[ \t]*\|[^\n]*\r?\n?/gim,
    ""
  );
}

type Busca =
  | { ok: true; detalhe: Detalhe }
  | { ok: false; motivo: "nao-encontrada" | "api-fora" };

async function getDetalhe(nome: string): Promise<Busca> {
  try {
    const res = await fetch(
      `${process.env.NEXT_PUBLIC_API_URL}/empresas/${encodeURIComponent(nome)}`,
      { next: { revalidate: 30 } }
    );
    if (res.status === 404) return { ok: false, motivo: "nao-encontrada" };
    if (!res.ok) return { ok: false, motivo: "api-fora" };
    return { ok: true, detalhe: await res.json() };
  } catch {
    return { ok: false, motivo: "api-fora" };
  }
}

function Badge({ classificacao }: { classificacao: string | null }) {
  const cores: Record<string, string> = {
    "ai-native": "text-nvidia border-nvidia/50",
    "ai-enabled": "text-amber border-amber/50",
  };
  const cor = cores[classificacao ?? ""] ?? "text-ink-muted border-line";
  return (
    <span className={`rounded-full border px-2 py-0.5 text-xs ${cor}`}>
      {classificacao ?? "n/d"}
    </span>
  );
}

const VOLTAR =
  "inline-flex items-center gap-1.5 rounded-lg border border-nvidia/70 px-4 py-2 text-sm font-medium text-ink transition-colors hover:border-nvidia hover:bg-nvidia/10 active:translate-y-px";

// o título da aba do navegador vira o nome da empresa
export async function generateMetadata({
  params,
}: {
  params: Promise<{ nome: string }>;
}): Promise<Metadata> {
  const { nome } = await params;
  return { title: `${decodeURIComponent(nome)} | Startup AI Radar` };
}

export default async function EmpresaPage({
  params,
}: {
  params: Promise<{ nome: string }>;
}) {
  const { nome } = await params;
  // a URL chega codificada ("Take%20Blip"); decodificamos para buscar e exibir
  const nomeEmpresa = decodeURIComponent(nome);
  const busca = await getDetalhe(nomeEmpresa);

  // estado gracioso: 404 da API ou API fora do ar, nunca erro 500
  if (!busca.ok) {
    return (
      <main className="mx-auto w-full max-w-3xl px-6 py-16">
        <div className="rounded-xl border border-line bg-[#0C0C0C] px-6 py-10 text-center">
          <h1 className="text-xl font-semibold tracking-tight">
            {busca.motivo === "nao-encontrada"
              ? `"${nomeEmpresa}" não está no radar`
              : "A API está fora do ar"}
          </h1>
          <p className="mt-2 text-sm text-ink-muted">
            {busca.motivo === "nao-encontrada"
              ? "Essa empresa ainda não foi analisada. Rode a análise pelo ranking."
              : "Suba o backend com: uvicorn app.api:app --reload"}
          </p>
          <div className="mt-6">
            <Link href="/radar" className={VOLTAR}>
              <ArrowLeftIcon size={16} className="text-nvidia" aria-hidden />
              Voltar ao ranking
            </Link>
          </div>
        </div>
      </main>
    );
  }

  const e = busca.detalhe;
  const rec = e.recomendacao;
  const dados = e.dados;

  return (
    <main className="mx-auto w-full max-w-[1100px] px-6 pb-16 pt-4">
      <Link href="/radar" className={VOLTAR}>
        <ArrowLeftIcon size={16} className="text-nvidia" aria-hidden />
        Voltar ao ranking
      </Link>

      {/* ── Cabeçalho ─────────────────────────────────────────────── */}
      <header className="mt-8 flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-3xl font-bold tracking-tight md:text-4xl">
            {e.nome}
          </h1>
          <p className="mt-2 flex items-center gap-2 text-sm text-ink-muted">
            {e.setor ?? "setor n/d"}
            <Badge classificacao={e.classificacao} />
          </p>
        </div>
        {e.score !== null && (
          <div className="text-right">
            <span className="block font-mono text-3xl font-semibold text-nvidia">
              {e.score.toFixed(1)}
            </span>
            <span className="text-xs text-ink-muted">score composto</span>
          </div>
        )}
      </header>

      {e.descricao && (
        <p className="mt-4 max-w-[75ch] text-ink-muted">{e.descricao}</p>
      )}

      {/* ── Notas + dados públicos | recomendação ─────────────────── */}
      <div className="mt-8 grid items-start gap-6 lg:grid-cols-[minmax(280px,1fr)_2fr]">
        <div className="space-y-6">
          {e.notas && (
            <section className="rounded-xl border border-line bg-[#0C0C0C] p-5">
              <h2 className="font-semibold">Notas</h2>
              <ul className="mt-3 divide-y divide-line">
                {EIXOS.map((eixo) => (
                  <li
                    key={eixo.key}
                    className="flex items-center justify-between py-2.5 text-sm"
                  >
                    <span className="text-ink-muted">{eixo.label}</span>
                    <span className="font-mono font-semibold text-nvidia">
                      {e.notas?.[eixo.key] ?? "n/d"}
                    </span>
                  </li>
                ))}
              </ul>
            </section>
          )}

          {dados &&
            ((dados.founders?.length ?? 0) > 0 ||
              dados.funding ||
              (dados.clientes?.length ?? 0) > 0 ||
              (dados.tecnologias?.length ?? 0) > 0) && (
              <section className="rounded-xl border border-line bg-[#0C0C0C] p-5">
                <h2 className="font-semibold">Dados públicos</h2>
                <dl className="mt-3 space-y-3 text-sm">
                  {(dados.founders?.length ?? 0) > 0 && (
                    <div>
                      <dt className="text-ink-muted">Founders</dt>
                      <dd className="mt-0.5">{dados.founders!.join(", ")}</dd>
                    </div>
                  )}
                  {dados.funding && (
                    <div>
                      <dt className="text-ink-muted">Funding</dt>
                      <dd className="mt-0.5">{dados.funding}</dd>
                    </div>
                  )}
                  {(dados.clientes?.length ?? 0) > 0 && (
                    <div>
                      <dt className="text-ink-muted">Clientes</dt>
                      <dd className="mt-0.5">{dados.clientes!.join(", ")}</dd>
                    </div>
                  )}
                  {(dados.tecnologias?.length ?? 0) > 0 && (
                    <div>
                      <dt className="text-ink-muted">Tecnologias</dt>
                      <dd className="mt-1 flex flex-wrap gap-1.5">
                        {dados.tecnologias!.map((t) => (
                          <span
                            key={t}
                            className="rounded-full border border-line px-2.5 py-0.5 text-xs"
                          >
                            {t}
                          </span>
                        ))}
                      </dd>
                    </div>
                  )}
                </dl>
              </section>
            )}
        </div>

        {rec && (
          <section className="rounded-xl border border-line bg-[#0C0C0C] p-6">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <h2 className="font-semibold">Recomendação NVIDIA</h2>
              <div className="flex gap-2 text-xs">
                {rec.prioridade && (
                  <span className="rounded-full border border-line px-2.5 py-0.5">
                    prioridade: {rec.prioridade}
                  </span>
                )}
                {rec.complexidade && (
                  <span className="rounded-full border border-line px-2.5 py-0.5">
                    complexidade: {rec.complexidade}
                  </span>
                )}
              </div>
            </div>

            {(rec.tecnologias?.length ?? 0) > 0 && (
              <div className="mt-4 flex flex-wrap gap-2">
                {rec.tecnologias!.map((t) => (
                  <span
                    key={t}
                    className="rounded-full border border-nvidia/50 px-3 py-1 text-sm text-nvidia"
                  >
                    {t}
                  </span>
                ))}
              </div>
            )}

            {rec.justificativa_tecnica && (
              <div className="mt-5">
                <Colapsavel
                  titulo="Justificativa técnica"
                  texto={rec.justificativa_tecnica}
                />
              </div>
            )}

            {rec.justificativa_negocio && (
              <div className="mt-3">
                <Colapsavel
                  titulo="Justificativa de negócio"
                  texto={rec.justificativa_negocio}
                />
              </div>
            )}

            {rec.proxima_acao && (
              <div className="mt-4 rounded-lg bg-surface-2 px-4 py-3">
                <h3 className="text-sm font-medium text-ink-muted">
                  Próxima ação
                </h3>
                <p className="mt-1 text-sm font-medium">{rec.proxima_acao}</p>
              </div>
            )}

            {(rec.evidencias?.length ?? 0) > 0 && (
              <div className="mt-5 border-t border-line pt-4">
                <h3 className="text-sm font-medium text-ink-muted">Evidências</h3>
                <ul className="mt-2 space-y-1.5">
                  {rec.evidencias!.map((ev) => (
                    <li key={ev} className="break-all text-xs text-ink-muted">
                      {/* evidência que é URL vira link, como na seção Fontes */}
                      {ev.startsWith("http") ? (
                        <a
                          href={ev}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="transition-colors hover:text-nvidia"
                        >
                          {ev}
                        </a>
                      ) : (
                        ev
                      )}
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </section>
        )}
      </div>

      {/* ── Briefing executivo ────────────────────────────────────── */}
      {e.briefing && (
        <section className="mt-6 rounded-xl border border-line bg-[#0C0C0C] p-6">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <h2 className="font-semibold">Briefing executivo</h2>
            {/* baixa o briefing CRU (com as fontes na Visão Geral), não a
                versão limpa que mostramos na tela */}
            <BaixarBriefing nome={e.nome} briefing={e.briefing} />
          </div>
          <div className="prose prose-invert prose-sm mt-4 max-w-none">
            <ReactMarkdown remarkPlugins={[remarkGfm]}>
              {limparBriefing(e.briefing)}
            </ReactMarkdown>
          </div>
        </section>
      )}

      {/* ── Fontes ────────────────────────────────────────────────── */}
      {(e.fontes?.length ?? 0) > 0 && (
        <section className="mt-6 rounded-xl border border-line bg-[#0C0C0C] p-6">
          <h2 className="font-semibold">Fontes</h2>
          <ul className="mt-3 space-y-1.5">
            {e.fontes!.map((fonte) => (
              <li key={fonte}>
                <a
                  href={fonte}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="break-all text-xs text-ink-muted transition-colors hover:text-nvidia"
                >
                  {fonte}
                </a>
              </li>
            ))}
          </ul>
        </section>
      )}
    </main>
  );
}
