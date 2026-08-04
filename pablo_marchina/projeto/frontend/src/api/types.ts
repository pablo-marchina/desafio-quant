export type JsonValue = string | number | boolean | null | JsonValue[] | { [key: string]: JsonValue };

export interface StartupListItem {
  id: string;
  name: string;
  website: string;
  sector: string;
  status: string;
  latest_analysis_run_id: string | null;
  latest_analysis_status: string | null;
  review_decision: string | null;
  created_at: string;
  updated_at: string;
}

export interface StartupEvidenceRead {
  id: string;
  claim: string;
  source_url: string;
  source_type: string;
  quote_or_evidence: string;
  confidence: string;
  evidence_kind: string;
  collected_at: string;
  metadata: Record<string, JsonValue>;
}

export interface StartupRead {
  id: string;
  name: string;
  normalized_name: string;
  website: string;
  country: string;
  sector: string;
  description: string;
  product_summary: string;
  status: string;
  tags: string[];
  evidence: StartupEvidenceRead[];
  created_at: string;
  updated_at: string;
}

export interface ReadinessCheckRead {
  code: string;
  severity: string;
  status: string;
  user_message: string;
  internal_detail: string;
  recommended_action: string;
  metadata: Record<string, JsonValue>;
  observed_at: string;
}

export interface AnalysisRunRead {
  id: string;
  startup_id: string;
  status: string;
  error_message: string | null;
  degraded_reason: string | null;
  started_at: string | null;
  completed_at: string | null;
  pipeline_version: string;
  corpus_version: string | null;
  input_snapshot: Record<string, JsonValue>;
  output_snapshot: Record<string, JsonValue>;
  scores: Record<string, JsonValue>[];
  gaps: Record<string, JsonValue>[];
  nvidia_mappings: Record<string, JsonValue>[];
  readiness_checks: ReadinessCheckRead[];
  action_brief_id: string | null;
  claim_summary: ClaimSummaryRead | null;
  dossier_summary: ActivationDossierSummaryRead | null;
  created_at: string;
  updated_at: string;
}

export interface ActionBriefRead {
  id: string;
  analysis_run_id: string;
  version: number;
  schema_version: string;
  brief_json: Record<string, JsonValue>;
  brief_markdown: string;
  is_latest: boolean;
  created_at: string;
  updated_at: string;
}

export interface ReviewDecisionRead {
  id: string;
  analysis_run_id: string;
  decision: string;
  reviewer: string;
  notes: string;
  metadata: Record<string, JsonValue>;
  created_at: string;
  updated_at: string;
}

export interface OpportunityListItem {
  startup_id: string;
  startup_name: string;
  latest_analysis_run_id: string | null;
  recommended_motion: string | null;
  inception_fit_score: number | null;
  ai_native_score: number | null;
  production_readiness_score: number | null;
  composite_score: number | null;
  confidence: string | null;
  status: string;
  top_gaps: string[];
  top_nvidia_mappings: string[];
  degraded_count: number;
  last_analyzed_at: string | null;
  review_status: string | null;
  unsupported_claim_count: number | null;
  evidence_coverage: number | null;
  top_activation_playbook: string | null;
  activation_confidence: string | null;
  activation_next_step: string | null;
  technical_experiment_summary: string | null;
  dossier_available: boolean;
  latest_dossier_id: string | null;
  export_readiness_score: number | null;
  review_readiness_score: number | null;
}

export interface OpportunityListResponse {
  items: OpportunityListItem[];
  total: number;
  offset: number;
  limit: number;
}

export interface ClaimRead {
  id: string;
  startup_id: string;
  analysis_run_id: string;
  claim_text: string;
  claim_type: string;
  support_level: string;
  confidence: string;
  evidence_refs: Record<string, JsonValue>[];
  used_in_score: boolean;
  used_in_gap: boolean;
  used_in_mapping: boolean;
  used_in_brief: boolean;
  review_status: string;
  reviewer_notes: string;
  metadata: Record<string, JsonValue>;
  created_at: string;
  updated_at: string;
}

export interface ClaimListResponse {
  items: ClaimRead[];
  total: number;
  offset: number;
  limit: number;
}

export interface EvidenceCoverageRead {
  total_claims: number;
  supported_claims: number;
  unsupported_claims: number;
  weak_claims: number;
  critical_claims: number;
  critical_supported_claims: number;
  evidence_coverage: number;
  unsupported_claim_rate: number;
  avg_claim_confidence: number;
}

export interface ClaimSummaryRead {
  total_claims: number;
  supported_claims: number;
  unsupported_claims: number;
  evidence_coverage: number;
}

export interface ActivationRecommendationRead {
  id: string;
  analysis_run_id: string;
  playbook_id: string;
  playbook_name: string;
  matched_gap_types: string[];
  matched_claim_ids: string[];
  nvidia_technologies: string[];
  technical_experiment: string;
  success_metrics: string[];
  recommended_motion: string;
  priority: number;
  confidence: string;
  reasoning: string;
  evidence_refs: Record<string, JsonValue>[];
  risks: string[];
  next_step: string;
  created_at: string | null;
  updated_at: string | null;
}

export interface ActivationDossierRead {
  id: string;
  analysis_run_id: string;
  version: number;
  schema_version: string;
  dossier_json: Record<string, JsonValue>;
  dossier_markdown: string;
  is_latest: boolean;
  evidence_coverage: number;
  unsupported_claim_count: number;
  top_activation_playbook_id: string | null;
  recommended_motion: string;
  review_status: string | null;
  created_at: string;
  updated_at: string;
}

export interface ActivationDossierMarkdownRead {
  markdown: string;
  dossier_id: string;
  version: number;
}

export interface ActivationDossierSummaryRead {
  dossier_id: string | null;
  dossier_version: number | null;
  dossier_available: boolean;
  evidence_coverage: number | null;
  unsupported_claim_count: number | null;
  top_activation_playbook_id: string | null;
  recommended_motion: string | null;
  review_status: string | null;
}

export interface AnalysisEvidenceBundle {
  analysis_run_id: string;
  startup_id: string;
  status: string;
  readiness: string;
  confidence: string;
  evidence_coverage: EvidenceCoverageRead;
  claims: Record<string, ClaimRead[]>;
  recommendations: ActivationRecommendationRead[];
  dossier: ActivationDossierRead | null;
  readiness_checks: ReadinessCheckRead[];
  missing_evidence: Record<string, JsonValue>[];
  contradictions: Record<string, JsonValue>[];
  degraded_checks: ReadinessCheckRead[];
  rag_support: Record<string, JsonValue>;
  trust_freshness: Record<string, JsonValue>;
  lineage: Record<string, JsonValue>;
  alternatives_lost: Record<string, JsonValue>[];
}

export interface ProductCapabilityRead {
  capability_id: string;
  name: string;
  description: string;
  category: string;
  required: boolean;
  status: string;
  status_reason: string;
  required_env_vars: string[];
  optional_env_vars: string[];
  required_extras: string[];
  required_services: string[];
  setup_instructions: string;
  failure_mode: string;
  user_visible: boolean;
  documentation_ref: string;
}

export interface ProductConfigurationItemRead {
  key: string;
  description: string;
  required: boolean;
  secret: boolean;
  default: string;
  current_value: string | null;
  is_set: boolean;
}

export interface ProductSetupChecklistItem {
  key: string;
  description: string;
  is_set: boolean;
  required: boolean;
}

export interface ProductSetupChecklistRead {
  items: ProductSetupChecklistItem[];
  total: number;
  completed: number;
  pending: number;
}

export interface ProductReadinessRead {
  ready: boolean;
  blocking_missing_config: Record<string, JsonValue>[];
  optional_missing_config: Record<string, JsonValue>[];
  unavailable_capabilities: Record<string, JsonValue>[];
  degraded_capabilities: Record<string, JsonValue>[];
  setup_checklist: ProductSetupChecklistItem[];
  user_messages: string[];
}

export interface ProductQualitySummaryRead {
  analysis_run_id: string;
  quality_run_id: string | null;
  status: string | null;
  evaluator_version: string | null;
  overall_status: string;
  total_metrics: number;
  passed_metrics: number;
  failed_metrics: number;
  export_readiness_score: number | null;
  review_readiness_score: number | null;
  degraded_reason: string | null;
  metrics: Record<string, Record<string, JsonValue>>;
}

export interface ProductHealthRead {
  status: string;
  app_mode: string;
  product_persistence_enabled: boolean;
  database_available: boolean;
  schema_ready: boolean;
  database_url: string;
  error: string | null;
}

export interface StartupCreatePayload {
  name: string;
  website: string;
  sector: string;
  description?: string;
  status?: string;
}

export interface StartupUpdatePayload {
  name?: string;
  website?: string;
  sector?: string;
}

// Discovery types
export interface DiscoverySourceRead {
  source_id: string;
  name: string;
  source_type: string;
  base_url: string;
  country_scope: string;
  sector_scope: string;
  allowed: boolean;
  requires_api_key: boolean;
  rate_limit_hint: string;
  collection_method: string;
  robots_or_terms_note: string;
  enabled_by_default: boolean;
  notes: string;
  usable: boolean;
}

export interface DiscoveryRunRead {
  id: string;
  source_id: string | null;
  status: string;
  error_message: string | null;
  results_count: number;
  candidates_created: number;
  duplicates_found: number;
  query_json: Record<string, JsonValue>;
  metadata_json: Record<string, JsonValue>;
  started_at: string | null;
  completed_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface DiscoveryRunListResponse {
  items: DiscoveryRunRead[];
  total: number;
  offset: number;
  limit: number;
}

export interface DiscoveryCandidateRead {
  id: string;
  discovery_run_id: string | null;
  source_id: string;
  discovered_name: string;
  normalized_name: string;
  website: string;
  country: string;
  sector: string;
  description: string;
  source_url: string;
  raw_text_excerpt: string;
  ai_native_signals_json: Record<string, JsonValue>;
  evidence_refs_json: Record<string, JsonValue>[];
  confidence: string;
  status: string;
  promoted_startup_id: string | null;
  metadata_json: Record<string, JsonValue>;
  created_at: string;
  updated_at: string;
}

export interface DiscoveryCandidateListResponse {
  items: DiscoveryCandidateRead[];
  total: number;
  offset: number;
  limit: number;
}

export interface ManualSeedEntry {
  name: string;
  website?: string;
  sector?: string;
  description?: string;
  country?: string;
}

export interface ManualSeedRequest {
  entries: ManualSeedEntry[];
}

export interface ManualSeedResponse {
  discovery_run_id: string;
  status: string;
  total_entries: number;
  candidates_created: number;
  duplicates_found: number;
}

export interface UrlListRequest {
  urls: string[];
}

export interface UrlListResponse {
  discovery_run_id: string;
  status: string;
  total_urls: number;
  candidates_created: number;
  duplicates_found: number;
  errors: string[];
}

export interface PromoteCandidateResponse {
  candidate_id: string;
  startup_id: string;
  status: string;
}

// Workflow Review types
export interface WorkflowReviewPayload {
  run_id: string;
  startup_id: string | null;
  reason: string;
  severity: string;
  failed_quality_checks: string[];
  blockers: string[];
  expected_human_actions: string[];
  resumable: boolean;
  interrupt_enabled: boolean;
}

export interface WorkflowReviewDecisionCreate {
  decision: string;
  reviewer: string;
  notes: string;
}

export interface WorkflowReviewDecisionRead {
  workflow_id: string;
  decision: string;
  reviewer: string;
  notes: string;
  created_at: string;
}

// Workflow types
export interface ProductWorkflowRunCreate {
  startup_id?: string | null;
  discovery_candidate_id?: string | null;
  analysis_run_id?: string | null;
  use_rag?: boolean;
}

export interface ProductWorkflowNodeRunRead {
  id: string;
  workflow_run_id: string;
  node_name: string;
  status: string;
  started_at: string | null;
  completed_at: string | null;
  error_message: string | null;
  retry_count: number;
  created_at: string;
}

export interface ProductWorkflowRunRead {
  id: string;
  startup_id: string | null;
  discovery_candidate_id: string | null;
  analysis_run_id: string | null;
  status: string;
  current_node: string;
  graph_version: string;
  error_message: string | null;
  degraded_reason: string | null;
  state: Record<string, JsonValue>;
  nodes: ProductWorkflowNodeRunRead[];
  started_at: string | null;
  completed_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface ProductWorkflowRunListResponse {
  items: ProductWorkflowRunRead[];
  total: number;
  offset: number;
  limit: number;
}

// Opportunity Score types
export interface OpportunityScoreComponentRead {
  name: string;
  value: number | null;
  weight: number;
}

export interface OpportunityScorePenaltyRead {
  type: string;
  value: number;
  detail: string;
}

export interface OpportunityScoreExplainRead {
  components: OpportunityScoreComponentRead[];
  missing_components: string[];
  penalties: OpportunityScorePenaltyRead[];
  penalty_total: number;
  formula_summary: string;
}

export interface OpportunityScoreRead {
  id: string;
  analysis_run_id: string;
  score_version: number;
  opportunity_score: number;
  score_tier: string;
  components: Record<string, JsonValue>;
  penalties: Record<string, JsonValue>[];
  penalty_total: number;
  evidence_refs: Record<string, JsonValue>[];
  recommended_action: string;
  reasoning: string;
  created_at: string;
  updated_at: string;
}

export interface OpportunityScoreCreateResponse {
  analysis_run_id: string;
  opportunity_score: number;
  score_tier: string;
  evidence_ref_count: number;
  recommended_action: string;
  reasoning: string;
  explanation: OpportunityScoreExplainRead;
}

export interface RankedOpportunityRead {
  startup_id: string;
  startup_name: string;
  sector: string;
  latest_analysis_run_id: string;
  opportunity_score: number;
  score_tier: string;
  components: Record<string, JsonValue>;
  penalties: Record<string, JsonValue>[];
  penalty_total: number;
  evidence_ref_count: number;
  recommended_action: string;
  reasoning: string;
  score_version: number;
  created_at: string | null;
}

export interface RankedOpportunityListResponse {
  items: RankedOpportunityRead[];
  total: number;
  offset: number;
  limit: number;
}

// Export types
export interface ExportCreate {
  export_type: string;
}

export interface ExportRead {
  id: string;
  analysis_run_id: string;
  action_brief_id: string | null;
  export_type: string;
  status: string;
  storage_path: string;
  content_hash: string;
  error_message: string | null;
  content?: string | Record<string, JsonValue> | null;
  created_at: string;
  updated_at: string;
}

// Quality Report
export interface QualityThresholdRead {
  threshold?: number | null;
  operator?: string | null;
  severity?: string | null;
}

export interface QualityReportRead {
  status: string;
  summary: string;
  metrics: Record<string, JsonValue>;
  thresholds?: Record<string, QualityThresholdRead>;
  last_updated: string | null;
}


// Unified Radar Dashboard
export interface RadarDashboardRecommendation {
  playbook_name?: string | null;
  priority?: number | null;
  confidence?: string | null;
  nvidia_technologies: string[];
  recommended_motion?: string | null;
  next_step?: string | null;
  reasoning?: string | null;
  success_metrics: string[];
}

export interface RadarDashboardItem {
  row_type: string;
  candidate_id?: string | null;
  startup_id?: string | null;
  company_name: string;
  website?: string | null;
  sector?: string | null;
  country?: string | null;
  analysis_run_id?: string | null;
  analysis_status?: string | null;
  recommendation_status?: string | null;
  recommended_motion?: string | null;
  opportunity_score?: number | null;
  score_tier?: string | null;
  confidence?: string | null;
  evidence_coverage?: number | null;
  unsupported_claim_count?: number | null;
  top_gaps: string[];
  top_nvidia_technologies: string[];
  activation_recommendations: RadarDashboardRecommendation[];
  source_count: number;
  information: Record<string, JsonValue>;
}

export interface RadarDashboardRead {
  items: RadarDashboardItem[];
  total: number;
  analyzed_total: number;
  limit: number;
}

export interface RadarPipelineResult {
  startup_id?: string;
  analysis_run_id?: string | null;
  workflow_id?: string | null;
  status: string;
  error?: string;
}

export interface RadarPopulateResponse {
  status: string;
  message: string;
  discovery_results: Record<string, JsonValue>[];
  promoted_candidates: Record<string, JsonValue>[];
  pipeline_results: RadarPipelineResult[];
  dashboard: RadarDashboardRead;
  discovery_queue?: Record<string, JsonValue>[];
  rejected_entities?: Record<string, JsonValue>[];
}
