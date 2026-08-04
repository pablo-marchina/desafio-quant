import { requestJson } from "./client";
import type {
  ProductReadinessRead,
  ProductCapabilityRead,
  ProductSetupChecklistRead,
  StartupListItem,
  StartupRead,
  StartupCreatePayload,
  StartupUpdatePayload,
  AnalysisRunRead,
  AnalysisEvidenceBundle,
  ActionBriefRead,
  ReviewDecisionRead,
  OpportunityListResponse,
  ClaimListResponse,
  EvidenceCoverageRead,
  ActivationRecommendationRead,
  ActivationDossierRead,
  ActivationDossierMarkdownRead,
  ProductQualitySummaryRead,
  DiscoverySourceRead,
  DiscoveryRunRead,
  DiscoveryRunListResponse,
  DiscoveryCandidateRead,
  DiscoveryCandidateListResponse,
  ManualSeedRequest,
  ManualSeedResponse,
  UrlListRequest,
  UrlListResponse,
  PromoteCandidateResponse,
  ProductWorkflowRunCreate,
  ProductWorkflowRunRead,
  ProductWorkflowRunListResponse,
  ProductWorkflowNodeRunRead,
  OpportunityScoreRead,
  OpportunityScoreCreateResponse,
  RankedOpportunityRead,
  RankedOpportunityListResponse,
  ExportCreate,
  ExportRead,
  QualityReportRead,
  WorkflowReviewPayload,
  WorkflowReviewDecisionRead,
  RadarDashboardRead,
  RadarPopulateResponse,
} from "./types";

export function getProductReadiness(): Promise<ProductReadinessRead> {
  return requestJson<ProductReadinessRead>("/product/readiness");
}

export function getProductCapabilities(): Promise<ProductCapabilityRead[]> {
  return requestJson<ProductCapabilityRead[]>("/product/capabilities");
}

export function getProductSetupChecklist(): Promise<ProductSetupChecklistRead> {
  return requestJson<ProductSetupChecklistRead>("/product/setup-checklist");
}

export function listStartups(
  offset = 0,
  limit = 100,
): Promise<StartupListItem[]> {
  return requestJson<StartupListItem[]>(
    `/startups?offset=${offset}&limit=${limit}`,
  );
}

export function createStartup(
  payload: StartupCreatePayload,
): Promise<StartupRead> {
  return requestJson<StartupRead>("/startups", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function getStartup(id: string): Promise<StartupRead> {
  return requestJson<StartupRead>(`/startups/${id}`);
}

export function updateStartup(
  id: string,
  payload: StartupUpdatePayload,
): Promise<StartupRead> {
  return requestJson<StartupRead>(`/startups/${id}`, {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
}

export async function runMainProductPipelineForStartup(
  startupId: string,
): Promise<ProductWorkflowRunRead> {
  return createWorkflowRun({
    startup_id: startupId,
    discovery_candidate_id: null,
    analysis_run_id: null,
    use_rag: true,
  });
}

export function getAnalysisRun(id: string): Promise<AnalysisRunRead> {
  return requestJson<AnalysisRunRead>(`/analysis-runs/${id}`);
}

export function getAnalysisEvidenceBundle(
  id: string,
): Promise<AnalysisEvidenceBundle> {
  return requestJson<AnalysisEvidenceBundle>(
    `/analysis-runs/${id}/evidence-bundle`,
  );
}

export function getAnalysisRunBrief(
  id: string,
): Promise<ActionBriefRead> {
  return requestJson<ActionBriefRead>(`/analysis-runs/${id}/brief`);
}

export function listOpportunities(
  offset = 0,
  limit = 50,
): Promise<OpportunityListResponse> {
  return requestJson<OpportunityListResponse>(
    `/opportunities?offset=${offset}&limit=${limit}`,
  );
}

export function getAnalysisRunClaims(
  id: string,
): Promise<ClaimListResponse> {
  return requestJson<ClaimListResponse>(
    `/analysis-runs/${id}/claims?limit=500`,
  );
}

export function getEvidenceCoverage(
  id: string,
): Promise<EvidenceCoverageRead> {
  return requestJson<EvidenceCoverageRead>(
    `/analysis-runs/${id}/evidence-coverage`,
  );
}

export function getActivationRecommendations(
  id: string,
): Promise<{ items: ActivationRecommendationRead[]; total: number }> {
  return requestJson<{ items: ActivationRecommendationRead[]; total: number }>(
    `/analysis-runs/${id}/activation-recommendations`,
  );
}

export function generateActivationRecommendations(
  id: string,
): Promise<{ recommendations: ActivationRecommendationRead[]; total: number }> {
  return requestJson<{
    recommendations: ActivationRecommendationRead[];
    total: number;
  }>(`/analysis-runs/${id}/activation-recommendations/generate`, {
    method: "POST",
  });
}

export function getDossier(id: string): Promise<ActivationDossierRead> {
  return requestJson<ActivationDossierRead>(
    `/analysis-runs/${id}/dossier`,
  );
}

export function getDossierMarkdown(
  id: string,
): Promise<ActivationDossierMarkdownRead> {
  return requestJson<ActivationDossierMarkdownRead>(
    `/analysis-runs/${id}/dossier/markdown`,
  );
}

export function generateDossier(
  id: string,
  force = false,
): Promise<{ dossier: ActivationDossierRead; version: number; is_new: boolean }> {
  const query = force ? "?force=true" : "";
  return requestJson<{
    dossier: ActivationDossierRead;
    version: number;
    is_new: boolean;
  }>(`/analysis-runs/${id}/dossier${query}`, {
    method: "POST",
  });
}

export function getQualitySummary(
  id: string,
): Promise<ProductQualitySummaryRead> {
  return requestJson<ProductQualitySummaryRead>(
    `/analysis-runs/${id}/quality-summary`,
  );
}

export function createReview(
  analysisRunId: string,
  decision: string,
  reviewer: string,
  notes = "",
): Promise<ReviewDecisionRead> {
  return requestJson<ReviewDecisionRead>(
    `/analysis-runs/${analysisRunId}/review`,
    {
      method: "POST",
      body: JSON.stringify({ decision, reviewer, notes }),
    },
  );
}

export function listReviews(
  analysisRunId: string,
): Promise<ReviewDecisionRead[]> {
  return requestJson<ReviewDecisionRead[]>(
    `/analysis-runs/${analysisRunId}/reviews`,
  );
}

export function updateClaimReview(
  analysisRunId: string,
  claimId: string,
  reviewStatus: string,
  reviewerNotes = "",
): Promise<void> {
  return requestJson<void>(
    `/analysis-runs/${analysisRunId}/claims/${claimId}/review`,
    {
      method: "PATCH",
      body: JSON.stringify({
        review_status: reviewStatus,
        reviewer_notes: reviewerNotes,
      }),
    },
  );
}

// Discovery API
export function listDiscoverySources(): Promise<DiscoverySourceRead[]> {
  return requestJson<DiscoverySourceRead[]>("/discovery/sources");
}

export function discoverManualSeed(
  body: ManualSeedRequest,
): Promise<ManualSeedResponse> {
  return requestJson<ManualSeedResponse>("/discovery/manual-seed", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function discoverUrlList(
  body: UrlListRequest,
): Promise<UrlListResponse> {
  return requestJson<UrlListResponse>("/discovery/url-list", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function listDiscoveryRuns(
  offset = 0,
  limit = 50,
  status?: string,
): Promise<DiscoveryRunListResponse> {
  let path = `/discovery/runs?offset=${offset}&limit=${limit}`;
  if (status) path += `&status=${status}`;
  return requestJson<DiscoveryRunListResponse>(path);
}

export function getDiscoveryRun(
  runId: string,
): Promise<DiscoveryRunRead> {
  return requestJson<DiscoveryRunRead>(`/discovery/runs/${runId}`);
}

export function listDiscoveryCandidates(
  offset = 0,
  limit = 50,
  params?: {
    status?: string;
    source_id?: string;
    sector?: string;
    confidence_min?: number;
    has_website?: boolean;
    ai_native_signal?: boolean;
  },
): Promise<DiscoveryCandidateListResponse> {
  let path = `/discovery/candidates?offset=${offset}&limit=${limit}`;
  if (params?.status) path += `&status=${params.status}`;
  if (params?.source_id) path += `&source_id=${params.source_id}`;
  if (params?.sector) path += `&sector=${encodeURIComponent(params.sector)}`;
  if (params?.confidence_min != null) path += `&confidence_min=${params.confidence_min}`;
  if (params?.has_website != null) path += `&has_website=${params.has_website}`;
  if (params?.ai_native_signal != null) path += `&ai_native_signal=${params.ai_native_signal}`;
  return requestJson<DiscoveryCandidateListResponse>(path);
}

export function getDiscoveryCandidate(
  candidateId: string,
): Promise<DiscoveryCandidateRead> {
  return requestJson<DiscoveryCandidateRead>(
    `/discovery/candidates/${candidateId}`,
  );
}

export function promoteDiscoveryCandidate(
  candidateId: string,
): Promise<PromoteCandidateResponse> {
  return requestJson<PromoteCandidateResponse>(
    `/discovery/candidates/${candidateId}/promote`,
    { method: "POST" },
  );
}

// Workflow API
export function createWorkflowRun(
  body: ProductWorkflowRunCreate,
): Promise<ProductWorkflowRunRead> {
  return requestJson<ProductWorkflowRunRead>("/workflows/product-runs", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function listWorkflowRuns(
  offset = 0,
  limit = 50,
  status?: string,
  startup_id?: string,
): Promise<ProductWorkflowRunListResponse> {
  let path = `/workflows/product-runs?offset=${offset}&limit=${limit}`;
  if (status) path += `&status=${status}`;
  if (startup_id) path += `&startup_id=${startup_id}`;
  return requestJson<ProductWorkflowRunListResponse>(path);
}

export function getWorkflowRun(
  workflowId: string,
): Promise<ProductWorkflowRunRead> {
  return requestJson<ProductWorkflowRunRead>(
    `/workflows/product-runs/${workflowId}`,
  );
}

export function listWorkflowNodeRuns(
  workflowId: string,
  offset = 0,
  limit = 100,
): Promise<ProductWorkflowNodeRunRead[]> {
  return requestJson<ProductWorkflowNodeRunRead[]>(
    `/workflows/product-runs/${workflowId}/nodes?offset=${offset}&limit=${limit}`,
  );
}

export function getWorkflowForAnalysisRun(
  analysisRunId: string,
): Promise<ProductWorkflowRunRead | null> {
  return requestJson<ProductWorkflowRunRead | null>(
    `/analysis-runs/${analysisRunId}/workflow`,
  );
}

// Opportunity Score API
export function getOpportunityScore(
  analysisRunId: string,
): Promise<OpportunityScoreRead> {
  return requestJson<OpportunityScoreRead>(
    `/analysis-runs/${analysisRunId}/opportunity-score`,
  );
}

export function computeOpportunityScore(
  analysisRunId: string,
): Promise<OpportunityScoreCreateResponse> {
  return requestJson<OpportunityScoreCreateResponse>(
    `/analysis-runs/${analysisRunId}/opportunity-score`,
    { method: "POST" },
  );
}

export function listRankedOpportunities(
  offset = 0,
  limit = 50,
  params?: {
    min_score?: number;
    tier?: string;
    recommended_action?: string;
  },
): Promise<RankedOpportunityListResponse> {
  let path = `/opportunities/ranked?offset=${offset}&limit=${limit}`;
  if (params?.min_score != null) path += `&min_score=${params.min_score}`;
  if (params?.tier) path += `&tier=${encodeURIComponent(params.tier)}`;
  if (params?.recommended_action) path += `&recommended_action=${encodeURIComponent(params.recommended_action)}`;
  return requestJson<RankedOpportunityListResponse>(path);
}

// Export API
export function createExport(
  analysisRunId: string,
  exportType: string,
): Promise<ExportRead> {
  return requestJson<ExportRead>(
    `/analysis-runs/${analysisRunId}/exports`,
    {
      method: "POST",
      body: JSON.stringify({ export_type: exportType } satisfies ExportCreate),
    },
  );
}

export function getExport(
  exportId: string,
): Promise<ExportRead> {
  return requestJson<ExportRead>(`/exports/${exportId}`);
}

// Workflow Review API
export function getWorkflowReviewPayload(
  workflowId: string,
): Promise<WorkflowReviewPayload> {
  return requestJson<WorkflowReviewPayload>(
    `/workflows/${workflowId}/review-payload`,
  );
}

export function submitWorkflowReview(
  workflowId: string,
  decision: string,
  reviewer: string,
  notes = "",
): Promise<WorkflowReviewDecisionRead> {
  return requestJson<WorkflowReviewDecisionRead>(
    `/workflows/${workflowId}/review`,
    {
      method: "POST",
      body: JSON.stringify({ decision, reviewer, notes }),
    },
  );
}

// Quality Report API
export function getQualityReport(): Promise<QualityReportRead> {
  return requestJson<QualityReportRead>("/product/quality-report");
}


// Unified Radar Dashboard API
export function getRadarDashboard(limit = 100): Promise<RadarDashboardRead> {
  return requestJson<RadarDashboardRead>(`/radar/dashboard?limit=${limit}`);
}

export function populateRadarDashboard(
  limit = 100,
  sourceLimit = 4,
  pipelineLimit = 5,
  runPipeline = true,
  forceRerun = false,
): Promise<RadarPopulateResponse> {
  const params = new URLSearchParams({
    limit: String(limit),
    source_limit: String(sourceLimit),
    pipeline_limit: String(pipelineLimit),
    run_pipeline: String(runPipeline),
    force_rerun: String(forceRerun),
  });
  return requestJson<RadarPopulateResponse>(`/radar/dashboard/populate?${params.toString()}`, {
    method: "POST",
  });
}
