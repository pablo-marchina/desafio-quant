export type UrlIngestionStatus = "pending" | "scraping" | "ingesting" | "embedding" | "analyzing" | "completed" | "failed";

export type UrlIngestionJob = {
  id: string;
  url: string;
  source_type: string;
  status: UrlIngestionStatus;
  scraping_job_id: string | null;
  scraping_result_id: string | null;
  ingestion_job_id: string | null;
  document_id: string | null;
  embedding_job_id: string | null;
  startup_id: string | null;
  parent_job_id: string | null;
  enrichment_round: number;
  recommendation_count: number | null;
  briefing_id: string | null;
  error_message: string | null;
  created_at: string;
  started_at: string | null;
  finished_at: string | null;
};

export type CreateUrlIngestionJobInput = { url: string; startup_id?: string };

export type UrlIngestionJobPage = {
  items: UrlIngestionJob[];
  total: number;
  page: number;
  page_size: number;
};

export type ListUrlIngestionJobsParams = {
  page?: number;
  page_size?: number;
  status?: UrlIngestionStatus | "";
  source_type?: string;
};

export type DiscoveryRunStatus = "pending" | "running" | "completed" | "failed";

export type DiscoveryRun = {
  id: string;
  status: DiscoveryRunStatus;
  hubs_processed: number;
  urls_found: number;
  jobs_submitted: number;
  error_message: string | null;
  created_at: string;
  completed_at: string | null;
};

export type StartupAIProfile = {
  ai_workload_type: string;
  model_type: string;
  data_modality: string;
  deployment_stage: string;
  infra_environment: string;
  gpu_need: string;
  latency_requirement: string;
  scale_signal: string | null;
  current_tools: string[];
  business_goal: string | null;
};

export type Startup = {
  id: string;
  name: string;
  website_url: string | null;
  description: string | null;
  sector: string | null;
  country: string | null;
  ai_maturity_level: string | null;
  classification_reason: string | null;
  classified_at: string | null;
  founders: string[];
  funding_stage: string | null;
  funding_amount_usd: number | null;
  customers: string[];
  ai_profile: StartupAIProfile | null;
  field_confidence: Record<string, number>;
  field_evidence_ids: Record<string, string[]>;
  created_at: string;
  updated_at: string;
};

export type StartupPage = {
  items: Startup[];
  total: number;
  page: number;
  page_size: number;
};

export type ListStartupsParams = {
  page?: number;
  page_size?: number;
  query?: string;
  sector?: string;
  country?: string;
  ai_maturity_level?: string;
};

export type StartupEvidence = {
  id: string;
  startup_id: string;
  scraping_result_id: string;
  source_url: string;
  evidence_type: string;
  title: string | null;
  confidence_score: number | null;
  notes: string | null;
  created_at: string;
};

export type Recommendation = {
  id: string;
  startup_id: string;
  technology_slug: string;
  technology_name: string;
  category: string;
  score: number;
  confidence: number;
  complexity: string;
  priority: number;
  justification: string;
  matched_keywords: string[];
  evidence_ids: string[];
  signal_origins: string[];
  missing_signals: string[];
  nivel: "forte" | "moderada" | "exploratoria";
  faltando: string[];
  review_status: "pending" | "approved" | "rejected";
  review_comment: string | null;
  reviewed_by: string | null;
  reviewed_at: string | null;
  created_at: string;
};

export type Briefing = {
  id: string;
  startup_id: string;
  content: string;
  review_status: "pending" | "approved" | "rejected";
  review_comment: string | null;
  reviewed_by: string | null;
  reviewed_at: string | null;
  generated_at: string;
};

export type ReviewInput = {
  status: "pending" | "approved" | "rejected";
  comment?: string;
  reviewed_by?: string;
};

export type MaturityDistribution = {
  ai_native: number;
  ai_enabled: number;
  non_ai: number;
  unclassified: number;
  total: number;
};

export type TechnologyStat = {
  technology_slug: string;
  technology_name: string;
  count: number;
};

export type TechnologyStats = {
  items: TechnologyStat[];
};

export type RagCitation = {
  chunk_id: string;
  document_id: string;
  source_url: string;
  quote: string;
};

export type RagEvidenceChunk = {
  chunk_id: string;
  document_id: string;
  source_url: string;
  source_type: string;
  text: string;
  score: number;
};

export type RagAnswer = {
  query: string;
  answer: string;
  citations: RagCitation[];
  evidences: RagEvidenceChunk[];
};
