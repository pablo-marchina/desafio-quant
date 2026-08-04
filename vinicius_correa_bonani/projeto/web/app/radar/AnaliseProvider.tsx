"use client";

// Provider do progresso de análise, montado no LAYOUT do radar.
//
// Por que existe: quando o hook vivia dentro de cada página, navegar entre
// Ranking e Descoberta DESMONTAVA a página, o cleanup fechava o SSE e o
// backend abortava o grafo (a análise "sumia"). O layout sobrevive à
// navegação entre as abas, então o hook aqui mantém a conexão viva e o
// modal/mini-barra seguem visíveis em qualquer aba do radar.
//
// Conceito React: Context. O provider chama useAnaliseStream UMA vez e
// distribui { progresso, analisar, ... } para qualquer página que chamar
// useAnalise(), sem passar props de mão em mão.

import { createContext, useContext, useEffect } from "react";
import { useAnaliseStream } from "./useAnaliseStream";
import ProgressoAnalise from "./ProgressoAnalise";

type ContextoAnalise = ReturnType<typeof useAnaliseStream>;

const AnaliseContext = createContext<ContextoAnalise | null>(null);

export function useAnalise(): ContextoAnalise {
  const ctx = useContext(AnaliseContext);
  if (!ctx) {
    throw new Error("useAnalise precisa estar dentro de <AnaliseProvider>");
  }
  return ctx;
}

export default function AnaliseProvider({
  children,
}: {
  children: React.ReactNode;
}) {
  const analise = useAnaliseStream();
  const emAnalise = analise.progresso.aberto && !analise.progresso.done;

  // recarregar/fechar a ABA durante uma análise mata o SSE sem aviso; o
  // beforeunload faz o navegador perguntar "sair mesmo?" enquanto roda
  useEffect(() => {
    if (!emAnalise) return;
    const avisar = (e: BeforeUnloadEvent) => {
      e.preventDefault();
    };
    window.addEventListener("beforeunload", avisar);
    return () => window.removeEventListener("beforeunload", avisar);
  }, [emAnalise]);

  return (
    <AnaliseContext.Provider value={analise}>
      {children}
      {/* renderizado AQUI (não nas páginas): o modal/mini-barra aparecem em
          qualquer aba do radar e sobrevivem à navegação */}
      <ProgressoAnalise
        progresso={analise.progresso}
        onFechar={analise.fechar}
        onCancelar={analise.cancelar}
        onMinimizar={analise.minimizar}
        onExpandir={analise.expandir}
      />
    </AnaliseContext.Provider>
  );
}
