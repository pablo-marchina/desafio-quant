"use client";

// Aba Descoberta: fecha o ciclo "encontrar -> analisar -> rankear" na UI.
// DESCOBRIR acha nomes + descrições curtas (busca web + LLM, POST /descobrir,
// que também grava o tema no histórico); o ANALISAR de cada item roda o
// pipeline completo (POST /analisar). O histórico (GET /descobertas) permite
// reabrir uma pesquisa antiga sem refazer busca + LLM.

import { useState, useEffect, useRef } from "react";
import Link from "next/link";
import {
  ArrowSquareOutIcon,
  ClockCounterClockwiseIcon,
  CompassIcon,
  TerminalWindowIcon,
} from "@phosphor-icons/react";
import TabsRadar from "../TabsRadar";
import { useAnalise } from "../AnaliseProvider";

type StatusItem = "novo" | "analisando" | "analisada";
type ItemDescoberto = { nome: string; descricao: string; status: StatusItem };
type RegistroHistorico = {
  id: number;
  tema: string;
  empresas: { nome: string; descricao?: string }[];
  criado_em: string | null;
};

const API = process.env.NEXT_PUBLIC_API_URL;

export default function DescobertaPage() {
  const [tema, setTema] = useState("");
  const [descobrindo, setDescobrindo] = useState(false);
  const [buscou, setBuscou] = useState(false); // já rodou/abriu alguma pesquisa?
  const [erroApi, setErroApi] = useState(false);
  const [itens, setItens] = useState<ItemDescoberto[]>([]);
  const [historico, setHistorico] = useState<RegistroHistorico[]>([]);
  const [analisandoTodas, setAnalisandoTodas] = useState(false);
  // ref (não state) para o loop do "Analisar todas" enxergar o pedido de
  // parada na hora, sem depender de re-render
  const pararFilaRef = useRef(false);

  // progresso ao vivo: vem do CONTEXTO (AnaliseProvider, no layout), então
  // a análise sobrevive à troca de abas; o modal/mini-barra são do provider
  const { progresso, analisar: rodarAnalise, fechar: fecharProgresso } =
    useAnalise();
  const emAnalise = progresso.aberto && !progresso.done;

  const carregarHistorico = () => {
    fetch(`${API}/descobertas`)
      .then((res) => res.json())
      .then(setHistorico)
      .catch(() => {}); // histórico é acessório; sem ele a aba segue útil
  };

  useEffect(() => {
    carregarHistorico();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // cruza uma lista {nome, descricao} com quem JÁ está no banco
  const montarItens = async (
    empresas: { nome: string; descricao?: string }[]
  ): Promise<ItemDescoberto[]> => {
    const res = await fetch(`${API}/empresas`);
    const existentes = new Set(
      ((await res.json()) as { nome: string }[]).map((e) =>
        e.nome.trim().toLowerCase()
      )
    );
    return empresas.map((e) => ({
      nome: e.nome,
      descricao: e.descricao ?? "",
      status: existentes.has(e.nome.trim().toLowerCase())
        ? "analisada"
        : "novo",
    }));
  };

  const descobrir = async () => {
    if (!tema.trim() || descobrindo) return;
    setDescobrindo(true);
    setErroApi(false);
    try {
      const res = await fetch(`${API}/descobrir`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ tema }),
      });
      if (!res.ok) throw new Error();
      const { empresas } = (await res.json()) as {
        empresas: { nome: string; descricao?: string }[];
      };
      setItens(await montarItens(empresas));
      setBuscou(true);
      carregarHistorico(); // a pesquisa recém-feita entra no histórico
    } catch {
      setErroApi(true);
    } finally {
      setDescobrindo(false);
    }
  };

  // reabre uma pesquisa do histórico sem refazer busca + LLM
  const abrirHistorico = async (registro: RegistroHistorico) => {
    // uma análise única (minimizada, rodando no provider) NÃO impede trocar de
    // pesquisa; só bloqueamos durante uma descoberta em curso ou a fila "todas"
    if (descobrindo || analisandoTodas) return;
    setErroApi(false);
    setTema(registro.tema);
    try {
      setItens(await montarItens(registro.empresas));
      setBuscou(true);
    } catch {
      setErroApi(true);
    }
  };

  const trocarStatus = (nome: string, status: StatusItem) =>
    setItens((atual) =>
      atual.map((i) => (i.nome === nome ? { ...i, status } : i))
    );

  // analisa UMA empresa via streaming (o modal mostra os agentes ao vivo);
  // rotulo opcional é o contador do "Analisar todas" ("2 de 5: Alice")
  const analisarItem = async (nome: string, rotulo?: string) => {
    trocarStatus(nome, "analisando");
    const resultado = await rodarAnalise(nome, rotulo);
    if (resultado.erro) {
      trocarStatus(nome, "novo"); // volta ao estado inicial para tentar de novo
      throw new Error("analise falhou"); // o Analisar todas para no erro
    }
    trocarStatus(nome, "analisada");
  };

  // roda o pipeline em SEQUÊNCIA (não em paralelo: cada análise já é pesada
  // para o backend); para na primeira falha
  const analisarTodas = async () => {
    if (analisandoTodas || emAnalise) return;
    pararFilaRef.current = false;
    setAnalisandoTodas(true);
    const fila = itens.filter((i) => i.status === "novo");
    try {
      for (const [indice, item] of fila.entries()) {
        if (pararFilaRef.current) break; // parada pedida: encerra a fila
        await analisarItem(
          item.nome,
          `${indice + 1} de ${fila.length}: ${item.nome}`
        );
      }
      fecharProgresso(); // fila concluída (ou parada): fecha o modal
    } catch {
      // parou na primeira falha; o modal fica aberto mostrando o erro
    } finally {
      setAnalisandoTodas(false);
    }
  };

  const novos = itens.filter((i) => i.status === "novo").length;
  // estimativa honesta: o pipeline completo leva ~3 min por empresa
  const minutosEstimados = novos * 3;
  const analisandoAlgum = itens.some((i) => i.status === "analisando");

  // histórico sem temas repetidos: a API vem do mais recente ao mais antigo,
  // então a PRIMEIRA ocorrência de cada tema (case-insensitive) é a mais nova
  const historicoUnico = historico.filter((registro, i) => {
    const chave = registro.tema.trim().toLowerCase();
    return historico.findIndex((r) => r.tema.trim().toLowerCase() === chave) === i;
  });

  return (
    <main className="mx-auto w-full max-w-[1400px] px-6 py-8">
      <TabsRadar />

      {/* ── Tema + Descobrir ──────────────────────────────────────── */}
      <div className="mt-8 flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Descoberta</h1>
          <p className="mt-1 text-sm text-ink-muted">
            Do tema aos nomes: a busca encontra startups; o Analisar roda o
            pipeline completo.
          </p>
        </div>

        <form
          onSubmit={(e) => {
            e.preventDefault();
            descobrir();
          }}
          className="flex items-center gap-2"
        >
          <input
            type="text"
            placeholder="Tema, ex.: IA em saúde"
            aria-label="Tema da descoberta"
            value={tema}
            onChange={(e) => setTema(e.target.value)}
            className="w-64 rounded-lg border border-line bg-[#0C0C0C] px-3 py-2 text-sm text-ink outline-none transition-colors placeholder:text-ink-muted/70 focus:border-nvidia/60 sm:w-80"
          />
          <button
            type="submit"
            disabled={descobrindo}
            className="rounded-lg bg-nvidia px-4 py-2 text-sm font-semibold text-black transition-colors hover:bg-nvidia-bright active:translate-y-px disabled:cursor-not-allowed disabled:opacity-60"
          >
            {descobrindo ? "Descobrindo..." : "Descobrir"}
          </button>
        </form>
      </div>
      {descobrindo && (
        <p className="mt-2 text-right text-xs text-ink-muted">
          Buscando e lendo listas na web; isso pode levar um tempo.
        </p>
      )}

      {/* ── Histórico de pesquisas ────────────────────────────────── */}
      {historicoUnico.length > 0 && (
        <div className="mt-6 flex flex-wrap items-center gap-2">
          <span className="flex items-center gap-1.5 text-xs text-ink-muted">
            <ClockCounterClockwiseIcon size={14} aria-hidden />
            Pesquisas anteriores:
          </span>
          {historicoUnico.map((registro) => (
            <button
              key={registro.id}
              onClick={() => abrirHistorico(registro)}
              title={
                registro.criado_em
                  ? new Date(
                      registro.criado_em.includes("+") ||
                      registro.criado_em.endsWith("Z")
                        ? registro.criado_em
                        : registro.criado_em + "Z"
                    ).toLocaleString("pt-BR")
                  : undefined
              }
              className="rounded-full border border-line px-3 py-1 text-xs text-ink-muted transition-colors hover:border-nvidia hover:text-ink active:translate-y-px"
            >
              {registro.tema}{" "}
              <span className="font-mono">({registro.empresas.length})</span>
            </button>
          ))}
        </div>
      )}

      {/* ── Resultado ─────────────────────────────────────────────── */}
      <div className="mt-8">
        {erroApi ? (
          <div className="rounded-xl border border-line bg-[#0C0C0C] px-6 py-10 text-center">
            <TerminalWindowIcon
              size={28}
              className="mx-auto text-ink-muted"
              aria-hidden
            />
            <p className="mt-3 text-sm text-ink-muted">
              A API está fora do ar (ou a análise falhou). Confira o backend:
            </p>
            <code className="mt-3 inline-block rounded-lg bg-surface-2 px-3 py-1.5 font-mono text-xs text-ink">
              uvicorn app.api:app --reload
            </code>
          </div>
        ) : descobrindo ? (
          // skeleton com a forma dos cards que vão chegar
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {Array.from({ length: 6 }).map((_, i) => (
              <div
                key={i}
                className="animate-pulse rounded-xl border border-line bg-[#0C0C0C] p-5 motion-reduce:animate-none"
              >
                <div className="h-4 w-32 rounded bg-surface-2" />
                <div className="mt-3 h-3 w-full rounded bg-surface-2" />
                <div className="mt-1.5 h-3 w-2/3 rounded bg-surface-2" />
                <div className="mt-4 h-8 w-24 rounded-lg bg-surface-2" />
              </div>
            ))}
          </div>
        ) : !buscou ? (
          // estado inicial: explica o que a aba faz
          <div className="rounded-xl border border-line bg-[#0C0C0C] px-6 py-12 text-center">
            <CompassIcon size={32} className="mx-auto text-nvidia" aria-hidden />
            <h2 className="mt-4 font-semibold">Descubra startups por tema</h2>
            <p className="mx-auto mt-2 max-w-md text-sm text-ink-muted">
              Digite um tema (ex.: "startups brasileiras de IA em saúde") e o
              pipeline busca listas e notícias na web e extrai nomes com uma
              breve descrição. Depois, analise as que interessarem para
              entrarem no ranking.
            </p>
          </div>
        ) : itens.length === 0 ? (
          <div className="rounded-xl border border-line bg-[#0C0C0C] px-6 py-10 text-center">
            <p className="text-sm text-ink-muted">
              Nenhum nome encontrado para esse tema. Tente um tema mais amplo,
              como "IA em agro" ou "fintechs de IA".
            </p>
          </div>
        ) : (
          <>
            {novos >= 2 && (
              <div className="mb-4 flex flex-wrap items-center justify-between gap-4">
                <p className="text-sm text-ink-muted">
                  <span className="font-mono text-ink">{novos}</span> ainda fora
                  do radar
                  <span className="text-ink-muted/70">
                    {" "}
                    (~{minutosEstimados} min no total)
                  </span>
                </p>
                {analisandoTodas ? (
                  // durante a fila o botão vira "Parar": encerra depois que a
                  // empresa atual terminar (não corta a análise em andamento)
                  <button
                    onClick={() => {
                      pararFilaRef.current = true;
                    }}
                    className="rounded-lg border border-nvidia/70 px-4 py-2 text-sm font-medium text-ink transition-colors hover:border-nvidia hover:bg-nvidia/10 active:translate-y-px"
                  >
                    Parar após a atual
                  </button>
                ) : (
                  <button
                    onClick={analisarTodas}
                    disabled={emAnalise}
                    className="rounded-lg border border-nvidia/70 px-4 py-2 text-sm font-medium text-ink transition-colors hover:border-nvidia hover:bg-nvidia/10 active:translate-y-px disabled:cursor-not-allowed disabled:opacity-60"
                  >
                    Analisar todas ({novos})
                  </button>
                )}
              </div>
            )}

            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
              {itens.map((item) => (
                <div
                  key={item.nome}
                  className="flex flex-col justify-between gap-4 rounded-xl border border-line bg-[#0C0C0C] p-5"
                >
                  <div>
                    <div className="flex items-start justify-between gap-3">
                      <h3 className="font-medium">{item.nome}</h3>
                      {item.status === "analisada" && (
                        <span className="shrink-0 rounded-full border border-nvidia/50 px-2.5 py-0.5 text-xs text-nvidia">
                          já no radar
                        </span>
                      )}
                    </div>
                    {item.descricao && (
                      <p className="mt-2 text-sm leading-relaxed text-ink-muted">
                        {item.descricao}
                      </p>
                    )}
                  </div>

                  {item.status === "analisada" ? (
                    <Link
                      href={`/radar/${encodeURIComponent(item.nome)}`}
                      className="inline-flex w-fit items-center gap-1.5 rounded-lg border border-nvidia/70 px-3 py-2 text-sm font-medium text-ink transition-colors hover:border-nvidia hover:bg-nvidia/10 active:translate-y-px"
                    >
                      <ArrowSquareOutIcon
                        size={15}
                        className="text-nvidia"
                        aria-hidden
                      />
                      Ver no radar
                    </Link>
                  ) : (
                    <button
                      onClick={() => analisarItem(item.nome).catch(() => {})}
                      disabled={
                        item.status === "analisando" ||
                        analisandoTodas ||
                        emAnalise
                      }
                      className="w-fit rounded-lg border border-nvidia/70 px-3 py-2 text-sm font-medium text-ink transition-colors hover:border-nvidia hover:bg-nvidia/10 active:translate-y-px disabled:cursor-not-allowed disabled:opacity-60"
                    >
                      {item.status === "analisando"
                        ? "Analisando..."
                        : "Analisar"}
                    </button>
                  )}
                </div>
              ))}
            </div>
            {(analisandoAlgum || analisandoTodas) && (
              <p className="mt-4 text-xs text-ink-muted">
                O pipeline completo roda para cada análise; pode levar alguns
                minutos por empresa.
              </p>
            )}
          </>
        )}
      </div>

    </main>
  );
}
