// Cliente da API TAPI (FastAPI, F5.2) consumido pelo front. O run longo nao cabe no
// request: `POST /runs` so enfileira e devolve o `run_id`; o progresso ao vivo chega por
// SSE em `GET /runs/{id}` (canal Redis pub/sub do worker, F2.10) — ver `runStreamUrl`.
//
// A base da API vem de `NEXT_PUBLIC_API_URL` (inlinada no bundle no build); o default
// `http://localhost:8080` cobre o dev local (a API roda na 8080, ver apps/Dockerfile). Auth (gate interno, F5.9): as chamadas fetch
// levam o `Authorization: Bearer` (authHeaders); o SSE e o PDF, que navegam sem header, levam
// o token na query (appendToken). Um 401 limpa a sessao e devolve a UI pro login (`reqJson`).
import { appendToken, authHeaders, signalUnauthorized } from "./auth";

export const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8080";

// fetch + tratamento uniforme do gate (F5.9): no 401 limpa o token e sinaliza o AuthGate, depois
// estoura um erro legivel; nos demais erros HTTP usa a mensagem do chamador. Devolve a Response
// pronta p/ `.json()`/checagem de 404 especifica de cada endpoint.
async function req(url: string, init: RequestInit = {}): Promise<Response> {
  const res = await fetch(url, { ...init, headers: { ...(init.headers ?? {}), ...authHeaders() } });
  if (res.status === 401) {
    signalUnauthorized();
    throw new Error("Sessao expirada ou credencial invalida. Entre novamente.");
  }
  return res;
}

// Modos de consulta (espelha ExecutionMode, packages/schemas/enums.py — F2.3).
export type RunMode = "single_company" | "discovery";

// Modo do HITL (HITLMode, F2.8): sync trava no single-company, auto nao bloqueia o lote.
export type HitlMode = "sync" | "auto";

// Resposta de `POST /runs` e `/resume` (RunAccepted, apps/api/schemas.py).
export interface RunAccepted {
  run_id: string;
  status: string;
}

// Evento de progresso por no (ProgressEvent, packages/agents/progress.py — contrato SSE).
export interface ProgressEvent {
  run_id: string;
  node: string;
  status: string;
  pct: number | null;
  ts: string;
  extra: Record<string, unknown>;
}

// Enfileira um run e devolve o `run_id`. O `hitl` segue o modo: single-company trava no
// interrupt (sync, F2.8/F5.10), discovery roda em lote sem bloquear a fila (auto).
export async function createRun(query: string, mode: RunMode): Promise<RunAccepted> {
  const hitl: HitlMode = mode === "single_company" ? "sync" : "auto";
  const res = await req(`${API_URL}/runs`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ query, mode, hitl }),
  });
  if (!res.ok) {
    throw new Error(`Falha ao enfileirar a consulta (HTTP ${res.status}).`);
  }
  return res.json() as Promise<RunAccepted>;
}

// URL do stream SSE do run — passada direto a `new EventSource(...)` no console (F5.3). O
// EventSource nao manda header, entao o token (F5.9) vai na query via `appendToken`.
export function runStreamUrl(runId: string): string {
  return appendToken(`${API_URL}/runs/${encodeURIComponent(runId)}`);
}

// Payload da revisao HITL de um run (RunReviewOut, apps/api/schemas.py — F5.10): o diagnostico
// (classe/AIMI/recs) que o gerente revisa antes do briefing, lido do estado persistido (F2.8/F2.2).
// `awaiting_review` diz se o run esta de fato parado no interrupt (a UI distingue "pausado p/
// revisar" de "ja seguiu", ex.: ao recarregar). Campos de diagnostico opcionais — run offline sem
// extracao vem com null/lista vazia.
export interface RunReview {
  run_id: string;
  awaiting_review: boolean;
  query: string | null;
  empresa: string | null;
  classificacao: string | null;
  aimi_total: number | null;
  recomendacoes: string[];
}

// Decisao do gerente enviada ao `POST /runs/{id}/resume` (F5.2/F5.10). Vira o retorno do
// `interrupt()` e fica registrada em trace["human_review"] (auditavel, F2.8). `aprovado=false` =
// rejeicao. `edicoes` carrega as correcoes (classe/AIMI) do modo editar — capturadas/auditadas;
// aplica-las p/ alterar o diagnostico no briefing e gancho futuro de backend (F2.8/F4.4).
export interface ResumeDecision {
  approved: boolean;
  nota?: string;
  edicoes?: {
    classificacao?: string;
    aimi_total?: number;
  };
}

// Carrega o payload de revisao de um run (`GET /runs/{id}/review`, F5.10). 404 vira mensagem
// propria (run inexistente) para a tela distinguir de uma falha de rede.
export async function getRunReview(runId: string): Promise<RunReview> {
  const res = await req(`${API_URL}/runs/${encodeURIComponent(runId)}/review`);
  if (res.status === 404) {
    throw new Error("Run nao encontrado (sem revisao pendente).");
  }
  if (!res.ok) {
    throw new Error(`Falha ao carregar a revisao do run (HTTP ${res.status}).`);
  }
  return res.json() as Promise<RunReview>;
}

// Retoma um run pausado no HITL sync com a decisao do gerente (`POST /runs/{id}/resume`, F5.2/
// F5.10): enfileira o job de resume e devolve o `run_id` (o SSE acompanha os nos restantes).
export async function resumeRun(runId: string, decision: ResumeDecision): Promise<RunAccepted> {
  const res = await req(`${API_URL}/runs/${encodeURIComponent(runId)}/resume`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(decision),
  });
  if (!res.ok) {
    throw new Error(`Falha ao retomar o run (HTTP ${res.status}).`);
  }
  return res.json() as Promise<RunAccepted>;
}

// Fase de um run em andamento p/ a UI reencontrar uma consulta longa ao voltar a tela (F5.3+). O
// trabalho roda no worker (F2.10) e SOBREVIVE a navegacao; isto so diz o que mostrar ao reabrir:
// running (reabrir o SSE ao vivo), awaiting_review (painel de revisao), done (hidratar do
// checkpoint), failed (job caiu) ou unknown (run expirado/orfao -> a UI descarta o run guardado).
export type RunPhase = "running" | "awaiting_review" | "done" | "failed" | "unknown";

// Estado de um run (RunStatusOut, apps/api/schemas.py): a fase + o desfecho real quando phase=done.
export interface RunStatusInfo {
  run_id: string;
  phase: RunPhase;
  run_status: string | null;
}

// Consulta a fase de um run (`GET /runs/{id}/status`, F5.3+) p/ a reconexao da consulta. Nunca 404:
// o backend sempre devolve uma fase acionavel (combina o status do job RQ com o checkpoint, F2.2).
export async function getRunStatus(runId: string): Promise<RunStatusInfo> {
  const res = await req(`${API_URL}/runs/${encodeURIComponent(runId)}/status`);
  if (!res.ok) {
    throw new Error(`Falha ao consultar o estado do run (HTTP ${res.status}).`);
  }
  return res.json() as Promise<RunStatusInfo>;
}

// Formatos do briefing servidos por `GET /briefings/{id}` (F4.6): JSON | Markdown | PDF.
export type BriefingFormat = "json" | "md" | "pdf";

// URL do briefing executivo renderizado de um run (`GET /briefings/{id}`, F4.4/F4.6 — export
// F5.8). O backend devolve o PDF com `Content-Disposition: inline`, entao abrir num
// `<a target="_blank">` exibe o relatorio (o usuario salva de la). Como o `<a>` navega sem
// header, a auth (F5.9) vai como query (`appendToken`) — por isso e uma URL montada, nao um fetch.
export function briefingUrl(runId: string, format: BriefingFormat = "pdf"): string {
  return appendToken(`${API_URL}/briefings/${encodeURIComponent(runId)}?format=${format}`);
}

// Projecao de empresa da lista (CompanyOut, apps/api/schemas.py — F5.4): perfil achatado com o
// diagnostico AIMI mais recente. Os campos de diagnostico sao opcionais — empresa coletada mas
// ainda nao pontuada chega sem classe/AIMI. `tecnologias`/`nvidia_techs` sao as tags do
// vocabulario controlado (F5.11): a tech que a startup usa e a tech NVIDIA recomendada.
export interface CompanyOut {
  id: number;
  nome: string;
  setor: string | null;
  pais: string;
  website: string | null;
  classificacao: string | null;
  aimi_total: number | null;
  inception_priority: number | null;
  tecnologias: string[];
  nvidia_techs: string[];
}

// Filtros do radar (F5.4/F5.11): setor, classe de maturidade, AIMI minimo e as duas facetas de
// tech — `tech` (a startup usa) e `nvidiaTech` (NVIDIA recomendada). Combinam em AND no backend;
// todos opcionais. As tags de tech vem do vocabulario controlado (`listTechFacets`).
export interface CompanyFilters {
  setor?: string;
  classificacao?: string;
  minAimi?: number;
  tech?: string;
  nvidiaTech?: string;
}

// Lista as startups (perfil + AIMI) ja ordenadas por inception_priority desc (a fila de
// outreach do gerente, F6.13) no `GET /companies` (F5.2). Vazios sao omitidos da query.
export async function listCompanies(filters: CompanyFilters = {}): Promise<CompanyOut[]> {
  const params = new URLSearchParams();
  if (filters.setor?.trim()) params.set("setor", filters.setor.trim());
  if (filters.classificacao) params.set("classificacao", filters.classificacao);
  if (filters.minAimi != null && filters.minAimi > 0) {
    params.set("min_aimi", String(filters.minAimi));
  }
  if (filters.tech) params.set("tech", filters.tech);
  if (filters.nvidiaTech) params.set("nvidia_tech", filters.nvidiaTech);
  const qs = params.toString();
  const res = await req(`${API_URL}/companies${qs ? `?${qs}` : ""}`);
  if (!res.ok) {
    throw new Error(`Falha ao carregar as startups (HTTP ${res.status}).`);
  }
  return res.json() as Promise<CompanyOut[]>;
}

// Vocabulario controlado dos filtros de tech (TechFacetsOut, F5.11): as tags que as startups da
// coorte usam (`tech`) e as tags NVIDIA recomendadas (`nvidia_tech`), normalizadas e ordenadas
// pelo backend. O radar monta os controles a partir disto — so filtra por tag que existe.
export interface TechFacets {
  tech: string[];
  nvidia_tech: string[];
}

// Carrega as tags disponiveis para os filtros de tech (`GET /companies/facets`, F5.11).
export async function listTechFacets(): Promise<TechFacets> {
  const res = await req(`${API_URL}/companies/facets`);
  if (!res.ok) {
    throw new Error(`Falha ao carregar as tecnologias (HTTP ${res.status}).`);
  }
  return res.json() as Promise<TechFacets>;
}

// Um match da descoberta (DiscoverHitOut, F3.10/F5.12): a empresa + por que casou. `similaridade`
// e o cosseno 0-1 com a pergunta no modo semantico (texto livre), null no modo so-filtro; `citacao`
// e a fonte rastreavel que sustenta o match (§8 — nada sem evidencia). Reusa CompanyOut/EvidenceOut.
export interface DiscoverHit {
  empresa: CompanyOut;
  similaridade: number | null;
  citacao: EvidenceOut | null;
}

// Resposta do chat de descoberta da coorte (DiscoverOut, apps/api/schemas.py — F3.10/F5.12).
// `entendido` ecoa como a pergunta NL foi interpretada; `resumo` e a frase de resposta; `modo` diz
// se a ordem veio do filtro (Inception Priority) ou do ranking semantico (relevancia ao texto
// livre); `resultados` sao os matches nessa ordem, cada um com a empresa + a citacao que o sustenta.
export interface DiscoverResult {
  pergunta: string;
  entendido: string;
  resumo: string;
  modo: "filtro" | "semantico";
  resultados: DiscoverHit[];
}

// Pergunta a coorte em linguagem natural (`GET /discover?q=`, F3.10/F5.12): o backend traduz a
// pergunta PT-BR nos filtros estruturados que `listCompanies` ja entende e devolve as empresas +
// como interpretou. Pergunta vazia volta a coorte inteira por prioridade de outreach (o backend
// trata "" como sem filtro). "Suscetivel a tech X" = o recommender prescreveu X (filtro nvidia_tech).
export async function discoverCohort(q: string): Promise<DiscoverResult> {
  const res = await req(`${API_URL}/discover?q=${encodeURIComponent(q)}`);
  if (!res.ok) {
    throw new Error(`Falha na descoberta da coorte (HTTP ${res.status}).`);
  }
  return res.json() as Promise<DiscoverResult>;
}

// Fonte citavel de um sub-score (EvidenceOut, apps/api/schemas.py — F5.5): o link que sustenta
// o pilar. Pode vir vazia ate a persistencia do AIMI gravar essas linhas (a UI degrada).
export interface EvidenceOut {
  url: string;
  snippet: string;
  source_title: string | null;
}

// Um pilar do AIMI no detalhe (PillarOut, F5.5): sub-score 0-25 + faixa + justificativa + fontes.
// `pilar` e a chave tecnica (AIMIPillar, ex.: "data_moat"); o rotulo PT-BR e da UI.
export interface PillarOut {
  pilar: string;
  score: number;
  band: string;
  justificativa: string | null;
  evidencias: EvidenceOut[];
}

// ROI quantificado de uma recomendacao (ROIOut, F5.6/F6): opcional — vem do GPU Graduation Engine
// quando ha gap de inferencia. Convencao de sinal: delta negativo = melhora (menos custo/latencia).
// Quando ausente o cartao degrada gracioso (mostra a recomendacao sem o numero).
export interface ROIOut {
  throughput_speedup: number | null;
  latency_p95_delta_pct: number | null;
  cost_delta_pct: number | null;
  baseline: string | null;
  optimized: string | null;
  benchmark_source: string | null;
  is_live_run: boolean;
}

// Cartao de recomendacao no detalhe (RecommendationOut, §5.5/F5.6): tech + justificativas +
// evidencia dos dois lados (gap da startup / KB NVIDIA) + ROI opcional. `pilar_origem` e a chave
// tecnica (AIMIPillar); a lista ja vem ordenada por prioridade (alta->baixa), como no briefing.
export interface RecommendationOut {
  tech: string;
  prioridade: string;
  complexidade: string;
  justificativa_tecnica: string;
  justificativa_negocio: string;
  proxima_acao: string;
  pilar_origem: string | null;
  roi: ROIOut | null;
  evidencia_gap: EvidenceOut[];
  evidencia_nvidia: EvidenceOut[];
}

// Detalhe de uma startup (CompanyDetailOut, F5.5/F5.6): perfil + radar AIMI (4 pilares) com
// evidencia por pilar + cartoes de recomendacao (justificativa, evidencia dos dois lados, ROI).
// `pilares`/`recomendacoes` vem vazias quando a empresa ainda nao foi pontuada/recomendada.
export interface CompanyDetail {
  id: number;
  nome: string;
  setor: string | null;
  pais: string;
  website: string | null;
  descricao: string | null;
  ano_fundacao: number | null;
  classificacao: string | null;
  aimi_total: number | null;
  inception_priority: number | null;
  confidence: number | null;
  heuristic_version: string | null;
  pilares: PillarOut[];
  nvidia_techs: string[];
  recomendacoes: RecommendationOut[];
}

// Detalhe de uma startup pelo id (`GET /companies/{id}`, F5.2/F5.5). 404 vira mensagem propria
// (empresa inexistente) para a tela distinguir de uma falha de rede.
export async function getCompany(id: number): Promise<CompanyDetail> {
  const res = await req(`${API_URL}/companies/${id}`);
  if (res.status === 404) {
    throw new Error("Startup nao encontrada.");
  }
  if (!res.ok) {
    throw new Error(`Falha ao carregar a startup (HTTP ${res.status}).`);
  }
  return res.json() as Promise<CompanyDetail>;
}

// Passo (no) do grafo no trace de um run (TraceStepOut, apps/api/trace.py — F5.7). `node` e a
// chave tecnica (PIPELINE_STEPS rotula em PT-BR); `status`: done (deixou artefato no estado),
// skipped (run terminou sem passar aqui — ramo terminal ou etapa opcional sem saida) ou pending
// (run pausou/falhou antes de chegar). `summary` resume o que o no produziu (so nos done).
export interface RunTraceStep {
  node: string;
  status: "done" | "skipped" | "pending";
  summary: string | null;
}

// Rollup de tokens/custo do run (TraceUsageOut, F2.9). Ausente (null) em run offline sem LLM.
export interface RunTraceUsage {
  input_tokens: number;
  output_tokens: number;
  total_tokens: number;
  calls: number;
  cost_usd: number;
}

// Trace de um run para o viewer (RunTraceOut, F5.7): passos dos agentes reconstruidos do estado
// persistido (checkpoint, F2.2) + custo + erros + link Langfuse (deep-trace, quando ligado).
export interface RunTrace {
  run_id: string;
  status: string;
  prompt_version: string | null;
  steps: RunTraceStep[];
  usage: RunTraceUsage | null;
  budget_limited: boolean;
  errors: string[];
  langfuse_url: string | null;
}

// Trace de um run (`GET /runs/{id}/trace`, F5.7). 404 vira mensagem propria (run sem checkpoint)
// para a tela distinguir de uma falha de rede.
export async function getRunTrace(runId: string): Promise<RunTrace> {
  const res = await req(`${API_URL}/runs/${encodeURIComponent(runId)}/trace`);
  if (res.status === 404) {
    throw new Error("Run nao encontrado (sem trace registrado).");
  }
  if (!res.ok) {
    throw new Error(`Falha ao carregar o trace do run (HTTP ${res.status}).`);
  }
  return res.json() as Promise<RunTrace>;
}

// Estado de saude da API (`GET /health`, aberto/sem gate). `auth_required` diz se a API exige
// credencial (ha TAPI_API_TOKEN configurado) — o AuthGate (F5.9) usa isso no boot p/ decidir se
// pede login antes de mostrar a UI.
export interface HealthInfo {
  status: string;
  auth_required: boolean;
}

export async function fetchHealth(): Promise<HealthInfo> {
  const res = await fetch(`${API_URL}/health`);
  if (!res.ok) {
    throw new Error(`API indisponivel (HTTP ${res.status}).`);
  }
  return res.json() as Promise<HealthInfo>;
}

// Valida o token guardado contra um endpoint protegido (gate F5.9) — usado pelo login do
// AuthGate p/ dar feedback imediato. true = aceito; false = credencial recusada (401). O 401 aqui
// NAO dispara o sinal global de logout (o proprio fluxo de login trata), por isso usa `fetch`.
export async function pingAuth(): Promise<boolean> {
  const res = await fetch(`${API_URL}/companies?limit=1`, { headers: authHeaders() });
  if (res.status === 401) return false;
  if (!res.ok) {
    throw new Error(`Falha ao validar a credencial (HTTP ${res.status}).`);
  }
  return true;
}

// Uma startup posicionada no radar de coorte (ClusterMember, packages/scoring/cohort_cluster.py —
// F6.7): coords 2D (x/y da projecao) + diagnostico + flag de alvo de graduacao ★.
export interface CohortClusterMember {
  id: number;
  nome: string;
  setor: string | null;
  classe: string | null;
  aimi: number | null;
  inception_priority: number | null;
  x: number;
  y: number;
  graduation_ready: boolean;
}

// Um cluster do ecossistema (Cluster, F6.7): metricas agregadas + prontidao de graduacao + membros.
export interface CohortCluster {
  id: number;
  label: string;
  size: number;
  mean_aimi: number;
  mean_inception: number;
  classe_dominante: string | null;
  graduation_ready_share: number;
  graduation_ready: boolean;
  members: CohortClusterMember[];
}

// Radar de portfolio da coorte (CohortClustering, F6.5-F6.7): clusters ja ordenados por prontidao +
// proveniencia (backend de clustering numpy/cuml e embedder hashing/nv). `method`/`embedder` deixam
// honesto se rodou offline (default) ou com a stack NVIDIA (flags).
export interface CohortClustering {
  n_companies: number;
  method: string;
  embedder: string;
  clusters: CohortCluster[];
}

// Carrega o radar de coorte (`GET /cohort/clusters`, F6.7). `k` opcional (nº de clusters; default
// heuristico no backend). Clusters ja vem ordenados por prontidao de graduacao (share ★ + Inception).
export async function getCohortClusters(k?: number): Promise<CohortClustering> {
  const qs = k != null ? `?k=${k}` : "";
  const res = await req(`${API_URL}/cohort/clusters${qs}`);
  if (!res.ok) {
    throw new Error(`Falha ao carregar o radar da coorte (HTTP ${res.status}).`);
  }
  return res.json() as Promise<CohortClustering>;
}
