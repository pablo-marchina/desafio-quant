export type DashboardSummary = {
  total_startups: number;
  validation_statuses: Record<string, number>;
  enrichment_statuses: Record<string, number>;
  ai_classifications: Record<string, number>;
  recommendations_count?: number;
  github_actions_registrations: Array<{
    date: string;
    weekday: "Seg" | "Qui";
    count: number;
  }>;
  generated_at: string;
};

export type Startup = {
  id?: string;
  candidate_id?: string;
  company_name?: string;
  validated_url?: string | null;
  website?: string | null;
  description?: string | null;
  company_description?: string | null;
  github_org?: string | null;
  linkedin_url?: string | null;
  gupy_url?: string | null;
  crunchbase_url?: string | null;
  source_url?: string | null;
  tech_stack?: string[] | string | null;
  technology_intelligence?: TechnologyIntelligenceReport | null;
  nvidia_recommendation?: NvidiaRecommendationResult | null;
  competitive_analysis?: CompetitiveAnalysisResult | null;
  action_report?: ActionReportResult | null;
  ai_integrations?: string[] | string | null;
  ai_dependency_level?: string | null;
  enrichment_status?: string | null;
  validation_status?: string | null;
  cnpj?: string | null;
  cnae?: string | null;
  socios?: CompanyPartner[] | null;
  cnpj_data?: CompanyRegistrationData | string | null;
  founding_year?: string | number | null;
  location?: string | null;
  ai_technology_focus?: string | null;
  target_market?: string | null;
  key_milestones?: string | null;
  is_active?: boolean;
  discard_reason?: string | null;
  created_at?: string | null;
  updated_at?: string | null;
  last_enriched_at?: string | null;
  identity_confidence_score?: number | null;
  tech_confidence_score?: number | null;
  identity_evidence?: Record<string, unknown> | null;
  [key: string]: unknown;
};

export type CompanyPartner = {
  nome?: string | null;
  name?: string | null;
  qualificacao?: string | null;
  role?: string | null;
  data_entrada?: string | null;
  cpf_cnpj_mascarado?: string | null;
  representante_legal?: string | null;
};

export type CompanyAddress = {
  logradouro?: string | null;
  numero?: string | null;
  complemento?: string | null;
  bairro?: string | null;
  municipio?: string | null;
  uf?: string | null;
  cep?: string | null;
};

export type CompanyContact = {
  telefone_1?: string | null;
  telefone_2?: string | null;
  telefone?: string | null;
  email?: string | null;
};

export type CompanyRegistrationData = {
  cnpj?: string | null;
  razao_social?: string | null;
  nome_fantasia?: string | null;
  situacao?: string | null;
  ativa?: boolean | null;
  municipio?: string | null;
  uf?: string | null;
  cnae?: string | number | null;
  cnae_descricao?: string | null;
  cnaes_secundarios?: Array<{
    codigo?: string | number | null;
    descricao?: string | null;
  }> | null;
  data_inicio_atividade?: string | null;
  capital_social?: string | number | null;
  porte?: string | null;
  natureza_juridica?: string | null;
  endereco?: CompanyAddress | null;
  contato?: CompanyContact | null;
  socios?: CompanyPartner[] | null;
  responsavel_federal?: string | null;
  raw_data?: Record<string, unknown> | null;
};

export type StartupList = {
  items: Startup[];
  total: number;
  page: number;
  page_size: number;
};

export type StartupQuery = {
  page: number;
  pageSize: number;
  search?: string;
  validationStatus?: string;
  hasNvidiaRecommendation?: boolean;
};

export type JobStatus = "queued" | "running" | "completed" | "failed";

export type NvidiaRecommendationItem = {
  gap?: string;
  produto?: string;
  justificativa?: string;
  fontes?: string[];
};

export type NvidiaRecommendationResult = {
  startup_id?: string;
  company_name?: string;
  recommendation?: string | null;
  recommendations?: NvidiaRecommendationItem[];
  gaps?: Array<Record<string, unknown>>;
  final_answer?: string | null;
  sources?: string[];
  roadmap?: string[];
  comparacao_bigtechs?: string[];
  structured_output?: Record<string, unknown> | null;
};

export type CompetitiveAnalysisResult = {
  startup_id?: string;
  company_name?: string;
  competitive_report?: string | null;
  briefing?: string | null;
  final_answer?: string | null;
  structured_output?: Record<string, unknown>;
  generated_at?: string;
};

export type ActionReportResult = {
  startup_id?: string;
  company_name?: string;
  model?: string;
  generated_at?: string;
  context?: Record<string, unknown>;
  executive_summary?: string;
  markdown_report?: string;
  score_ai_native?: number | null;
  benchmark_competitivo?: {
    concorrentes?: Array<{
      nome?: string;
      usa_nvidia?: boolean | "desconhecido";
      fonte?: string;
    }>;
    posicionamento?: string;
  };
  confiabilidade?: Record<string, unknown>;
  next_actions?: Array<{
    action?: string;
    rationale?: string;
    priority?: string;
    owner?: string;
    timeframe?: string;
    success_metric?: string;
  }>;
  nvidia_focus?: string[];
  bigtech_implications?: string[];
  risks?: string[];
  open_questions?: string[];
  raw_report?: string;
  structured_output?: Record<string, unknown>;
};

export type TechnologyEvidence = {
  id: string;
  url: string;
  titulo?: string;
  dominio?: string;
  consulta?: string;
  trecho?: string;
};

export type TechnologyFinding = {
  tecnologia: string;
  uso_provavel: string;
  certeza: "Alta" | "Média" | "Baixa";
  evidencias: string[];
};

export type TechnologyIntelligenceReport = {
  schema_version?: string;
  company_name?: string;
  perfil_geral: { resumo: string; evidencias: string[] };
  infraestrutura_backend: TechnologyFinding[];
  frontend_mobile: TechnologyFinding[];
  ia_operacional_interna: TechnologyFinding[];
  ia_produto_core: TechnologyFinding[];
  nivel_certeza: {
    classificacao: "Alta" | "Média" | "Baixa";
    justificativa: string;
  };
  dados_insuficientes: string[];
  fontes: TechnologyEvidence[];
  modelo?: string;
  pesquisado_em?: string;
};

export type JobResponse<TResult = NvidiaRecommendationResult> = {
  job_id: string;
  status: JobStatus;
  job_type: string;
  startup_id: string;
  progress: number;
  created_at: string;
  started_at?: string | null;
  finished_at?: string | null;
  error?: string | null;
  result?: TResult | null;
};
