// Espelho no front da espinha do grafo multi-agente para rotular o progresso ao vivo (F5.3).
// A ordem e os nomes seguem `PIPELINE` em packages/agents/graph.py (F2.1); cada evento SSE
// (status=running) chega com o `node` que acabou de rodar — o console marca os vistos.
export const PIPELINE_STEPS: ReadonlyArray<{ node: string; label: string }> = [
  { node: "search_planner", label: "Planejando a busca" },
  { node: "scraper", label: "Coletando dados" },
  { node: "extractor", label: "Extraindo o perfil" },
  { node: "classifier", label: "Classificando (classe + AIMI)" },
  { node: "evidence_validator", label: "Validando evidencias" },
  { node: "nvidia_rag", label: "Buscando tecnologias NVIDIA (RAG)" },
  { node: "recommender", label: "Gerando recomendacoes" },
  { node: "gpu_benchmark", label: "Benchmark de GPU (ROI)" },
  { node: "human_review", label: "Revisao humana (HITL)" },
  { node: "briefing", label: "Montando o briefing" },
];

// No sentinela do evento terminal (END_NODE, packages/agents/progress.py): fecha o SSE.
export const END_NODE = "__end__";

// RunStatus (packages/schemas/enums.py) -> rotulo PT-BR exibido no estado do run.
const STATUS_LABELS: Record<string, string> = {
  pending: "Na fila",
  running: "Em execucao",
  resuming: "Retomando",
  awaiting_review: "Aguardando revisao",
  completed: "Concluido",
  insufficient_data: "Dados insuficientes",
  out_of_scope: "Fora de escopo",
  failed: "Falhou",
};

export function statusLabel(status: string): string {
  return STATUS_LABELS[status] ?? status;
}

// Desfechos terminais em que o run chegou ao no `briefing` — logo, ha relatorio para exportar
// (F5.8): o caminho completo (completed) e os ramos terminais que saltam direto ao briefing
// (insufficient_data F2.12 / out_of_scope F2.13). `awaiting_review` pausa ANTES do briefing e
// `failed` nao o alcanca, entao nao tem o que exportar.
const BRIEFING_STATES = new Set(["completed", "insufficient_data", "out_of_scope"]);

// Ha briefing exportavel para este desfecho? (gate do botao de export PDF no console, F5.8).
export function hasBriefing(status: string | null | undefined): boolean {
  return status != null && BRIEFING_STATES.has(status);
}
