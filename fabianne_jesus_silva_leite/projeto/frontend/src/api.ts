const API_URL = import.meta.env.VITE_API_URL;

if (!API_URL) {
  throw new Error("VITE_API_URL não configurada.");
}

export type StartupHistoryItem = {
  startup_id: string;
  name: string;
  sector: string | null;
  created_at: string;
  latest_analysis_id: string | null;
  latest_analysis_at: string | null;
  classification_category: string | null;
  nvidia_opportunity_score: number | null;
};

export type AnalysisHistoryItem = {
  analysis_id: string;
  status: string;
  created_at: string;
  collected_at: string | null;
  sources_successful: number;
  classification_category: string | null;
  ai_native_score: number | null;
  wrapper_risk_score: number | null;
  nvidia_opportunity_score: number | null;
  gaps_count: number;
};

export type CollectedSource = {
  url: string;
  title: string | null;
  status: string;
  extraction_method: string | null;
  word_count: number | null;
  error: string | null;
};

export type Evidence = {
  claim: string;
  quote: string;
  source_url: string;
  status: string;
  confidence: number;
  category: string;
};

export type RecommendationCitation = {
  evidence_id: string;
  source_type: "startup" | "nvidia";
  source_url: string;
  quote: string;
};

export type Recommendation = {
  technology_id: string;
  technology_name: string;
  priority: "ALTA" | "MEDIA" | "BAIXA";
  complexity: "ALTA" | "MEDIA" | "BAIXA";
  technical_reason: string;
  business_reason: string;
  next_action: string;
  startup_evidences: RecommendationCitation[];
  nvidia_evidences: RecommendationCitation[];
};

export type NvidiaRagEvidence = {
  technology_id: string;
  technology_name: string;
  title: string;
  text: string;
  source_url: string;
  tags: string[];
  lexical_score: number;
  semantic_score: number;
  fused_score: number;
  rerank_score: number;
};

export type NvidiaRagTechnology = {
  technology_id: string;
  technology_name: string;
  why_retrieved: string[];
  evidences: NvidiaRagEvidence[];
};

export type NvidiaContext = {
  generated_queries: string[];
  technologies: NvidiaRagTechnology[];
};

type StartupListResponse = {
  startups: StartupHistoryItem[];
};

export type StartupAnalysesResponse = {
  startup_id: string;
  startup_name: string;
  analyses: AnalysisHistoryItem[];
};

export type FlightPlanPhase = {
  period: "0-30 dias" | "31-60 dias" | "61-90 dias";
  title: string;
  objective: string;
  actions: string[];
  nvidia_technologies: string[];
  success_criteria: string[];
};

export type FlightPlan = {
  title: string;
  summary: string;
  phases: FlightPlanPhase[];
};

export type FullAnalysisResponse = {
  analysis_id: string;

  research: {
    startup_name: string;
    sources_successful: number;
    sources: CollectedSource[];
    evidences: Evidence[];

    classification: {
      category: string;
      ai_native_score: number;
      wrapper_risk_score: number;
      nvidia_opportunity_score: number;
    };

    gaps: {
      category: string;
      status: string;
      message: string;
    }[];
  };

  nvidia_context?: NvidiaContext;

  recommendations: {
    model: string;
    recommendations: Recommendation[];
    limitations: string[];
  };

  briefing: {
    startup_name: string;
    generated_at: string;
    recommendation_count: number;
    markdown: string;
    flight_plan?: FlightPlan;
  };
};

export async function getStartups(): Promise<StartupHistoryItem[]> {
  const response = await fetch(`${API_URL}/startups`);

  if (!response.ok) {
    throw new Error("Não foi possível carregar o histórico.");
  }

  const data: StartupListResponse = await response.json();

  return data.startups;
}

export async function getStartupAnalyses(
  startupId: string,
): Promise<StartupAnalysesResponse> {
  const response = await fetch(
    `${API_URL}/startups/${startupId}/analyses`,
  );

  if (!response.ok) {
    throw new Error(
      "Não foi possível carregar as análises dessa startup.",
    );
  }

  return response.json();
}

export async function createFullAnalysis(payload: {
  startup_name: string;
  sector?: string;
  max_sources: number;
}): Promise<FullAnalysisResponse> {
  const response = await fetch(`${API_URL}/research/full`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => null);

    throw new Error(
      error?.detail || "Não foi possível executar a análise.",
    );
  }

  return response.json();
}

export async function getAnalysis(
  analysisId: string,
): Promise<FullAnalysisResponse> {
  const response = await fetch(
    `${API_URL}/analyses/${analysisId}`,
  );

  if (!response.ok) {
    throw new Error("Não foi possível carregar a análise salva.");
  }

  return response.json();
}

export async function downloadAnalysisPdf(
  analysisId: string,
): Promise<Blob> {
  const response = await fetch(
    `${API_URL}/analyses/${analysisId}/report.pdf`,
    { cache: "no-store" },
  );

  if (!response.ok) {
    const error = await response.json().catch(() => null);

    throw new Error(
      error?.detail || "Não foi possível gerar o relatório em PDF.",
    );
  }

  return response.blob();
}
