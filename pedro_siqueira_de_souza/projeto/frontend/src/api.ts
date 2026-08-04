// Camada de acesso ao backend + tipos compartilhados entre as páginas.
// Espelha o payload de POST /api/pipeline/run (api/main.py).

export interface TechRec {
  tech: string;
  url: string;
  summary: string;
  confidence: string; // força do match por regras (alta/média/baixa)
  matched_signals: string[];
  growth: string; // como o produto ajuda ESTA empresa a crescer
  snippet: string;
}
export interface Recommendation {
  name: string;
  label: string;
  technologies: TechRec[];
  overall_confidence: string;
  notes: string[];
}
export interface StartupInner {
  name: string;
  description: string | null;
  sector: string | null;
  stage: string | null;
  funding: string | null;
}
export interface Classified {
  startup: StartupInner;
  label: string;
  rationale: string;
  confidence: string;
}
export interface PipelineResult {
  query: string;
  classified_startups: Classified[];
  recommendations: Recommendation[];
  briefings: { name: string; label: string; markdown: string }[];
  trace: string[];
}

// Startup persistida no banco (página Qualificadas).
export interface StartupRow {
  name: string;
  sector: string | null;
  stage: string | null;
  funding: string | null;
  classification: string;
  confidence: number;
  created_at: string;
}

export async function listStartups(): Promise<StartupRow[]> {
  const resp = await fetch("/api/startups");
  if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
  return (await resp.json()).startups;
}

// Detalhe de uma startup persistida (dropdown da página Qualificadas).
export interface StartupDetail extends StartupRow {
  description: string | null;
  recommendations: Recommendation | null; // produtos NVIDIA recomendados
  briefing: string | null; // briefing executivo em markdown
}

export async function getStartup(name: string): Promise<StartupDetail> {
  const resp = await fetch(`/api/startups/${encodeURIComponent(name)}`);
  if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
  return resp.json();
}

// Agregados do ecossistema (página Analytics).
export interface Analytics {
  total: number;
  by_classification: { classification: string; count: number }[];
  by_sector: { sector: string; count: number }[];
  by_nvidia_tech: { tech: string; count: number }[];
  with_reco: number; // startups com ao menos um produto NVIDIA recomendado
}

export async function getAnalytics(): Promise<Analytics> {
  const resp = await fetch("/api/analytics");
  if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
  return resp.json();
}

export async function runPipeline(query: string): Promise<PipelineResult> {
  const resp = await fetch("/api/pipeline/run", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ query }),
  });
  if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
  return resp.json();
}

// --- Pipeline com streaming (SSE): progresso por etapa ---
export interface StageInfo {
  node: string;
  label: string;
}
// Eventos emitidos por POST /api/pipeline/stream (espelha api/main.py).
export type PipelineEvent =
  | { type: "start"; stages: StageInfo[] }
  | { type: "node"; node: string; label: string; message: string | null }
  | { type: "done"; result: PipelineResult }
  | { type: "error"; error: string };

// Dispara o pipeline em modo streaming e chama `onEvent` a cada frame SSE.
// Usa fetch + reader (em vez de EventSource) porque precisamos de POST com body;
// EventSource só faz GET. Faz o parse manual do protocolo SSE (frames separados
// por linha em branco, payload na linha `data: `).
export async function streamPipeline(
  query: string,
  onEvent: (ev: PipelineEvent) => void,
  signal?: AbortSignal,
): Promise<void> {
  const resp = await fetch("/api/pipeline/stream", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ query }),
    signal,
  });
  if (!resp.ok || !resp.body) throw new Error(`HTTP ${resp.status}`);

  const reader = resp.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });

    // Frames SSE são separados por uma linha em branco (\n\n).
    let sep: number;
    while ((sep = buffer.indexOf("\n\n")) !== -1) {
      const frame = buffer.slice(0, sep);
      buffer = buffer.slice(sep + 2);
      const linha = frame.split("\n").find((l) => l.startsWith("data:"));
      if (linha) onEvent(JSON.parse(linha.slice(5).trim()) as PipelineEvent);
    }
  }
}

// --- Cores semânticas (ux.md §2.2), reusadas pelas páginas ---
export function labelClass(label: string): string {
  if (label === "AI-native") return "badge-green";
  if (label === "AI-enabled") return "badge-amber";
  return "badge-dim";
}
