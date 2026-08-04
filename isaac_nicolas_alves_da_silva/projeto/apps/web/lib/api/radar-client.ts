import type {
  Briefing,
  CreateUrlIngestionJobInput,
  DiscoveryRun,
  ListStartupsParams,
  ListUrlIngestionJobsParams,
  MaturityDistribution,
  RagAnswer,
  Recommendation,
  ReviewInput,
  Startup,
  StartupEvidence,
  StartupPage,
  TechnologyStats,
  UrlIngestionJob,
  UrlIngestionJobPage,
} from "./radar-types";

export class RadarApiError extends Error {
  constructor(message: string, public readonly status: number) { super(message); }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, {
    ...init,
    headers: { "content-type": "application/json", ...init?.headers },
  });
  if (!response.ok) {
    const body = await response.json().catch(() => null) as { detail?: string } | null;
    throw new RadarApiError(body?.detail ?? "Nao foi possivel comunicar com a API.", response.status);
  }
  return response.json() as Promise<T>;
}

function buildQueryString(params: Record<string, unknown>): string {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== "") search.set(key, String(value));
  }
  return search.size ? `?${search.toString()}` : "";
}

export function createUrlIngestionJob(input: CreateUrlIngestionJobInput) {
  return request<UrlIngestionJob>("/api/radar/url-ingestion-jobs", { method: "POST", body: JSON.stringify(input) });
}

export function getUrlIngestionJob(jobId: string) {
  return request<UrlIngestionJob>(`/api/radar/url-ingestion-jobs/${jobId}`);
}

export function listUrlIngestionJobs(params: ListUrlIngestionJobsParams = {}) {
  return request<UrlIngestionJobPage>(`/api/radar/url-ingestion-jobs${buildQueryString(params)}`);
}

export function getStartup(startupId: string) {
  return request<Startup>(`/api/radar/startups/${startupId}`);
}

export function listStartups(params: ListStartupsParams = {}) {
  return request<StartupPage>(`/api/radar/startups${buildQueryString(params)}`);
}

export function getStartupEvidences(startupId: string) {
  return request<StartupEvidence[]>(`/api/radar/startups/${startupId}/evidences`);
}

export function listRecommendations(startupId: string) {
  return request<Recommendation[]>(`/api/radar/recommendations?startup_id=${encodeURIComponent(startupId)}`);
}

export function reviewRecommendation(recommendationId: string, input: ReviewInput) {
  return request<Recommendation>(`/api/radar/recommendations/${recommendationId}/review`, {
    method: "PATCH",
    body: JSON.stringify(input),
  });
}

export function listBriefings(startupId: string) {
  return request<Briefing[]>(`/api/radar/briefings?startup_id=${encodeURIComponent(startupId)}`);
}

export function reviewBriefing(briefingId: string, input: ReviewInput) {
  return request<Briefing>(`/api/radar/briefings/${briefingId}/review`, {
    method: "PATCH",
    body: JSON.stringify(input),
  });
}

export function askNvidiaKnowledge(query: string) {
  return request<RagAnswer>("/api/radar/rag/answer", {
    method: "POST",
    body: JSON.stringify({ query, source_type: "nvidia_knowledge" }),
  });
}

export function getPortfolioStats() {
  return request<MaturityDistribution>("/api/radar/startups/stats");
}

export function getTechnologyStats(limit = 10) {
  return request<TechnologyStats>(`/api/radar/recommendations/stats?limit=${limit}`);
}

export async function createBatchUrlIngestionJobs(urls: string[]) {
  const results = await Promise.allSettled(
    urls.map((url) => createUrlIngestionJob({ url }))
  );
  return results.map((r, i) => ({
    url: urls[i],
    job: r.status === "fulfilled" ? r.value : null,
    error: r.status === "rejected" ? (r.reason as Error).message : null,
  }));
}

export function createDiscoveryRun() {
  return request<DiscoveryRun>("/api/radar/startup-discovery/runs", { method: "POST", body: "{}" });
}

export function getDiscoveryRun(runId: string) {
  return request<DiscoveryRun>(`/api/radar/startup-discovery/runs/${runId}`);
}

export async function refreshStartupAnalysis(startupId: string) {
  await request<Recommendation[]>("/api/radar/recommendations", {
    method: "POST",
    body: JSON.stringify({ startup_id: startupId }),
  });
  return request<Briefing>("/api/radar/briefings", {
    method: "POST",
    body: JSON.stringify({ startup_id: startupId }),
  });
}
