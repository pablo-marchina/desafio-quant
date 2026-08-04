const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

export interface ApiError {
  endpoint: string;
  status: number;
  message: string;
  code?: string;
}

async function request<T>(endpoint: string, options?: RequestInit): Promise<T> {
  const url = `${API_BASE}${endpoint}`;
  try {
    const res = await fetch(url, {
      ...options,
      headers: {
        "Content-Type": "application/json",
        ...options?.headers,
      },
    });
    if (!res.ok) {
      const body = await res.text();
      throw {
        endpoint,
        status: res.status,
        message: body || res.statusText,
      } satisfies ApiError;
    }
    return res.json();
  } catch (err: unknown) {
    if (err && typeof err === "object" && "endpoint" in err) {
      throw err;
    }
    const e = err as Error;
    throw {
      endpoint,
      status: 0,
      message: e.message,
      code: e.cause ? String(e.cause) : undefined,
    } satisfies ApiError;
  }
}

export interface HealthResponse {
  status: string;
}

export interface PreflightResponse {
  status: string;
  search_provider: string;
  page_provider: string;
  external_providers_enabled: boolean;
  llm_provider: string;
  llm_ready: boolean;
  missing_credentials: string[];
  messages: string[];
}

export interface RunSummary {
  id: number;
  query: string;
  startup_id: string | null;
  status: string;
  created_at: string;
  completed_at: string | null;
}

export interface RecommendationRecord {
  id: string;
  run_id: number;
  technology: string;
  target_gap: string;
  technical_justification: string;
  business_justification: string;
  priority: string;
  implementation_complexity: string;
  suggested_next_action: string;
  startup_evidence_ids: string;
  nvidia_knowledge_ids: string;
}

export interface PipelineStepRecord {
  step_key: string;
  status: string;
  detail: string | null;
  error_message: string | null;
  started_at: string | null;
  completed_at: string | null;
}
export interface ValidationRecord {
  has_minimum_evidence: boolean;
  source_quality: string;
  supporting_evidence_ids: string[];
  conflicts: string[];
  caveats: string[];
  requires_human_review: boolean;
}

export interface BriefingSectionRecord {
  title: string;
  content: string;
  evidence_ids?: string[];
}

export interface BriefingRecord {
  id: string;
  title: string;
  startup_name: string;
  startup_sector: string | null;
  generated_at: string;
  classification_label: string;
  classification_confidence: number;
  classification_rationale: string;
  executive_summary: string;
  ai_maturity_diagnosis: BriefingSectionRecord;
  evidence_summary: BriefingSectionRecord;
  technical_gaps: BriefingSectionRecord;
  nvidia_recommendations_section: BriefingSectionRecord;
  caveats: string[];
  suggested_approach: BriefingSectionRecord;
  recommendations: RecommendationRecord[];
}

export interface RunDetail {
  id: number;
  query: string;
  startup_id: string | null;
  status: string;
  created_at: string;
  completed_at: string | null;
  recommendations: RecommendationRecord[];
  steps: PipelineStepRecord[];
  validation: ValidationRecord | null;
  briefing: BriefingRecord | null;
}

export interface StartupRecord {
  id: string;
  name: string;
  sector: string | null;
  product: string | null;
  description: string | null;
  founders: string;
  customers: string;
  funding: string | null;
  cited_technologies: string;
  ai_usage_summary: string | null;
  classification_label: string | null;
  classification_confidence: number | null;
  classification_rationale: string | null;
  radar_score?: number;
  evidence_count?: number;
  recommendation_count?: number;
  created_at: string;
  updated_at: string;
}

export interface SourceDocumentRecord {
  id: string;
  run_id: number;
  url: string;
  domain: string;
  source_type: string;
  title: string | null;
  text: string;
  retrieved_at: string;
  collection_method: string;
  claim_count: number;
  average_claim_confidence: number | null;
}

export interface EvidenceClaimRecord {
  id: string;
  run_id: number;
  source_document_id: string;
  text: string;
  claim_type: string;
  confidence: number;
}

export interface SubmitRunPayload {
  query: string;
  startupName?: string;
}

export interface SubmitRunResponse {
  run_id: number;
  status: string;
}

export function fetchHealth(): Promise<HealthResponse> {
  return request<HealthResponse>("/health");
}

export function fetchPreflight(): Promise<PreflightResponse> {
  return request<PreflightResponse>("/providers/preflight");
}

export function fetchRuns(): Promise<RunSummary[]> {
  return request<RunSummary[]>("/runs");
}

export function fetchRunById(id: number): Promise<RunDetail> {
  return request<RunDetail>(`/runs/${id}`);
}

export function fetchStartups(): Promise<StartupRecord[]> {
  return request<StartupRecord[]>("/startups");
}

export function fetchStartupById(id: string): Promise<StartupRecord> {
  return request<StartupRecord>(`/startups/${id}`);
}

export function fetchSources(): Promise<SourceDocumentRecord[]> {
  return request<SourceDocumentRecord[]>("/sources");
}

export function fetchRunSources(id: number): Promise<SourceDocumentRecord[]> {
  return request<SourceDocumentRecord[]>(`/runs/${id}/sources`);
}

export function fetchRunClaims(id: number): Promise<EvidenceClaimRecord[]> {
  return request<EvidenceClaimRecord[]>(`/runs/${id}/claims`);
}

export interface ContactSource {
  source_url: string;
  found_at: string;
}

export interface ContactEntry {
  value: string;
  confidence: number;
  sources: ContactSource[];
}

export interface CompanyContact {
  startup_id: string;
  startup_name: string;
  emails: ContactEntry[];
  phones: ContactEntry[];
  linkedin_urls: ContactEntry[];
  addresses: ContactEntry[];
  primary_name: string | null;
  primary_role: string | null;
  raw_text_snippets: string[];
  collected_at: string | null;
}

export function discoverStartupContacts(
  id: string,
): Promise<CompanyContact> {
  return request<CompanyContact>(`/startups/${id}/contacts`, {
    method: "POST",
  });
}

export function fetchStartupContacts(
  id: string,
): Promise<CompanyContact> {
  return request<CompanyContact>(`/startups/${id}/contacts`);
}

export function submitRun(
  payload: SubmitRunPayload,
): Promise<SubmitRunResponse> {
  const startupName = payload.startupName?.trim();
  return request<SubmitRunResponse>("/runs", {
    method: "POST",
    body: JSON.stringify({
      query: payload.query,
      ...(startupName ? { startup_name: startupName } : {}),
    }),
  });
}
