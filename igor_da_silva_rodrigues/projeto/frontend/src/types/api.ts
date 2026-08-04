// =============================================================
// Tipos mapeados da API FastAPI do NVIDIA Startup AI Radar
// =============================================================

export type MaturityClass = 'AI-native' | 'AI-enabled' | 'API-consumer' | 'Non-AI' | 'unknown'

export type RunStatus =
  | 'pending'
  | 'running'
  | 'completed'
  | 'partial'
  | 'failed'
  | 'cancelled'

export type BatchStatus = 'created' | 'pending' | 'running' | 'completed' | 'partial' | 'cancelled' | 'failed'

export type InceptionEligibility = 'eligible' | 'ineligible' | 'unknown'

// ------------------------------------------------------------------
// Startup
// ------------------------------------------------------------------
export interface Startup {
  id: string
  external_id: string | null
  nome: string
  site_oficial: string | null
  categoria: string | null
  cidade: string | null
  estado: string | null
  pais: string | null
  descricao_curta?: string | null
  logo_url?: string | null
  created_at: string
  maturity_class?: MaturityClass
  maturity_level?: number | null
  fit_score?: number | null
  pipeline_runs?: PipelineRunSummary[]
}

export interface StartupDiscoveryResult {
  status: 'success' | 'partial'
  source: string
  requested_limit: number
  source_offset: number
  collected_count: number
  curated_count: number
  created_count: number
  existing_count: number
  startup_ids: string[]
  batch_id: string | null
  analysis_queued_count: number
  errors: Array<{ startup_index?: number; mensagem?: string }>
}

// ------------------------------------------------------------------
// Pipeline Run
// ------------------------------------------------------------------
export interface PipelineRunSummary {
  id: string
  status: RunStatus
  current_stage: string | null
  started_at: string | null
  finished_at: string | null
  duration_ms: number | null
  created_at: string
}

export interface PipelineRun extends PipelineRunSummary {
  startup_id: string
  attempt_count: number
  error_summary: string | null
}

// ------------------------------------------------------------------
// Analysis (Run detail)
// ------------------------------------------------------------------
export interface AiAssessment {
  id: string
  pipeline_run_id: string
  maturity_class: MaturityClass
  maturity_level: number | null
  technologies: string[]
  evidence_summary: string | null
  limitations: string[]
  confidence: number | null
  review_required: boolean
  review_reason: string | null
  created_at: string
}

export interface InceptionFitAssessment {
  id: string
  pipeline_run_id: string
  eligibility_status: InceptionEligibility
  startup_stage: 'early' | 'growth' | 'scale' | 'unknown'
  needs: string[]
  benefit_matches: BenefitMatch[]
  open_questions: string[]
  created_at: string
}

export interface BenefitMatch {
  benefit: string
  justification: string
  source: string | null
  confidence: number
}

export interface NvidiaRecommendation {
  id: string
  pipeline_run_id: string
  technologies: RecommendedTechnology[]
  opportunity_score: number | null
  next_action: string | null
  created_at: string
}

export interface RecommendedTechnology {
  name: string
  category: string
  rationale: string
  priority: 'high' | 'medium' | 'low'
}

export interface ImpactEstimate {
  id: string
  pipeline_run_id: string
  estimated_impact: string | null
  impact_areas: string[]
  confidence: number | null
  aggregate_index: number | null
  uncertainties: string[]
  suggested_kpis: string[]
  estimates: ImpactTechnologyEstimate[]
  created_at: string
}

export interface ImpactTechnologyEstimate {
  tecnologia: string
  confianca: string
  premissas: string[]
  impacto_negocio: string
  impacto_tecnico: Record<string, string>
  fontes_evidencia: string[]
}

export interface RecommendationRefinement {
  id: string
  pipeline_run_id: string
  fit_score: number | null
  technologies: RefinedTechnology[]
  roadmap: Record<string, { acoes: string[]; tecnologias: string[] }>
  startup_questions: string[]
  alerts: string[]
  created_at: string
}

export interface RefinedTechnology {
  tecnologia: string
  fase: string
  ordem: number
  riscos: string
  beneficio: string
  complexidade: string
  dependencias: string[]
  fontes_evidencia: string[]
  problema_resolvido: string
}

export interface ExecutiveBriefing {
  id: string
  pipeline_run_id: string
  markdown: string
  created_at: string
}

export interface RunAnalysis {
  run: PipelineRun
  assessment: AiAssessment | null
  inception_fit: InceptionFitAssessment | null
  recommendation: NvidiaRecommendation | null
  refinement: RecommendationRefinement | null
  impact: ImpactEstimate | null
  briefing: ExecutiveBriefing | null
}

// ------------------------------------------------------------------
// Batch
// ------------------------------------------------------------------
export interface Batch {
  id: string
  status: BatchStatus
  total_items: number
  completed_items: number
  failed_items: number
  partial_items: number
  created_at: string
  started_at: string | null
  finished_at: string | null
  items?: BatchItem[]
}

export type BatchItemStatus = 'pending' | 'running' | 'completed' | 'partial' | 'failed' | 'cancelled'

export interface BatchItem {
  id: string
  batch_id: string
  startup_id: string
  startup_name?: string
  status: BatchItemStatus
  attempt_count: number
  pipeline_run_id: string | null
  error_message: string | null
  created_at: string
  updated_at: string
}

export interface DeadLetter {
  id: string
  batch_id: string
  batch_item_id: string
  startup_name?: string
  error_category: string | null
  error_message: string | null
  attempt_count: number
  created_at: string
}

export interface EvidenceSource {
  id: string
  url: string
  tipo_fonte: string
  credibilidade: number
  status: string
  created_at: string
}

export interface Evidence {
  id: string
  pipeline_run_id: string
  source_id: string
  trecho: string
  score_confianca: number
  classificacao: string
  contem_ia: boolean
  descartada: boolean
  motivo_descarte: string | null
  created_at: string
  source: EvidenceSource | null
}

export interface POCBlueprint {
  startup: string
  purpose: string
  baseline_checklist: string[]
  workstreams: Array<{
    technology: string
    phase: string
    objective: string
    prerequisites: string[]
    kpis: string[]
    acceptance_criteria: string[]
    risks: string[]
    sources: string[]
  }>
  timeline: Array<{ phase: string; activity: string }>
  uncertainties: string[]
  markdown: string
}

export interface BatchCreateRequest {
  source_file?: string
  limit?: number
  startup_ids?: string[]
  include_ineligible?: boolean
  max_attempts?: number
  stop_on_error?: boolean
}

// ------------------------------------------------------------------
// Metrics
// ------------------------------------------------------------------
export interface ApiMetrics {
  total_startups: number
  total_runs: number
  completed_runs: number
  failed_runs: number
  partial_runs: number
  pending_runs: number
  avg_duration_ms: number | null
  maturity_distribution: Record<string, number>
  runs_today: number
  success_rate: number
}
