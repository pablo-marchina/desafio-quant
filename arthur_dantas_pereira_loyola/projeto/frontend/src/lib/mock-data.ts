export type AIMaturity = "AI-Native" | "AI-Enabled" | "Non-AI";
export type SourceType =
  | "Site oficial"
  | "Blog oficial"
  | "Página de carreiras"
  | "Perfil público de founder"
  | "Notícia"
  | "Diretório de startups";

export type NvidiaTech =
  | "NVIDIA Inception"
  | "NIM"
  | "NeMo"
  | "NeMo Guardrails"
  | "Triton Inference Server"
  | "TensorRT-LLM"
  | "RAPIDS"
  | "cuDF"
  | "cuML"
  | "CUDA"
  | "Riva"
  | "Omniverse"
  | "Isaac"
  | "Clara"
  | "Morpheus"
  | "AI Enterprise";

export interface Evidence {
  url: string;
  type: SourceType;
  snippet: string;
  collectedAt: string;
  confidence: number; // 0-100
}

export interface Recommendation {
  tech: NvidiaTech;
  technicalRationale: string;
  businessRationale: string;
  priority: "Alta" | "Média" | "Baixa";
  complexity: "Baixa" | "Média" | "Alta";
  nextAction: string;
  evidenceRefs: number[]; // index into evidence array
}

export interface Startup {
  id: string;
  name: string;
  sector: string;
  region: string;
  foundedYear: number;
  maturity: AIMaturity;
  radarScore: number;
  evidenceConfidence: number;
  growthPotential: number;
  nvidiaFit: number;
  contactPriority: number;
  lastValidatedSource: string;
  valuationRange: string;
  fundingRange: string;
  executiveSummary: string;
  maturityJustification: string;
  evidences: Evidence[];
  gaps: { name: string; description: string; severity: "Alta" | "Média" | "Baixa" }[];
  recommendations: Recommendation[];
  nextAction: string;
}

const today = "2026-06-12";

export const startups: Startup[] = [
  {
    id: "neurabra",
    name: "Neurabra AI",
    sector: "Fintech / Risco de crédito",
    region: "São Paulo, SP",
    foundedYear: 2022,
    maturity: "AI-Native",
    radarScore: 92,
    evidenceConfidence: 88,
    growthPotential: 90,
    nvidiaFit: 94,
    contactPriority: 95,
    lastValidatedSource: "neurabra.ai/tech",
    valuationRange: "US$ 40-60M",
    fundingRange: "Série A — US$ 12M",
    executiveSummary:
      "Plataforma de scoring de crédito baseada em LLMs proprietários para o mercado SMB brasileiro. Equipe técnica ex-Nubank e USP, operação 100% cloud com pipelines de inferência próprios.",
    maturityJustification:
      "Modelos próprios treinados e fine-tunados internamente, inferência em produção como produto principal e core de receita atrelado à qualidade do modelo.",
    evidences: [
      {
        url: "https://neurabra.ai/tech",
        type: "Site oficial",
        snippet:
          "Operamos modelos LLM próprios fine-tunados em dados de bureau brasileiro, servidos via cluster GPU dedicado.",
        collectedAt: today,
        confidence: 94,
      },
      {
        url: "https://neurabra.ai/blog/scaling-inference",
        type: "Blog oficial",
        snippet:
          "Reduzimos latência p95 de 1.8s para 420ms migrando para servidor de inferência otimizado.",
        collectedAt: today,
        confidence: 88,
      },
      {
        url: "https://neurabra.ai/careers/ml-platform",
        type: "Página de carreiras",
        snippet: "Buscamos engenheiro de plataforma ML com experiência em CUDA, Triton e quantização.",
        collectedAt: today,
        confidence: 82,
      },
    ],
    gaps: [
      { name: "Custo de inferência", description: "Custo por requisição cresce linearmente com volume de scoring.", severity: "Alta" },
      { name: "Observabilidade", description: "Sem telemetria de drift em produção.", severity: "Média" },
      { name: "Governança", description: "Sem guardrails formais sobre saídas do LLM em decisões de crédito.", severity: "Alta" },
    ],
    recommendations: [
      {
        tech: "Triton Inference Server",
        technicalRationale: "Consolida múltiplos modelos em um único servidor com batching dinâmico.",
        businessRationale: "Reduz custo unitário de inferência em ~35% no volume atual projetado.",
        priority: "Alta",
        complexity: "Média",
        nextAction: "Workshop técnico de 2h com squad de ML platform.",
        evidenceRefs: [0, 1],
      },
      {
        tech: "TensorRT-LLM",
        technicalRationale: "Otimização de kernels para LLMs do tamanho declarado (7B-13B).",
        businessRationale: "Acelera tempo de resposta crítico para integração bancária em tempo real.",
        priority: "Alta",
        complexity: "Alta",
        nextAction: "POC de quantização INT8 em modelo de scoring principal.",
        evidenceRefs: [1, 2],
      },
      {
        tech: "NeMo Guardrails",
        technicalRationale: "Política declarativa sobre saídas em domínio regulado.",
        businessRationale: "Mitiga risco regulatório com Bacen e CVM em decisões automatizadas.",
        priority: "Alta",
        complexity: "Baixa",
        nextAction: "Mapear top 10 fluxos de decisão e desenhar políticas.",
        evidenceRefs: [0],
      },
      {
        tech: "NVIDIA Inception",
        technicalRationale: "Acesso a créditos, suporte técnico e go-to-market.",
        businessRationale: "Alinha com momento de Série A e expansão de plataforma.",
        priority: "Alta",
        complexity: "Baixa",
        nextAction: "Convidar founders para onboarding Inception.",
        evidenceRefs: [0],
      },
    ],
    nextAction: "Agendar discovery técnica com VP Engineering nas próximas 2 semanas.",
  },
  {
    id: "vortex-vision",
    name: "Vortex Vision Labs",
    sector: "Indústria / Visão computacional",
    region: "Florianópolis, SC",
    foundedYear: 2021,
    maturity: "AI-Native",
    radarScore: 86,
    evidenceConfidence: 84,
    growthPotential: 82,
    nvidiaFit: 91,
    contactPriority: 88,
    lastValidatedSource: "vortexvision.com.br",
    valuationRange: "US$ 25-40M",
    fundingRange: "Seed estendido — US$ 6M",
    executiveSummary:
      "Inspeção visual em linhas de produção via redes convolucionais customizadas. Implantado em 14 plantas industriais no Sul e Sudeste.",
    maturityJustification:
      "Modelos próprios de detecção treinados sobre datasets industriais, deploy edge em câmeras dedicadas.",
    evidences: [
      {
        url: "https://vortexvision.com.br/produto",
        type: "Site oficial",
        snippet: "Modelos rodam em edge devices com aceleração GPU para inferência sub-50ms.",
        collectedAt: today,
        confidence: 90,
      },
      {
        url: "https://vortexvision.com.br/cases/automotiva",
        type: "Site oficial",
        snippet: "Detecção de defeitos com 99.2% de recall em peças metálicas.",
        collectedAt: today,
        confidence: 86,
      },
      {
        url: "https://startupbase.fictdir.com/vortex",
        type: "Diretório de startups",
        snippet: "Vortex Vision — 38 funcionários, foco em manufatura.",
        collectedAt: today,
        confidence: 70,
      },
    ],
    gaps: [
      { name: "Escalabilidade", description: "Treino atualmente em hardware on-prem limitado.", severity: "Alta" },
      { name: "Latência", description: "Modelos não otimizados para edge mais barato.", severity: "Média" },
    ],
    recommendations: [
      {
        tech: "TensorRT-LLM",
        technicalRationale: "Otimização de modelos de visão para edge devices Jetson.",
        businessRationale: "Reduz BOM por estação de inspeção em ~22%.",
        priority: "Alta",
        complexity: "Média",
        nextAction: "Benchmark em Jetson Orin Nano.",
        evidenceRefs: [0, 1],
      },
      {
        tech: "Isaac",
        technicalRationale: "Simulação sintética de defeitos raros.",
        businessRationale: "Acelera entrada em novos verticais sem coletar dataset físico.",
        priority: "Média",
        complexity: "Alta",
        nextAction: "POC em novo cliente automotivo.",
        evidenceRefs: [1],
      },
      {
        tech: "NVIDIA Inception",
        technicalRationale: "Acesso a Jetson developer kits e suporte.",
        businessRationale: "Reduz CAPEX de R&D em hardware.",
        priority: "Alta",
        complexity: "Baixa",
        nextAction: "Onboarding em Inception.",
        evidenceRefs: [0],
      },
    ],
    nextAction: "Conectar com time de Robotics LATAM.",
  },
  {
    id: "agroflow",
    name: "AgroFlow Intelligence",
    sector: "Agronegócio / Sensoriamento",
    region: "Ribeirão Preto, SP",
    foundedYear: 2020,
    maturity: "AI-Enabled",
    radarScore: 74,
    evidenceConfidence: 71,
    growthPotential: 79,
    nvidiaFit: 72,
    contactPriority: 70,
    lastValidatedSource: "agroflow.farm",
    valuationRange: "US$ 30-50M",
    fundingRange: "Série A — US$ 9M",
    executiveSummary:
      "Telemetria e analytics para fazendas grandes. Usa modelos abertos de visão para detecção de pragas em imagens de drone.",
    maturityJustification:
      "Modelos majoritariamente open-source com fine-tuning leve, IA é diferencial mas não core do produto.",
    evidences: [
      {
        url: "https://agroflow.farm/tecnologia",
        type: "Site oficial",
        snippet: "Pipeline de imagens combina YOLO com regras heurísticas.",
        collectedAt: today,
        confidence: 78,
      },
      {
        url: "https://valor.fictnews.com/agroflow-rodada",
        type: "Notícia",
        snippet: "AgroFlow capta US$ 9M para expansão no Centro-Oeste.",
        collectedAt: today,
        confidence: 72,
      },
    ],
    gaps: [
      { name: "Dependência de APIs externas", description: "Inferência terceirizada em provider US.", severity: "Alta" },
      { name: "Custo de inferência", description: "Margem comprimida com novos clientes.", severity: "Média" },
    ],
    recommendations: [
      {
        tech: "RAPIDS",
        technicalRationale: "Processamento acelerado de séries temporais multispectrais.",
        businessRationale: "Permite cobrar por hectare em planos premium.",
        priority: "Média",
        complexity: "Média",
        nextAction: "Sessão de discovery com time de dados.",
        evidenceRefs: [0],
      },
      {
        tech: "Triton Inference Server",
        technicalRationale: "Internalizar inferência hoje terceirizada.",
        businessRationale: "Reduz custo recorrente de API externa.",
        priority: "Alta",
        complexity: "Média",
        nextAction: "Estimar TCO de migração.",
        evidenceRefs: [0, 1],
      },
    ],
    nextAction: "Validar interesse em Inception com CTO.",
  },
  {
    id: "lumini-health",
    name: "Lumini Health",
    sector: "Healthtech / Imagem médica",
    region: "Porto Alegre, RS",
    foundedYear: 2023,
    maturity: "AI-Native",
    radarScore: 81,
    evidenceConfidence: 76,
    growthPotential: 85,
    nvidiaFit: 89,
    contactPriority: 78,
    lastValidatedSource: "luminihealth.com.br/research",
    valuationRange: "US$ 15-25M",
    fundingRange: "Seed — US$ 3.5M",
    executiveSummary:
      "Triagem radiológica assistida por IA, com pipeline DICOM proprietário e foco em hospitais de médio porte.",
    maturityJustification: "Modelos proprietários, certificação ANVISA em andamento, IA é o produto.",
    evidences: [
      {
        url: "https://luminihealth.com.br/research",
        type: "Site oficial",
        snippet: "Modelos treinados em 1.2M de exames anonimizados.",
        collectedAt: today,
        confidence: 84,
      },
      {
        url: "https://luminihealth.com.br/carreiras/research",
        type: "Página de carreiras",
        snippet: "Vaga: Research Engineer com experiência em MONAI e CUDA.",
        collectedAt: today,
        confidence: 80,
      },
    ],
    gaps: [
      { name: "Governança", description: "Auditoria de viés ainda manual.", severity: "Alta" },
      { name: "Observabilidade", description: "Sem monitoramento contínuo de performance clínica.", severity: "Média" },
    ],
    recommendations: [
      {
        tech: "Clara",
        technicalRationale: "Framework dedicado para imagem médica em fluxos DICOM.",
        businessRationale: "Acelera certificação e reduz tempo de pipeline em ~40%.",
        priority: "Alta",
        complexity: "Média",
        nextAction: "Workshop com squad de Research.",
        evidenceRefs: [0, 1],
      },
      {
        tech: "Morpheus",
        technicalRationale: "Detecção de anomalias em logs de inferência clínica.",
        businessRationale: "Reforça compliance LGPD em ambiente hospitalar.",
        priority: "Média",
        complexity: "Alta",
        nextAction: "Sessão técnica com Security Officer.",
        evidenceRefs: [1],
      },
    ],
    nextAction: "Conectar com Healthcare BD LATAM.",
  },
  {
    id: "polyglot-voice",
    name: "Polyglot Voice",
    sector: "Customer experience / Voz",
    region: "Rio de Janeiro, RJ",
    foundedYear: 2022,
    maturity: "AI-Native",
    radarScore: 79,
    evidenceConfidence: 73,
    growthPotential: 81,
    nvidiaFit: 86,
    contactPriority: 74,
    lastValidatedSource: "polyglotvoice.io",
    valuationRange: "US$ 18-28M",
    fundingRange: "Seed — US$ 4.2M",
    executiveSummary:
      "Atendimento por voz com agentes LLM em PT-BR regional. Foco em utilities e cobrança.",
    maturityJustification: "ASR e TTS próprios fine-tunados para sotaques brasileiros.",
    evidences: [
      {
        url: "https://polyglotvoice.io/produto",
        type: "Site oficial",
        snippet: "Stack proprietária de ASR/TTS otimizada para PT-BR.",
        collectedAt: today,
        confidence: 82,
      },
      {
        url: "https://medium.fictblog.com/@polyglotvoice/streaming-asr",
        type: "Blog oficial",
        snippet: "Reduzimos WER em sotaque nordestino em 22% com fine-tuning.",
        collectedAt: today,
        confidence: 70,
      },
    ],
    gaps: [
      { name: "Latência", description: "Pipeline streaming com gargalo em GPU compartilhada.", severity: "Alta" },
      { name: "Custo de inferência", description: "Voz contínua é cara em provedor atual.", severity: "Alta" },
    ],
    recommendations: [
      {
        tech: "Riva",
        technicalRationale: "Stack otimizada de ASR/TTS com baixa latência em GPU.",
        businessRationale: "Diferencial de qualidade em sotaques regionais com menor custo por minuto.",
        priority: "Alta",
        complexity: "Média",
        nextAction: "POC em ambiente de cliente piloto.",
        evidenceRefs: [0, 1],
      },
      {
        tech: "NIM",
        technicalRationale: "Microsserviços de inferência empacotados para multi-tenant.",
        businessRationale: "Acelera time-to-market de novas verticais.",
        priority: "Média",
        complexity: "Baixa",
        nextAction: "Avaliar fit em pipeline atual.",
        evidenceRefs: [0],
      },
    ],
    nextAction: "Briefing técnico com time de Conversational AI.",
  },
  {
    id: "quanta-logix",
    name: "Quanta Logix",
    sector: "Logística / Otimização",
    region: "Curitiba, PR",
    foundedYear: 2019,
    maturity: "AI-Enabled",
    radarScore: 68,
    evidenceConfidence: 66,
    growthPotential: 72,
    nvidiaFit: 65,
    contactPriority: 60,
    lastValidatedSource: "quantalogix.com.br",
    valuationRange: "US$ 40-70M",
    fundingRange: "Série B — US$ 22M",
    executiveSummary:
      "Roteirização e gestão de frota com modelos heurísticos e ML clássico.",
    maturityJustification: "ML clássico e otimização combinatória; IA como feature complementar.",
    evidences: [
      {
        url: "https://quantalogix.com.br/produto",
        type: "Site oficial",
        snippet: "Roteirizador combina OR-Tools com modelos preditivos de demanda.",
        collectedAt: today,
        confidence: 68,
      },
      {
        url: "https://startupbase.fictdir.com/quantalogix",
        type: "Diretório de startups",
        snippet: "Quanta Logix — 120 funcionários, Série B em 2024.",
        collectedAt: today,
        confidence: 64,
      },
    ],
    gaps: [
      { name: "Escalabilidade", description: "Tempo de cálculo cresce com tamanho da frota.", severity: "Média" },
    ],
    recommendations: [
      {
        tech: "cuDF",
        technicalRationale: "Acelera ETL de telemetria de frota.",
        businessRationale: "Permite janelas de replanejamento mais frequentes.",
        priority: "Média",
        complexity: "Baixa",
        nextAction: "Workshop de RAPIDS com time de dados.",
        evidenceRefs: [0],
      },
      {
        tech: "cuML",
        technicalRationale: "Modelos de previsão de demanda em escala.",
        businessRationale: "Eleva acurácia de previsão e reduz custo operacional.",
        priority: "Média",
        complexity: "Média",
        nextAction: "POC em rota piloto.",
        evidenceRefs: [0, 1],
      },
    ],
    nextAction: "Avaliar fit comercial em ciclo de Q3.",
  },
  {
    id: "ferra-secure",
    name: "Ferra Secure",
    sector: "Cybersecurity / SOC",
    region: "Belo Horizonte, MG",
    foundedYear: 2021,
    maturity: "AI-Enabled",
    radarScore: 75,
    evidenceConfidence: 70,
    growthPotential: 76,
    nvidiaFit: 82,
    contactPriority: 73,
    lastValidatedSource: "ferrasecure.io",
    valuationRange: "US$ 20-35M",
    fundingRange: "Seed estendido — US$ 5M",
    executiveSummary:
      "Detecção de ameaças com correlação de eventos e modelos de anomalia. Foco em mid-market.",
    maturityJustification: "ML aplicado, mas core do produto ainda é correlação baseada em regras.",
    evidences: [
      {
        url: "https://ferrasecure.io/plataforma",
        type: "Site oficial",
        snippet: "Engine de correlação enriquecida por modelos de anomalia comportamental.",
        collectedAt: today,
        confidence: 76,
      },
      {
        url: "https://ferrasecure.io/founder",
        type: "Perfil público de founder",
        snippet: "Founder com background em threat intelligence em banco tier-1.",
        collectedAt: today,
        confidence: 70,
      },
    ],
    gaps: [
      { name: "Latência", description: "Tempo de detecção alto em picos.", severity: "Alta" },
      { name: "Observabilidade", description: "Falta visibilidade de drift de modelo.", severity: "Média" },
    ],
    recommendations: [
      {
        tech: "Morpheus",
        technicalRationale: "Framework GPU-accelerated para cybersecurity em alto volume.",
        businessRationale: "Permite atender enterprises com SLA agressivo.",
        priority: "Alta",
        complexity: "Alta",
        nextAction: "Discovery técnica com Head of Engineering.",
        evidenceRefs: [0],
      },
      {
        tech: "AI Enterprise",
        technicalRationale: "Stack suportada para deploy on-prem em clientes regulados.",
        businessRationale: "Desbloqueia contas em setor financeiro.",
        priority: "Média",
        complexity: "Média",
        nextAction: "Mapear pipeline de contas reguladas.",
        evidenceRefs: [0, 1],
      },
    ],
    nextAction: "Conectar com programa Inception e SE de Cyber.",
  },
  {
    id: "omnigen",
    name: "OmniGen Studios",
    sector: "Creative / Generative media",
    region: "São Paulo, SP",
    foundedYear: 2023,
    maturity: "AI-Native",
    radarScore: 83,
    evidenceConfidence: 79,
    growthPotential: 88,
    nvidiaFit: 90,
    contactPriority: 82,
    lastValidatedSource: "omnigen.studio",
    valuationRange: "US$ 12-20M",
    fundingRange: "Pre-seed — US$ 1.8M",
    executiveSummary:
      "Plataforma de geração de assets 3D para games e publicidade, com pipeline próprio sobre modelos abertos.",
    maturityJustification: "Pipeline próprio, fine-tuning ativo e produto core 100% generativo.",
    evidences: [
      {
        url: "https://omnigen.studio/tech",
        type: "Site oficial",
        snippet: "Pipeline combina difusão 2D, reconstrução 3D e refinamento PBR.",
        collectedAt: today,
        confidence: 82,
      },
      {
        url: "https://omnigen.studio/carreiras",
        type: "Página de carreiras",
        snippet: "Vaga: Engenheiro CUDA com experiência em renderização.",
        collectedAt: today,
        confidence: 78,
      },
      {
        url: "https://exame.fictnews.com/omnigen",
        type: "Notícia",
        snippet: "OmniGen anuncia parceria com estúdio de games AAA brasileiro.",
        collectedAt: today,
        confidence: 74,
      },
    ],
    gaps: [
      { name: "Custo de inferência", description: "Render de alta resolução é caro em provider atual.", severity: "Alta" },
      { name: "Escalabilidade", description: "Fila de geração com pico em horário comercial.", severity: "Média" },
    ],
    recommendations: [
      {
        tech: "Omniverse",
        technicalRationale: "Pipeline colaborativo USD para assets 3D.",
        businessRationale: "Diferencial competitivo em integrações com estúdios.",
        priority: "Alta",
        complexity: "Média",
        nextAction: "Demo com time criativo.",
        evidenceRefs: [0, 2],
      },
      {
        tech: "Triton Inference Server",
        technicalRationale: "Batching dinâmico para pipeline de difusão.",
        businessRationale: "Reduz custo por asset gerado.",
        priority: "Alta",
        complexity: "Média",
        nextAction: "Benchmark interno.",
        evidenceRefs: [0, 1],
      },
      {
        tech: "NVIDIA Inception",
        technicalRationale: "Acesso a créditos e suporte técnico.",
        businessRationale: "Suporta fase pre-seed com baixo CAC técnico.",
        priority: "Alta",
        complexity: "Baixa",
        nextAction: "Onboarding Inception.",
        evidenceRefs: [0],
      },
    ],
    nextAction: "Apresentar para time de Media & Entertainment LATAM.",
  },
];

export function getStartup(id: string) {
  return startups.find((s) => s.id === id);
}

export const overviewMetrics = {
  analyzed: 248,
  aiNative: 64,
  validatedEvidences: 1432,
  recommendations: 312,
  briefings: 87,
};

export const maturityDistribution = [
  { name: "AI-Native", value: 64 },
  { name: "AI-Enabled", value: 112 },
  { name: "Non-AI", value: 72 },
];

export const pipelineSteps = [
  {
    name: "Search Planner Agent",
    status: "completed" as const,
    desc: "Planeja consultas a partir do input do analista.",
    output: "12 queries planejadas em pt-BR e en-US.",
    lastRun: "há 3 min",
  },
  {
    name: "Scraper Agent",
    status: "completed" as const,
    desc: "Coleta páginas públicas respeitando robots.txt.",
    output: "47 páginas coletadas, 6 descartadas por robots.",
    lastRun: "há 3 min",
  },
  {
    name: "Extractor Agent",
    status: "completed" as const,
    desc: "Extrai trechos relevantes com âncora de URL.",
    output: "184 trechos com URL e selector preservados.",
    lastRun: "há 2 min",
  },
  {
    name: "Evidence Validator Agent",
    status: "running" as const,
    desc: "Cruza evidências e atribui confiança.",
    output: "62% concluído — 3 contradições em análise.",
    lastRun: "agora",
  },
  {
    name: "Startup Classifier Agent",
    status: "needs evidence" as const,
    desc: "Classifica AI-Native, AI-Enabled ou Non-AI.",
    output: "Aguardando trecho de página de produto.",
    lastRun: "—",
  },
  {
    name: "NVIDIA RAG Agent",
    status: "ready" as const,
    desc: "Consulta base oficial NVIDIA via RAG.",
    output: "Índice pronto: 12.4k documentos.",
    lastRun: "há 5 min",
  },
  {
    name: "Recommendation Agent",
    status: "blocked" as const,
    desc: "Gera recomendações com justificativa rastreável.",
    output: "Bloqueado: depende do Classifier.",
    lastRun: "—",
  },
  {
    name: "Briefing Agent",
    status: "ready" as const,
    desc: "Monta briefing executivo final.",
    output: "Template carregado.",
    lastRun: "—",
  },
];

export const sources = [
  { name: "neurabra.ai", type: "Site oficial" as SourceType, evidences: 14, quality: 92, lastCollected: today, status: "validada" as const },
  { name: "neurabra.ai/blog", type: "Blog oficial" as SourceType, evidences: 8, quality: 86, lastCollected: today, status: "validada" as const },
  { name: "neurabra.ai/careers", type: "Página de carreiras" as SourceType, evidences: 5, quality: 80, lastCollected: today, status: "validada" as const },
  { name: "vortexvision.com.br", type: "Site oficial" as SourceType, evidences: 11, quality: 88, lastCollected: today, status: "validada" as const },
  { name: "linkedin.fictprofile/founder-vortex", type: "Perfil público de founder" as SourceType, evidences: 3, quality: 64, lastCollected: today, status: "fraca" as const },
  { name: "valor.fictnews.com", type: "Notícia" as SourceType, evidences: 7, quality: 72, lastCollected: today, status: "validada" as const },
  { name: "startupbase.fictdir.com", type: "Diretório de startups" as SourceType, evidences: 12, quality: 68, lastCollected: today, status: "fraca" as const },
  { name: "agroflow.farm", type: "Site oficial" as SourceType, evidences: 9, quality: 78, lastCollected: today, status: "validada" as const },
  { name: "luminihealth.com.br/research", type: "Site oficial" as SourceType, evidences: 6, quality: 84, lastCollected: today, status: "validada" as const },
  { name: "medium.fictblog.com/@polyglotvoice", type: "Blog oficial" as SourceType, evidences: 4, quality: 70, lastCollected: today, status: "contraditória" as const },
  { name: "ferrasecure.io/founder", type: "Perfil público de founder" as SourceType, evidences: 2, quality: 66, lastCollected: today, status: "pendente" as const },
  { name: "exame.fictnews.com", type: "Notícia" as SourceType, evidences: 5, quality: 74, lastCollected: today, status: "validada" as const },
];

export const NVIDIA_TECHS: NvidiaTech[] = [
  "NVIDIA Inception", "NIM", "NeMo", "NeMo Guardrails", "Triton Inference Server",
  "TensorRT-LLM", "RAPIDS", "cuDF", "cuML", "CUDA", "Riva", "Omniverse", "Isaac",
  "Clara", "Morpheus", "AI Enterprise",
];

export const SOURCE_TYPES: SourceType[] = [
  "Site oficial", "Blog oficial", "Página de carreiras", "Perfil público de founder", "Notícia", "Diretório de startups",
];
