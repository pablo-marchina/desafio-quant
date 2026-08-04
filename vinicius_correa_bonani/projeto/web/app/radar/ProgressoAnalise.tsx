"use client";

// Progresso ao vivo da análise, em DOIS modos controlados por
// progresso.minimizado (vem do hook useAnaliseStream):
//   - EXPANDIDO: o modal com o checklist dos 8 agentes;
//   - MINIMIZADO: uma barra fixa embaixo, com os ÍCONES dos agentes
//     acendendo, que deixa a página utilizável enquanto o grafo roda.
//
// A troca entre os modos é um MORPH: os dois containers compartilham o
// mesmo layoutId, então o Motion mede as duas caixas e anima posição +
// tamanho de uma para a outra (técnica FLIP), em vez de sumir/aparecer.
//
// Botões: "Cancelar análise" (neutro) enquanto roda, que aborta de verdade
// via onCancelar; vira "Concluído" (verde sólido) quando termina.

import { motion, AnimatePresence, useReducedMotion } from "motion/react";
import {
  ArrowsOutSimpleIcon,
  CheckCircleIcon,
  CircleIcon,
  CircleNotchIcon,
  MinusIcon,
} from "@phosphor-icons/react";
import { AGENTES_PIPELINE, type Progresso } from "./useAnaliseStream";

const BOTAO_NEUTRO =
  "rounded-lg border border-line px-4 py-2 text-sm font-medium text-ink transition-colors hover:border-ink-muted hover:bg-surface-2 active:translate-y-px";
const BOTAO_VERDE =
  "rounded-lg bg-nvidia px-4 py-2 text-sm font-semibold text-black transition-colors hover:bg-nvidia-bright active:translate-y-px";

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

export default function ProgressoAnalise({
  progresso,
  onFechar,
  onCancelar,
  onMinimizar,
  onExpandir,
}: {
  progresso: Progresso;
  onFechar: () => void;
  onCancelar: () => void;
  onMinimizar: () => void;
  onExpandir: () => void;
}) {
  const reduce = useReducedMotion();
  // com "reduzir movimento", desligamos o morph (troca instantânea)
  const morphId = reduce ? undefined : "painel-progresso";

  return (
    <>
      {/* ── Modo expandido: o modal ─────────────────────────────────── */}
      <AnimatePresence>
        {progresso.aberto && !progresso.minimizado && (
          <motion.div
            key="backdrop-progresso"
            initial={reduce ? false : { opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={reduce ? undefined : { opacity: 0 }}
            transition={{ duration: 0.15 }}
            className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4 backdrop-blur-sm"
            onClick={() => progresso.done && onFechar()}
          >
            <motion.div
              key="card-progresso"
              layoutId={morphId}
              role="dialog"
              aria-modal="true"
              aria-label={`Análise de ${progresso.rotulo}`}
              initial={reduce ? false : { opacity: 0, scale: 0.96, y: 8 }}
              animate={{ opacity: 1, scale: 1, y: 0 }}
              exit={reduce ? undefined : { opacity: 0 }}
              transition={{ type: "spring", duration: 0.45, bounce: 0.05 }}
              onClick={(e) => e.stopPropagation()}
              className="w-full max-w-md rounded-xl border border-line bg-[#0C0C0C] p-6"
            >
              <div className="flex items-start justify-between gap-4">
                <div>
                  <h2 className="text-lg font-bold tracking-tight">
                    Analisando {progresso.rotulo}
                  </h2>
                  <p className="mt-1 text-sm text-ink-muted">
                    O grafo roda os 8 agentes em sequência; pode levar minutos.
                  </p>
                </div>
                {/* minimizar funciona SEMPRE: o ponto é liberar a tela */}
                <button
                  onClick={onMinimizar}
                  aria-label="Minimizar progresso"
                  title="Minimizar (a análise continua)"
                  className="shrink-0 rounded-lg border border-nvidia/70 p-2 text-ink transition-colors hover:border-nvidia hover:bg-nvidia/10 active:translate-y-px"
                >
                  <MinusIcon size={16} aria-hidden />
                </button>
              </div>

              <ul className="mt-5 space-y-2.5">
                {AGENTES_PIPELINE.map((agente) => {
                  const concluido = progresso.concluidos.includes(agente.id);
                  const rodando = progresso.atual === agente.id;
                  return (
                    <li key={agente.id} className="flex items-center gap-3 text-sm">
                      {concluido ? (
                        <CheckCircleIcon
                          size={18}
                          weight="fill"
                          className="shrink-0 text-nvidia"
                          aria-hidden
                        />
                      ) : rodando ? (
                        <CircleNotchIcon
                          size={18}
                          className="shrink-0 animate-spin text-nvidia motion-reduce:animate-none"
                          aria-hidden
                        />
                      ) : (
                        <CircleIcon
                          size={18}
                          className="shrink-0 text-ink-muted/40"
                          aria-hidden
                        />
                      )}
                      <span
                        className={
                          concluido ? "" : rodando ? "text-ink" : "text-ink-muted"
                        }
                      >
                        {agente.rotulo}
                      </span>
                      {rodando && (
                        <span className="ml-auto font-mono text-xs text-nvidia">
                          rodando
                        </span>
                      )}
                    </li>
                  );
                })}
              </ul>

              <div className="mt-5 border-t border-line pt-4">
                {!progresso.done ? (
                  <>
                    <p className="text-xs text-ink-muted">
                      Você pode minimizar; a análise continua rodando.
                    </p>
                    <button
                      onClick={onCancelar}
                      className={`mt-3 w-full ${BOTAO_NEUTRO}`}
                    >
                      Cancelar análise
                    </button>
                  </>
                ) : progresso.erro ? (
                  <>
                    <p className="break-all text-sm text-ink-muted">
                      A análise falhou: {progresso.erro}
                    </p>
                    <button
                      onClick={onFechar}
                      className={`mt-3 w-full ${BOTAO_NEUTRO}`}
                    >
                      Fechar
                    </button>
                  </>
                ) : (
                  <>
                    <p className="flex items-center gap-2 text-sm">
                      Análise concluída
                      <Badge classificacao={progresso.classificacao} />
                    </p>
                    {progresso.classificacao === "non-ai" && (
                      <p className="mt-1 text-xs text-ink-muted">
                        Encerrada no desvio non-ai: o grafo poupa RAG,
                        recomendação e briefing.
                      </p>
                    )}
                    <button
                      onClick={onFechar}
                      className={`mt-3 w-full ${BOTAO_VERDE}`}
                    >
                      Concluído
                    </button>
                  </>
                )}
              </div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* ── Modo minimizado: a barra fixa (não bloqueia a página) ─────
          A centralização é por um WRAPPER flex, NÃO por left-1/2 +
          translateX(-50%): o morph do layoutId controla o transform do
          elemento, e um translateX manual de centralização brigava com ele,
          fazendo a barra deslizar pro lado antes de assentar. Sem transform
          de centralização, o morph vai direto ao centro. */}
      <div className="pointer-events-none fixed inset-x-0 bottom-6 z-40 flex justify-center px-4">
        <AnimatePresence>
          {progresso.aberto && progresso.minimizado && (
          <motion.div
            key="mini-progresso"
            layoutId={morphId}
            initial={reduce ? false : { opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={reduce ? undefined : { opacity: 0 }}
            transition={{ type: "spring", duration: 0.45, bounce: 0.05 }}
            className="pointer-events-auto flex max-w-full flex-wrap items-center gap-4 rounded-xl border border-line bg-[#0C0C0C] px-5 py-4"
          >
            <span className="max-w-[220px] truncate text-sm font-medium">
              {progresso.rotulo}
            </span>

            {/* os 8 agentes como ícones; o que roda ganha um anel girando */}
            <div className="flex items-center gap-2.5">
              {AGENTES_PIPELINE.map((agente) => {
                const concluido = progresso.concluidos.includes(agente.id);
                const rodando = progresso.atual === agente.id;
                const Icone = agente.icone;
                return (
                  <span
                    key={agente.id}
                    title={agente.rotulo}
                    className="relative flex h-8 w-8 items-center justify-center"
                  >
                    <Icone
                      size={19}
                      className={
                        concluido || rodando
                          ? "text-nvidia"
                          : "text-ink-muted/40"
                      }
                      aria-hidden
                    />
                    {rodando && (
                      <CircleNotchIcon
                        size={30}
                        className="absolute animate-spin text-nvidia/50 motion-reduce:animate-none"
                        aria-hidden
                      />
                    )}
                  </span>
                );
              })}
            </div>

            <div className="flex items-center gap-2">
              {!progresso.done ? (
                <button
                  onClick={onCancelar}
                  className={`${BOTAO_NEUTRO} px-3 py-1.5 text-xs`}
                >
                  Cancelar
                </button>
              ) : (
                <button
                  onClick={onFechar}
                  className={`${progresso.erro ? BOTAO_NEUTRO : BOTAO_VERDE} px-3 py-1.5 text-xs`}
                >
                  {progresso.erro ? "Fechar" : "Concluído"}
                </button>
              )}
              <button
                onClick={onExpandir}
                aria-label="Expandir progresso"
                title="Expandir"
                className="shrink-0 rounded-lg border border-nvidia/70 p-2 text-ink transition-colors hover:border-nvidia hover:bg-nvidia/10 active:translate-y-px"
              >
                <ArrowsOutSimpleIcon size={15} aria-hidden />
              </button>
            </div>
          </motion.div>
          )}
        </AnimatePresence>
      </div>
    </>
  );
}
