import type {
  DashboardSummary,
  JobResponse,
  Startup,
  StartupList,
  StartupQuery
} from "@/lib/types";

const API_URL = (process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000").replace(
  /\/$/,
  ""
);

export class ApiError extends Error {
  constructor(
    message: string,
    public status?: number
  ) {
    super(message);
  }
}

async function request<T>(
  path: string,
  signal?: AbortSignal,
  init?: RequestInit
): Promise<T> {
  let response: Response;
  const controller = new AbortController();
  let timedOut = false;
  const timeout = setTimeout(() => {
    timedOut = true;
    controller.abort();
  }, 20_000);
  const abort = () => controller.abort();
  signal?.addEventListener("abort", abort, { once: true });
  try {
    response = await fetch(`${API_URL}${path}`, {
      ...init,
      signal: controller.signal,
      headers: { Accept: "application/json", ...init?.headers }
    });
  } catch (error) {
    if (signal?.aborted && !timedOut) throw error;
    if (timedOut) {
      throw new ApiError(
        "A API nao respondeu em 20 segundos. Confirme se o backend terminou de processar e tente novamente."
      );
    }
    throw new ApiError(
      "Não foi possível conectar à API. Confirme se o FastAPI está ativo."
    );
  } finally {
    clearTimeout(timeout);
    signal?.removeEventListener("abort", abort);
  }

  if (!response.ok) {
    let detail = `A API respondeu com o status ${response.status}.`;
    try {
      const body = (await response.json()) as { detail?: string };
      if (body.detail) detail = body.detail;
    } catch {
      // Keep the status-based message when the API does not return JSON.
    }
    throw new ApiError(detail, response.status);
  }

  return response.json() as Promise<T>;
}

export function getDashboardSummary(signal?: AbortSignal) {
  return request<DashboardSummary>("/dashboard/summary", signal);
}

export function getStartups(query: StartupQuery, signal?: AbortSignal) {
  const params = new URLSearchParams({
    page: String(query.page),
    page_size: String(query.pageSize)
  });
  if (query.search) params.set("search", query.search);
  if (query.validationStatus) {
    params.set("validation_status", query.validationStatus);
  }
  if (query.hasNvidiaRecommendation) {
    params.set("has_nvidia_recommendation", "true");
  }
  return request<StartupList>(`/startups?${params}`, signal);
}

export async function getStartup(id: string, signal?: AbortSignal) {
  const response = await request<{ startup: Startup }>(
    `/startups/${encodeURIComponent(id)}`,
    signal
  );
  return response.startup;
}

export function startCompanyRegistrationEnrichment(startupId: string) {
  return request<{ job_id: string; status: string }>(
    `/startups/${encodeURIComponent(startupId)}/company-registration`,
    undefined,
    { method: "POST" }
  );
}

export async function updateStartup(
  startupId: string,
  changes: Partial<Startup>
) {
  const response = await request<{ startup: Startup }>(
    `/startups/${encodeURIComponent(startupId)}`,
    undefined,
    {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(changes)
    }
  );
  return response.startup;
}

export function startNvidiaRecommendation(startupId: string, need: string) {
  return request<{ job_id: string; status: string }>(
    `/startups/${encodeURIComponent(startupId)}/nvidia-recommendation`,
    undefined,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ need })
    }
  );
}

export function startCompetitiveAnalysis(startupId: string, question = "") {
  return request<{ job_id: string; status: string }>(
    `/startups/${encodeURIComponent(startupId)}/competitive-analysis`,
    undefined,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question })
    }
  );
}

export function startActionReport(
  startupId: string,
  objective = "",
  context?: Record<string, unknown>
) {
  return request<{ job_id: string; status: string }>(
    `/startups/${encodeURIComponent(startupId)}/action-report`,
    undefined,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ objective, context })
    }
  );
}

export function startTechnologyIntelligence(startupId: string) {
  const controller = new AbortController();
  const timeout = window.setTimeout(() => controller.abort(), 15_000);
  return request<{ job_id: string; status: string }>(
    `/startups/${encodeURIComponent(startupId)}/technology-intelligence`,
    controller.signal,
    { method: "POST" }
  )
    .catch((error) => {
      if (controller.signal.aborted) {
        throw new ApiError(
          "A API não respondeu em 15 segundos. Reinicie o backend e tente novamente."
        );
      }
      if (error instanceof ApiError && error.status === 404) {
        throw new ApiError(
          "A rota de inteligência tecnológica não está ativa. Reinicie o backend FastAPI.",
          404
        );
      }
      throw error;
    })
    .finally(() => window.clearTimeout(timeout));
}

export function getJob<TResult = import("@/lib/types").NvidiaRecommendationResult>(
  jobId: string,
  signal?: AbortSignal
) {
  return request<JobResponse<TResult>>(
    `/jobs/${encodeURIComponent(jobId)}`,
    signal
  );
}
