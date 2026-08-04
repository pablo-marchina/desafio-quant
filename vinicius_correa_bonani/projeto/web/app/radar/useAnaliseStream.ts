"use client";

// Hook compartilhado do PROGRESSO AO VIVO da análise (usado pelo Ranking e
// pela Descoberta). Encapsula toda a conversa SSE com /analisar-stream:
// abre o EventSource, atualiza o checklist dos 8 agentes e resolve uma
// Promise ao terminar, para o chamador poder `await analisar(nome)` (é o
// que permite o "Analisar todas" rodar em sequência).
//
// FOOTGUN CRÍTICO mantido aqui dentro: EventSource RECONECTA sozinho quando
// o servidor fecha a conexão; sem o es.close() no evento {done} E no
// onerror, a análise re-dispararia em loop para sempre.

import { useEffect, useRef, useState } from "react";
import {
  DatabaseIcon,
  FileTextIcon,
  GlobeIcon,
  MagnifyingGlassIcon,
  ScalesIcon,
  SealCheckIcon,
  TableIcon,
  TreeStructureIcon,
  type Icon,
} from "@phosphor-icons/react";

// os 8 nós do grafo, na ordem do fluxo; os ids batem com os nomes que o
// stream do LangGraph emite (app/graph.py). Os ícones (referências de
// componente, sem JSX) alimentam a mini-barra do modo minimizado.
export const AGENTES_PIPELINE: { id: string; rotulo: string; icone: Icon }[] = [
  { id: "search_planner", rotulo: "Search Planner", icone: MagnifyingGlassIcon },
  { id: "scraper", rotulo: "Scraper", icone: GlobeIcon },
  { id: "extractor", rotulo: "Extractor", icone: TableIcon },
  { id: "evidence_validator", rotulo: "Evidence Validator", icone: SealCheckIcon },
  { id: "classifier", rotulo: "Classifier", icone: TreeStructureIcon },
  { id: "nvidia_rag", rotulo: "NVIDIA RAG", icone: DatabaseIcon },
  { id: "recommendation", rotulo: "Recommendation", icone: ScalesIcon },
  { id: "briefing", rotulo: "Briefing", icone: FileTextIcon },
];

export type Progresso = {
  aberto: boolean;
  /** true = modal escondido, mini-barra embaixo mostrando o andamento */
  minimizado: boolean;
  /** o que o modal mostra no título (ex.: "Alice" ou "2 de 5: Alice") */
  rotulo: string;
  atual: string | null; // nó rodando agora
  concluidos: string[]; // nós que já rodaram
  done: boolean;
  erro: string | null;
  classificacao: string | null;
};

const PROGRESSO_INICIAL: Progresso = {
  aberto: false,
  minimizado: false,
  rotulo: "",
  atual: null,
  concluidos: [],
  done: false,
  erro: null,
  classificacao: null,
};

export type ResultadoAnalise = {
  erro: string | null;
  classificacao: string | null;
};

export function useAnaliseStream() {
  const [progresso, setProgresso] = useState<Progresso>(PROGRESSO_INICIAL);
  const esRef = useRef<EventSource | null>(null);
  // guarda o resolve da Promise em andamento, para o cancelar() poder
  // destravar quem está aguardando (ex.: a fila do "Analisar todas")
  const resolveRef = useRef<((r: ResultadoAnalise) => void) | null>(null);

  // se o provider desmontar de vez, a conexão SSE morre junto
  useEffect(() => () => esRef.current?.close(), []);

  const analisar = (consulta: string, rotulo?: string) =>
    new Promise<ResultadoAnalise>((resolve) => {
      resolveRef.current = resolve;
      // reseta o checklist (no "Analisar todas" cada empresa recomeça do
      // zero) e abre o modal. Se o usuário minimizou e a FILA continua
      // (o modal já estava aberto), respeitamos a minimização; só uma
      // análise iniciada do zero abre expandida.
      setProgresso((p) => ({
        ...PROGRESSO_INICIAL,
        aberto: true,
        minimizado: p.aberto ? p.minimizado : false,
        rotulo: rotulo ?? consulta,
      }));

      const es = new EventSource(
        `${process.env.NEXT_PUBLIC_API_URL}/analisar-stream?consulta=${encodeURIComponent(consulta)}`
      );
      esRef.current = es;

      es.onmessage = (ev) => {
        const dado = JSON.parse(ev.data);
        if (dado.agente) {
          // o nó anterior terminou; o novo está rodando
          setProgresso((p) => ({
            ...p,
            atual: dado.agente,
            concluidos:
              p.atual && p.atual !== dado.agente && !p.concluidos.includes(p.atual)
                ? [...p.concluidos, p.atual]
                : p.concluidos,
          }));
        }
        if (dado.done) {
          es.close(); // <- impede a reconexão automática (re-análise em loop)
          esRef.current = null;
          setProgresso((p) => ({
            ...p,
            done: true,
            atual: null,
            concluidos:
              p.atual && !p.concluidos.includes(p.atual)
                ? [...p.concluidos, p.atual]
                : p.concluidos,
            erro: dado.erro ?? null,
            classificacao: dado.classificacao ?? null,
          }));
          resolveRef.current = null;
          resolve({
            erro: dado.erro ?? null,
            classificacao: dado.classificacao ?? null,
          });
        }
      };

      es.onerror = () => {
        es.close(); // mesmo motivo: nunca deixar o EventSource reconectar
        esRef.current = null;
        setProgresso((p) =>
          p.done ? p : { ...p, done: true, erro: "Conexão com a análise perdida." }
        );
        resolveRef.current = null;
        resolve({ erro: "Conexão com a análise perdida.", classificacao: null });
      };
    });

  const fechar = () => setProgresso(PROGRESSO_INICIAL);

  // Cancela DE VERDADE: fecha o SSE (o backend aborta o grafo ao perder a
  // conexão; nada é persistido) e destrava quem estava aguardando a Promise
  // (a fila do "Analisar todas" recebe o erro e para).
  const cancelar = () => {
    esRef.current?.close();
    esRef.current = null;
    resolveRef.current?.({ erro: "cancelada", classificacao: null });
    resolveRef.current = null;
    setProgresso(PROGRESSO_INICIAL);
  };

  // minimizar/expandir só trocam a apresentação; o SSE segue rodando igual
  const minimizar = () => setProgresso((p) => ({ ...p, minimizado: true }));
  const expandir = () => setProgresso((p) => ({ ...p, minimizado: false }));

  return { progresso, analisar, fechar, cancelar, minimizar, expandir };
}
