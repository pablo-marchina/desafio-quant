import { useEffect, useState, type FormEvent } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import {
  createFullAnalysis,
  downloadAnalysisPdf,
  getAnalysis,
  getStartupAnalyses,
  getStartups,
  type FullAnalysisResponse,
  type StartupAnalysesResponse,
  type StartupHistoryItem,
} from "./api";
import "./App.css";

type PipelineStep = {
  title: string;
  description: string;
};

type ResultTab =
  | "summary"
  | "recommendations"
  | "flight-plan"
  | "nvidia-context"
  | "evidences"
  | "briefing";

type AnalysisComparison = {
  older: FullAnalysisResponse;
  newer: FullAnalysisResponse;
};

type ComparisonHighlight = {
  label: string;
  title: string;
  description: string;
  whyItMatters: string;
  nextStep: string;
  tone: "neutral" | "positive" | "attention";
};

const PIPELINE_STEPS: PipelineStep[] = [
  {
    title: "Planejando a pesquisa",
    description:
      "Definindo quais informações públicas podem ajudar a entender a startup.",
  },
  {
    title: "Buscando fontes públicas",
    description:
      "Consultando páginas oficiais, notícias e outras fontes abertas.",
  },
  {
    title: "Organizando as informações",
    description:
      "Separando sinais relevantes, pontos de atenção e informações que ainda precisam de validação.",
  },
  {
    title: "Consultando tecnologias NVIDIA",
    description:
      "Relacionando as necessidades identificadas com documentação oficial da NVIDIA.",
  },
  {
    title: "Preparando sugestões",
    description:
      "Conectando as informações encontradas a tecnologias e próximos passos possíveis.",
  },
  {
    title: "Montando o relatório",
    description:
      "Organizando o resumo, as sugestões e o plano de próximos passos.",
  },
];

function formatDate(value: string | null) {
  if (!value) {
    return "Data não disponível";
  }

  return new Intl.DateTimeFormat("pt-BR", {
    dateStyle: "short",
    timeStyle: "short",
  }).format(new Date(value));
}

function ensurePeriod(text: string) {
  const trimmedText = text.trim();

  if (!trimmedText) {
    return trimmedText;
  }

  if (/[.!?…:]$/.test(trimmedText)) {
    return trimmedText;
  }

  return `${trimmedText}.`;
}

function downloadBriefing(markdown: string, startupName: string) {
  const file = new Blob([markdown], {
    type: "text/markdown;charset=utf-8",
  });

  const url = URL.createObjectURL(file);
  const link = document.createElement("a");

  link.href = url;
  link.download = `relatorio-${startupName
    .toLowerCase()
    .replace(/\s+/g, "-")}.md`;

  document.body.appendChild(link);
  link.click();
  link.remove();

  URL.revokeObjectURL(url);
}

function savePdfReport(pdf: Blob, startupName: string) {
  const url = URL.createObjectURL(pdf);
  const link = document.createElement("a");

  link.href = url;
  link.download = `relatorio-nvidia-${startupName
    .toLowerCase()
    .replace(/\s+/g, "-")}.pdf`;

  document.body.appendChild(link);
  link.click();
  link.remove();

  URL.revokeObjectURL(url);
}

function formatClassification(category: string | null) {
  if (!category) {
    return "Perfil não identificado";
  }

  const labels: Record<string, string> = {
    "AI-native": "IA como parte central do produto",
    "AI-Native": "IA como parte central do produto",
    AI_NATIVE: "IA como parte central do produto",
    "AI-enabled": "IA como apoio ao produto",
    "AI-Enabled": "IA como apoio ao produto",
    AI_ENABLED: "IA como apoio ao produto",
    Wrapper: "Alta dependência de soluções externas",
    wrapper: "Alta dependência de soluções externas",
    WRAPPER: "Alta dependência de soluções externas",
  };

  return (
    labels[category] ||
    category
      .replace(/_/g, " ")
      .replace(/\b\w/g, (letter) => letter.toUpperCase())
  );
}

function formatTopic(category: string) {
  const labels: Record<string, string> = {
    governance_security: "Segurança, privacidade e governança",
    governance: "Governança e segurança",
    security: "Segurança e privacidade",
    data_maturity: "Dados disponíveis para IA",
    data: "Dados disponíveis",
    model_ownership: "Desenvolvimento de modelos próprios",
    infrastructure: "Infraestrutura e escalabilidade",
    ai_strategy: "Estratégia de inteligência artificial",
    technical_stack: "Tecnologias utilizadas",
    technology: "Tecnologias utilizadas",
    business: "Contexto de negócio",
    product: "Produto e proposta de valor",
    market: "Mercado e público atendido",
  };

  return (
    labels[category] ||
    category
      .replace(/_/g, " ")
      .replace(/\b\w/g, (letter) => letter.toUpperCase())
  );
}

function formatPriority(priority: string) {
  const labels: Record<string, string> = {
    ALTA: "Prioridade alta",
    MEDIA: "Prioridade média",
    BAIXA: "Prioridade baixa",
  };

  return labels[priority] || priority;
}

function formatComplexity(complexity: string) {
  const labels: Record<string, string> = {
    ALTA: "Alta",
    MEDIA: "Média",
    BAIXA: "Baixa",
  };

  return labels[complexity] || complexity;
}

function formatSourceStatus(status: string) {
  const labels: Record<string, string> = {
    success: "Informação disponível",
    successful: "Informação disponível",
    completed: "Informação disponível",
    failed: "Não foi possível consultar",
    failure: "Não foi possível consultar",
    error: "Não foi possível consultar",
    unavailable: "Indisponível",
  };

  return (
    labels[status.toLowerCase()] ||
    status
      .replace(/_/g, " ")
      .replace(/\b\w/g, (letter) => letter.toUpperCase())
  );
}

function describeAiRole(score: number) {
  if (score >= 75) {
    return "IA é central no produto";
  }

  if (score >= 50) {
    return "IA tem papel relevante";
  }

  if (score >= 25) {
    return "IA aparece como apoio";
  }

  return "Poucos sinais públicos de uso de IA";
}

function describeExternalDependency(score: number) {
  if (score >= 75) {
    return "Dependência alta";
  }

  if (score >= 50) {
    return "Dependência moderada";
  }

  if (score >= 25) {
    return "Dependência limitada";
  }

  return "Dependência baixa";
}

function describeNvidiaPotential(score: number) {
  if (score >= 75) {
    return "Potencial alto";
  }

  if (score >= 50) {
    return "Potencial moderado";
  }

  if (score >= 25) {
    return "Potencial inicial";
  }

  return "Potencial ainda pouco claro";
}

function getGapCategories(analysis: FullAnalysisResponse) {
  return new Set(
    analysis.research.gaps.map((gap) => gap.category),
  );
}

function getRecommendationNames(analysis: FullAnalysisResponse) {
  return new Set(
    analysis.recommendations.recommendations.map(
      (recommendation) => recommendation.technology_name,
    ),
  );
}

function getDifference(
  primary: Set<string>,
  secondary: Set<string>,
) {
  return [...primary].filter((item) => !secondary.has(item));
}

function getIntersection(
  first: Set<string>,
  second: Set<string>,
) {
  return [...first].filter((item) => second.has(item));
}

function getWhyItMatters(category: string) {
  const explanations: Record<string, string> = {
    governance_security:
      "Sem essas informações, fica mais difícil entender se a solução está preparada para lidar com dados sensíveis, privacidade e controles de uso de IA.",
    data_maturity:
      "A disponibilidade e a qualidade dos dados influenciam diretamente a viabilidade de testar, treinar e escalar soluções de IA.",
    model_ownership:
      "Entender quem desenvolve e controla os modelos ajuda a avaliar autonomia técnica, diferenciação e dependência de fornecedores externos.",
    infrastructure:
      "A infraestrutura atual influencia custo, desempenho, escalabilidade e a possibilidade de adotar novas tecnologias.",
    ai_strategy:
      "Sem clareza sobre a estratégia de IA, é difícil entender quais iniciativas técnicas realmente fazem sentido como próximo passo.",
    technical_stack:
      "Conhecer as tecnologias usadas atualmente permite propor um caminho técnico mais compatível com a realidade da startup.",
  };

  return (
    explanations[category] ||
    "Esse ponto precisa ser confirmado para que a leitura sobre a startup seja mais completa e segura."
  );
}

function getSuggestedQuestion(category: string) {
  const questions: Record<string, string> = {
    governance_security:
      "Perguntar como a startup trata privacidade, segurança, conformidade e controles de uso de IA.",
    data_maturity:
      "Perguntar quais dados estão disponíveis, como são organizados e quais limitações existem para uso em IA.",
    model_ownership:
      "Perguntar se a startup desenvolve modelos próprios ou depende principalmente de fornecedores externos.",
    infrastructure:
      "Perguntar como a solução é executada hoje, quais limitações existem e quais são os principais desafios de escala.",
    ai_strategy:
      "Perguntar quais objetivos de IA a startup quer atingir nos próximos meses e quais barreiras impedem esse avanço.",
    technical_stack:
      "Perguntar quais tecnologias já estão em uso e quais pontos técnicos mais limitam a evolução atual.",
  };

  return (
    questions[category] ||
    "Conversar com a startup para confirmar os detalhes que não aparecem nas fontes públicas."
  );
}

function buildComparisonHighlight(
  comparison: AnalysisComparison,
): ComparisonHighlight {
  const { older, newer } = comparison;

  const previousTopics = getGapCategories(older);

  const newPointsToValidate = newer.research.gaps.filter(
    (gap) => !previousTopics.has(gap.category),
  );

  const evidenceDifference =
    newer.research.evidences.length -
    older.research.evidences.length;

  const newTechnologies = getDifference(
    getRecommendationNames(newer),
    getRecommendationNames(older),
  );

  if (newPointsToValidate.length > 0) {
    const point = newPointsToValidate[0];

    return {
      label: "Novo ponto de atenção",
      title: formatTopic(point.category),
      description: point.message,
      whyItMatters: getWhyItMatters(point.category),
      nextStep: getSuggestedQuestion(point.category),
      tone: "attention",
    };
  }

  if (newTechnologies.length > 0) {
    return {
      label: "Nova tecnologia sugerida",
      title: newTechnologies[0],
      description:
        "Essa tecnologia passou a aparecer como uma possibilidade relevante na análise mais recente.",
      whyItMatters:
        "Uma nova sugestão pode indicar que as informações encontradas agora mostram uma necessidade técnica que não estava clara antes.",
      nextStep:
        "Validar com a startup se essa tecnologia se encaixa na arquitetura atual e nos objetivos dos próximos meses.",
      tone: "positive",
    };
  }

  if (evidenceDifference < 0) {
    return {
      label: "Menos informações públicas disponíveis",
      title: `${Math.abs(evidenceDifference)} informação(ões) a menos`,
      description:
        "A análise mais recente encontrou menos informações verificáveis para apoiar a leitura atual.",
      whyItMatters:
        "Isso pede mais cautela ao interpretar as sugestões, mas não significa que a startup piorou.",
      nextStep:
        "Usar uma conversa direta com a startup para preencher os pontos que não aparecem nas fontes públicas.",
      tone: "attention",
    };
  }

  if (evidenceDifference > 0) {
    return {
      label: "Mais informações públicas disponíveis",
      title: `${evidenceDifference} informação(ões) a mais`,
      description:
        "A análise mais recente encontrou mais elementos verificáveis para apoiar a leitura atual.",
      whyItMatters:
        "Com mais informações disponíveis, a conversa com a startup pode ser mais específica e direcionada.",
      nextStep:
        "Usar as novas informações para confirmar prioridades técnicas e definir um possível piloto.",
      tone: "positive",
    };
  }

  return {
    label: "Leitura geral estável",
    title: "Nenhuma mudança importante identificada",
    description:
      "As duas análises encontraram sinais públicos parecidos sobre a startup.",
    whyItMatters:
      "A direção geral continua válida, mas ainda é importante confirmar os detalhes diretamente com a startup.",
    nextStep:
      "Avançar para uma conversa sobre arquitetura atual, prioridades técnicas e possíveis próximos passos.",
    tone: "neutral",
  };
}

function buildContinuityText(comparison: AnalysisComparison) {
  const maintainedTechnologies = getIntersection(
    getRecommendationNames(comparison.older),
    getRecommendationNames(comparison.newer),
  );

  const olderScores = comparison.older.research.classification;
  const newerScores = comparison.newer.research.classification;

  const messages: string[] = [];

  if (
    olderScores.ai_native_score === newerScores.ai_native_score
  ) {
    messages.push("O papel da IA no produto permaneceu parecido.");
  }

  if (
    olderScores.wrapper_risk_score === newerScores.wrapper_risk_score
  ) {
    messages.push(
      "A dependência de soluções externas continuou no mesmo nível.",
    );
  }

  if (maintainedTechnologies.length > 0) {
    messages.push(
      `${maintainedTechnologies[0]} continuou relevante nas duas análises.`,
    );
  }

  return (
    messages.join(" ") ||
    "A direção técnica continua parecida, mas alguns sinais públicos mudaram entre as análises."
  );
}

function App() {
  const [startups, setStartups] = useState<StartupHistoryItem[]>(
    [],
  );

  const [startupSearch, setStartupSearch] = useState("");

  const [pipelineStep, setPipelineStep] = useState(0);
  const [loadingPdf, setLoadingPdf] = useState(false);

  const [selectedAnalysis, setSelectedAnalysis] =
    useState<FullAnalysisResponse | null>(null);

  const [activeResultTab, setActiveResultTab] =
    useState<ResultTab>("summary");

  const [selectedStartupHistory, setSelectedStartupHistory] =
    useState<StartupAnalysesResponse | null>(null);

  const [comparisonMode, setComparisonMode] = useState(false);
  const [comparisonIds, setComparisonIds] = useState<string[]>([]);
  const [comparison, setComparison] =
    useState<AnalysisComparison | null>(null);

  const [startupName, setStartupName] = useState("");
  const [sector, setSector] = useState("");
  const [showNewAnalysisForm, setShowNewAnalysisForm] =
    useState(false);

  const [loadingHistory, setLoadingHistory] = useState(true);
  const [loadingAnalysis, setLoadingAnalysis] = useState(false);
  const [loadingStartupHistory, setLoadingStartupHistory] =
    useState(false);
  const [loadingSavedAnalysis, setLoadingSavedAnalysis] =
    useState(false);
  const [loadingComparison, setLoadingComparison] =
    useState(false);

  const [error, setError] = useState("");

  const filteredStartups = startups.filter((startup) =>
    startup.name
      .toLowerCase()
      .includes(startupSearch.trim().toLowerCase()),
  );

  async function loadHistory() {
    try {
      setError("");
      setLoadingHistory(true);

      const savedStartups = await getStartups();
      setStartups(savedStartups);
    } catch (requestError) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : "Ocorreu um erro inesperado.",
      );
    } finally {
      setLoadingHistory(false);
    }
  }

  useEffect(() => {
    let isActive = true;

    async function loadInitialHistory() {
      try {
        const savedStartups = await getStartups();

        if (isActive) {
          setStartups(savedStartups);
        }
      } catch (requestError) {
        if (isActive) {
          setError(
            requestError instanceof Error
              ? requestError.message
              : "Ocorreu um erro inesperado.",
          );
        }
      } finally {
        if (isActive) {
          setLoadingHistory(false);
        }
      }
    }

    void loadInitialHistory();

    return () => {
      isActive = false;
    };
  }, []);

  async function handleDownloadPdf() {
    if (!selectedAnalysis) {
      return;
    }

    try {
      setError("");
      setLoadingPdf(true);

      const pdf = await downloadAnalysisPdf(
        selectedAnalysis.analysis_id,
      );

      savePdfReport(
        pdf,
        selectedAnalysis.research.startup_name,
      );
    } catch (requestError) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : "Não foi possível baixar o relatório em PDF.",
      );
    } finally {
      setLoadingPdf(false);
    }
  }

  async function handleCreateAnalysis(event: FormEvent) {
    event.preventDefault();

    if (!startupName.trim()) {
      setError("Informe o nome da startup.");
      return;
    }

    let stageTimer: ReturnType<typeof window.setInterval> | undefined;

    try {
      setError("");
      setLoadingAnalysis(true);
      setSelectedAnalysis(null);
      setSelectedStartupHistory(null);
      setComparisonMode(false);
      setComparisonIds([]);
      setComparison(null);
      setPipelineStep(0);
      setActiveResultTab("summary");

      stageTimer = window.setInterval(() => {
        setPipelineStep((currentStep) =>
          Math.min(
            currentStep + 1,
            PIPELINE_STEPS.length - 1,
          ),
        );
      }, 3500);

      const analysis = await createFullAnalysis({
        startup_name: startupName.trim(),
        sector: sector.trim() || undefined,
        max_sources: 4,
      });

      setPipelineStep(PIPELINE_STEPS.length - 1);
      setSelectedAnalysis(analysis);
      setShowNewAnalysisForm(false);
      setStartupName("");
      setSector("");

      await loadHistory();
    } catch (requestError) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : "Ocorreu um erro inesperado.",
      );
    } finally {
      if (stageTimer) {
        window.clearInterval(stageTimer);
      }

      setLoadingAnalysis(false);
    }
  }

  async function handleOpenStartupHistory(
    startup: StartupHistoryItem,
  ) {
    try {
      setError("");
      setLoadingStartupHistory(true);
      setSelectedAnalysis(null);
      setShowNewAnalysisForm(false);
      setComparisonMode(false);
      setComparisonIds([]);
      setComparison(null);

      const history = await getStartupAnalyses(startup.startup_id);

      setSelectedStartupHistory(history);
    } catch (requestError) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : "Ocorreu um erro inesperado.",
      );
    } finally {
      setLoadingStartupHistory(false);
    }
  }

  async function handleOpenSavedAnalysis(analysisId: string) {
    try {
      setError("");
      setLoadingSavedAnalysis(true);

      const analysis = await getAnalysis(analysisId);

      setSelectedAnalysis(analysis);
      setActiveResultTab("summary");
      setComparisonMode(false);
      setComparisonIds([]);
      setComparison(null);
    } catch (requestError) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : "Não foi possível carregar a análise salva.",
      );
    } finally {
      setLoadingSavedAnalysis(false);
    }
  }

  function handleToggleComparisonMode() {
    setError("");
    setComparisonMode((current) => !current);
    setComparisonIds([]);
    setComparison(null);
    setSelectedAnalysis(null);
  }

  function handleToggleComparisonSelection(analysisId: string) {
    setError("");
    setComparison(null);

    if (comparisonIds.includes(analysisId)) {
      setComparisonIds((current) =>
        current.filter((id) => id !== analysisId),
      );

      return;
    }

    if (comparisonIds.length >= 2) {
      setError(
        "Escolha apenas duas análises para fazer uma comparação.",
      );

      return;
    }

    setComparisonIds((current) => [...current, analysisId]);
  }

  async function handleCompareAnalyses() {
    if (comparisonIds.length !== 2) {
      setError("Escolha duas análises para comparar.");
      return;
    }

    try {
      setError("");
      setLoadingComparison(true);
      setSelectedAnalysis(null);

      const analyses = await Promise.all(
        comparisonIds.map((analysisId) => getAnalysis(analysisId)),
      );

      const orderedAnalyses = [...analyses].sort(
        (first, second) =>
          new Date(first.briefing.generated_at).getTime() -
          new Date(second.briefing.generated_at).getTime(),
      );

      setComparison({
        older: orderedAnalyses[0],
        newer: orderedAnalyses[1],
      });
    } catch (requestError) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : "Não foi possível comparar as análises selecionadas.",
      );
    } finally {
      setLoadingComparison(false);
    }
  }

  function handleOpenComparisonAnalysis(
    analysis: FullAnalysisResponse,
  ) {
    setSelectedAnalysis(analysis);
    setActiveResultTab("summary");
    setComparisonMode(false);
    setComparisonIds([]);
    setComparison(null);
  }

  return (
    <main className="page">
      <header className="hero">
        <p className="eyebrow">NVIDIA Startup AI Radar</p>

        <h1>
          Inteligência para identificar oportunidades em startups.
        </h1>

      </header>

      <section className="panel">
        <div className="section-header">
          <div>
            <p className="eyebrow">Histórico:</p>
            <h2>Startups analisadas</h2>
          </div>

          <button
            type="button"
            onClick={() => {
              setShowNewAnalysisForm((current) => !current);
              setSelectedAnalysis(null);
              setSelectedStartupHistory(null);
              setComparisonMode(false);
              setComparisonIds([]);
              setComparison(null);
              setError("");
            }}
          >
            Nova análise
          </button>
        </div>

        {showNewAnalysisForm && (
          <form
            className="analysis-form"
            onSubmit={handleCreateAnalysis}
          >
            <label>
              Nome da startup:
              <input
                value={startupName}
                onChange={(event) =>
                  setStartupName(event.target.value)
                }
                placeholder="Ex.: Fintalk"
              />
            </label>

            <label>
              Setor de atuação:
              <input
                value={sector}
                onChange={(event) => setSector(event.target.value)}
                placeholder="Ex.: Fintech"
              />
            </label>

            <button type="submit" disabled={loadingAnalysis}>
              {loadingAnalysis ? "Analisando..." : "Iniciar análise"}
            </button>
          </form>
        )}

        {loadingHistory && <p>Carregando histórico...</p>}

        {error && <p className="error">{error}</p>}

        {loadingAnalysis && (
          <section className="pipeline-loading" aria-live="polite">
            <div className="pipeline-loading-header">
              <div>
                <p className="eyebrow">Etapas da análise:</p>
                <h3>Análise em andamento</h3>
              </div>

              <span className="pipeline-estimate">
                Progresso estimado
              </span>
            </div>

            <p className="pipeline-note">
              As informações são organizadas ao final da pesquisa e
              apresentadas em um único relatório.
            </p>

            <ol className="pipeline-steps">
              {PIPELINE_STEPS.map((step, index) => {
                const isCompleted = index < pipelineStep;
                const isCurrent = index === pipelineStep;

                return (
                  <li
                    className={[
                      "pipeline-step",
                      isCompleted ? "completed" : "",
                      isCurrent ? "current" : "",
                    ]
                      .filter(Boolean)
                      .join(" ")}
                    key={step.title}
                  >
                    <span className="pipeline-marker">
                      {isCompleted ? "✓" : index + 1}
                    </span>

                    <div>
                      <div className="pipeline-step-title">
                        <strong>{step.title}</strong>

                        {isCurrent && (
                          <span className="pipeline-status">
                            Em andamento
                          </span>
                        )}

                        {isCompleted && (
                          <span className="pipeline-status done">
                            Concluído
                          </span>
                        )}
                      </div>

                      <p>{step.description}</p>
                    </div>
                  </li>
                );
              })}
            </ol>
          </section>
        )}

        {!loadingHistory && startups.length === 0 && (
          <p>Nenhuma startup foi analisada ainda.</p>
        )}

        {!loadingHistory && startups.length > 0 && (
          <>
            <div className="startup-search">
              <input
                type="search"
                placeholder="Buscar startup analisada..."
                value={startupSearch}
                onChange={(event) =>
                  setStartupSearch(event.target.value)
                }
              />
            </div>

            {filteredStartups.length === 0 ? (
              <p>Nenhuma startup encontrada.</p>
            ) : (
              <div className="startup-list">
                {filteredStartups.map((startup) => (
                  <button
                    className="startup-card"
                    key={startup.startup_id}
                    type="button"
                    onClick={() =>
                      void handleOpenStartupHistory(startup)
                    }
                  >
                    <div>
                      <h3>{startup.name}</h3>

                      <p>{startup.sector || "Setor não informado"}</p>

                      <small>
                        Última análise:{" "}
                        {formatDate(startup.latest_analysis_at)}
                      </small>
                    </div>

                    <div className="startup-meta">
                      <span>
                        {startup.classification_category ||
                          "Sem classificação"}
                      </span>

                      <strong>
                        Oportunidade NVIDIA:{" "}
                        {startup.nvidia_opportunity_score ?? "-"}
                      </strong>
                    </div>
                  </button>
                ))}
              </div>
            )}
          </>
        )}
      </section>

      {loadingStartupHistory && (
        <section className="panel result-panel">
          <p>Carregando análises salvas...</p>
        </section>
      )}

      {selectedStartupHistory && !loadingStartupHistory && (
        <section className="panel result-panel">
          <div className="section-header">
            <div>
              <p className="eyebrow">Análises salvas:</p>
              <h2>{selectedStartupHistory.startup_name}</h2>
            </div>

            <div className="history-actions">
              {selectedStartupHistory.analyses.length >= 2 && (
                <button
                  className={
                    comparisonMode
                      ? "ghost-button active-history-action"
                      : "ghost-button"
                  }
                  type="button"
                  onClick={handleToggleComparisonMode}
                >
                  {comparisonMode
                    ? "Cancelar comparação"
                    : "Comparar análises"}
                </button>
              )}

              <button
                className="ghost-button"
                type="button"
                onClick={() => {
                  setSelectedStartupHistory(null);
                  setSelectedAnalysis(null);
                  setComparisonMode(false);
                  setComparisonIds([]);
                  setComparison(null);
                }}
              >
                Fechar
              </button>
            </div>
          </div>

          {comparisonMode && (
            <div className="comparison-selection-bar">
              <div>
                <strong>Escolha duas análises:</strong>

                <p>
                  Selecione duas versões para entender o que mudou nas
                  informações públicas encontradas.
                </p>
              </div>

              <button
                type="button"
                disabled={comparisonIds.length !== 2}
                onClick={() => void handleCompareAnalyses()}
              >
                Comparar selecionadas ({comparisonIds.length}/2)
              </button>
            </div>
          )}

          {selectedStartupHistory.analyses.length === 0 && (
            <p>Não há análises salvas para esta startup.</p>
          )}

          <div className="analysis-history-list">
            {selectedStartupHistory.analyses.map((analysis) => {
              const isSelected = comparisonIds.includes(
                analysis.analysis_id,
              );

              const selectedPosition =
                comparisonIds.indexOf(analysis.analysis_id) + 1;

              return (
                <button
                  className={[
                    "analysis-history-card",
                    comparisonMode ? "comparison-mode-card" : "",
                    isSelected ? "comparison-selected-card" : "",
                  ]
                    .filter(Boolean)
                    .join(" ")}
                  key={analysis.analysis_id}
                  type="button"
                  onClick={() => {
                    if (comparisonMode) {
                      handleToggleComparisonSelection(
                        analysis.analysis_id,
                      );

                      return;
                    }

                    void handleOpenSavedAnalysis(
                      analysis.analysis_id,
                    );
                  }}
                >
                  <div>
                    <h3>
                      Análise de {formatDate(analysis.created_at)}
                    </h3>

                    <p>
                      {formatClassification(
                        analysis.classification_category,
                      )}
                    </p>

                    {comparisonMode && (
                      <span className="comparison-card-label">
                        {isSelected
                          ? `Análise selecionada: ${selectedPosition}`
                          : "Selecionar para comparar"}
                      </span>
                    )}
                  </div>

                  <div className="analysis-history-meta">
                    <span>
                      Fontes consultadas: {analysis.sources_successful}
                    </span>

                    <span>
                      Pontos para validar: {analysis.gaps_count}
                    </span>

                    <strong>
                      Potencial NVIDIA:{" "}
                      {analysis.nvidia_opportunity_score ?? "-"}
                    </strong>
                  </div>
                </button>
              );
            })}
          </div>
        </section>
      )}

      {loadingComparison && (
        <section className="panel result-panel">
          <p>Preparando comparação entre as análises...</p>
        </section>
      )}

      {comparison && !loadingComparison && (
        <section className="panel result-panel comparison-panel">
          {(() => {
            const highlight = buildComparisonHighlight(comparison);

            const maintainedTechnologies = getIntersection(
              getRecommendationNames(comparison.older),
              getRecommendationNames(comparison.newer),
            );

            const olderTechnologies = [
              ...getRecommendationNames(comparison.older),
            ];

            const newerTechnologies = [
              ...getRecommendationNames(comparison.newer),
            ];

            return (
              <>
                <div className="section-header">
                  <div>
                    <p className="eyebrow">
                      Comparação entre análises:
                    </p>
                  </div>

                  <button
                    className="ghost-button"
                    type="button"
                    onClick={() => {
                      setComparison(null);
                      setComparisonIds([]);
                      setComparisonMode(false);
                    }}
                  >
                    Fechar comparação
                  </button>
                </div>

                <p className="comparison-disclaimer">
                  Esta tela compara informações públicas encontradas em
                  duas datas. Uma mudança pode acontecer porque novas
                  informações foram encontradas, porque fontes deixaram
                  de estar disponíveis ou porque a startup mudou.
                </p>

                <section className="comparison-now">
                  <div className="comparison-now-header">
                    <p className="eyebrow">
                      Principal mudança na análise recente:
                    </p>

                  </div>

                  <article
                    className={`comparison-highlight ${highlight.tone}`}
                  >
                    <span>{highlight.label}:</span>
                    <strong>{highlight.title}</strong>
                    <p>{ensurePeriod(highlight.description)}</p>
                  </article>

                  <div className="comparison-action-grid">
                    <article className="comparison-action-card attention">
                      <span>Por que isso importa:</span>

                      <strong>
                        Este ponto pode mudar a direção da próxima
                        conversa.
                      </strong>

                      <p>{ensurePeriod(highlight.whyItMatters)}</p>
                    </article>

                    <article className="comparison-action-card neutral">
                      <span>O que continua válido:</span>

                      <strong>
                        {maintainedTechnologies.length > 0
                          ? `${maintainedTechnologies[0]} continua relevante.`
                          : "A direção técnica geral continua parecida."}
                      </strong>

                      <p>
                        {ensurePeriod(
                          buildContinuityText(comparison),
                        )}
                      </p>
                    </article>

                    <article className="comparison-action-card positive">
                      <span>Próxima conversa sugerida:</span>

                      <strong>
                        Transforme a análise em uma ação prática.
                      </strong>

                      <p>{ensurePeriod(highlight.nextStep)}</p>
                    </article>
                  </div>
                </section>

                <details className="comparison-supporting-data comparison-visual-details">
                  <summary>
                    <span>Ver comparação lado a lado</span>

                    <small>
                      Veja claramente o que era antes e o que apareceu
                      agora.
                    </small>
                  </summary>

                  <div className="comparison-visual-header">
                    <div className="comparison-visual-header-label">
                      O que estamos comparando:
                    </div>

                    <div className="comparison-visual-header-old">
                      <span>Antes:</span>

                      <strong>
                        {formatDate(
                          comparison.older.briefing.generated_at,
                        )}
                      </strong>
                    </div>

                    <div className="comparison-visual-header-new">
                      <span>Agora:</span>

                      <strong>
                        {formatDate(
                          comparison.newer.briefing.generated_at,
                        )}
                      </strong>
                    </div>
                  </div>

                  <section className="comparison-visual-row">
                    <div className="comparison-visual-label">
                      <strong>Perfil identificado:</strong>
                      <span>Como a IA aparece no produto.</span>
                    </div>

                    <div className="comparison-visual-values">
                      <article className="comparison-visual-value old">
                        <span className="comparison-value-caption">
                          Antes:
                        </span>

                        <strong>
                          {formatClassification(
                            comparison.older.research.classification
                              .category,
                          )}
                        </strong>
                      </article>

                      <article className="comparison-visual-value new">
                        <span className="comparison-value-caption">
                          Agora:
                        </span>

                        <strong>
                          {formatClassification(
                            comparison.newer.research.classification
                              .category,
                          )}
                        </strong>
                      </article>
                    </div>
                  </section>

                  <section className="comparison-visual-row">
                    <div className="comparison-visual-label">
                      <strong>Papel da IA no produto:</strong>

                      <span>
                        Quanto a IA parece ser central para a solução.
                      </span>
                    </div>

                    <div className="comparison-visual-values">
                      <article className="comparison-visual-value old">
                        <span className="comparison-value-caption">
                          Antes:
                        </span>

                        <strong>
                          {describeAiRole(
                            comparison.older.research.classification
                              .ai_native_score,
                          )}
                        </strong>
                      </article>

                      <article className="comparison-visual-value new">
                        <span className="comparison-value-caption">
                          Agora:
                        </span>

                        <strong>
                          {describeAiRole(
                            comparison.newer.research.classification
                              .ai_native_score,
                          )}
                        </strong>
                      </article>
                    </div>
                  </section>

                  <section className="comparison-visual-row">
                    <div className="comparison-visual-label">
                      <strong>
                        Dependência de soluções externas:
                      </strong>

                      <span>
                        Quanto a startup depende de ferramentas de
                        terceiros.
                      </span>
                    </div>

                    <div className="comparison-visual-values">
                      <article className="comparison-visual-value old">
                        <span className="comparison-value-caption">
                          Antes:
                        </span>

                        <strong>
                          {describeExternalDependency(
                            comparison.older.research.classification
                              .wrapper_risk_score,
                          )}
                        </strong>
                      </article>

                      <article className="comparison-visual-value new">
                        <span className="comparison-value-caption">
                          Agora:
                        </span>

                        <strong>
                          {describeExternalDependency(
                            comparison.newer.research.classification
                              .wrapper_risk_score,
                          )}
                        </strong>
                      </article>
                    </div>
                  </section>

                  <section className="comparison-visual-row">
                    <div className="comparison-visual-label">
                      <strong>
                        Potencial de colaboração com NVIDIA:
                      </strong>

                      <span>
                        Leitura baseada nas informações públicas
                        encontradas.
                      </span>
                    </div>

                    <div className="comparison-visual-values">
                      <article className="comparison-visual-value old">
                        <span className="comparison-value-caption">
                          Antes:
                        </span>

                        <strong>
                          {describeNvidiaPotential(
                            comparison.older.research.classification
                              .nvidia_opportunity_score,
                          )}
                        </strong>
                      </article>

                      <article className="comparison-visual-value new">
                        <span className="comparison-value-caption">
                          Agora:
                        </span>

                        <strong>
                          {describeNvidiaPotential(
                            comparison.newer.research.classification
                              .nvidia_opportunity_score,
                          )}
                        </strong>
                      </article>
                    </div>
                  </section>

                  <section className="comparison-visual-row">
                    <div className="comparison-visual-label">
                      <strong>
                        Informações públicas encontradas:
                      </strong>

                      <span>
                        Elementos verificáveis usados na análise.
                      </span>
                    </div>

                    <div className="comparison-visual-values">
                      <article className="comparison-visual-value old">
                        <span className="comparison-value-caption">
                          Antes:
                        </span>

                        <strong>
                          {comparison.older.research.evidences.length}{" "}
                          informações
                        </strong>

                        <p>
                          {
                            comparison.older.research
                              .sources_successful
                          }{" "}
                          fontes consultadas.
                        </p>
                      </article>

                      <article className="comparison-visual-value new">
                        <span className="comparison-value-caption">
                          Agora:
                        </span>

                        <strong>
                          {comparison.newer.research.evidences.length}{" "}
                          informações
                        </strong>

                        <p>
                          {
                            comparison.newer.research
                              .sources_successful
                          }{" "}
                          fontes consultadas.
                        </p>
                      </article>
                    </div>
                  </section>

                  <section className="comparison-visual-row">
                    <div className="comparison-visual-label">
                      <strong>
                        Pontos que precisam ser confirmados:
                      </strong>

                      <span>
                        Assuntos que não ficaram claros nas fontes
                        públicas.
                      </span>
                    </div>

                    <div className="comparison-visual-values">
                      <article className="comparison-visual-value old">
                        <span className="comparison-value-caption">
                          Antes:
                        </span>

                        <div className="comparison-topic-list">
                          {comparison.older.research.gaps.length ===
                            0 && (
                              <p>
                                Nenhum ponto adicional identificado.
                              </p>
                            )}

                          {comparison.older.research.gaps.map(
                            (gap, index) => (
                              <span
                                className="comparison-chip"
                                key={`${gap.category}-${index}`}
                              >
                                {formatTopic(gap.category)}
                              </span>
                            ),
                          )}
                        </div>
                      </article>

                      <article className="comparison-visual-value new">
                        <span className="comparison-value-caption">
                          Agora:
                        </span>

                        <div className="comparison-topic-list">
                          {comparison.newer.research.gaps.length ===
                            0 && (
                              <p>
                                Nenhum ponto adicional identificado.
                              </p>
                            )}

                          {comparison.newer.research.gaps.map(
                            (gap, index) => (
                              <span
                                className="comparison-chip attention"
                                key={`${gap.category}-${index}`}
                              >
                                {formatTopic(gap.category)}
                              </span>
                            ),
                          )}
                        </div>
                      </article>
                    </div>
                  </section>

                  <section className="comparison-visual-row">
                    <div className="comparison-visual-label">
                      <strong>Tecnologias sugeridas:</strong>

                      <span>
                        Tecnologias relacionadas às necessidades
                        identificadas.
                      </span>
                    </div>

                    <div className="comparison-visual-values">
                      <article className="comparison-visual-value old">
                        <span className="comparison-value-caption">
                          Antes:
                        </span>

                        <div className="comparison-topic-list">
                          {olderTechnologies.length === 0 && (
                            <p>
                              Nenhuma tecnologia sugerida nesta análise.
                            </p>
                          )}

                          {olderTechnologies.map((technology) => (
                            <span
                              className="comparison-chip"
                              key={technology}
                            >
                              {technology}
                            </span>
                          ))}
                        </div>
                      </article>

                      <article className="comparison-visual-value new">
                        <span className="comparison-value-caption">
                          Agora:
                        </span>

                        <div className="comparison-topic-list">
                          {newerTechnologies.length === 0 && (
                            <p>
                              Nenhuma tecnologia sugerida nesta análise.
                            </p>
                          )}

                          {newerTechnologies.map((technology) => (
                            <span
                              className="comparison-chip added"
                              key={technology}
                            >
                              {technology}
                            </span>
                          ))}
                        </div>
                      </article>
                    </div>
                  </section>

                  <div className="comparison-analysis-links">
                    <button
                      className="ghost-button"
                      type="button"
                      onClick={() =>
                        handleOpenComparisonAnalysis(
                          comparison.older,
                        )
                      }
                    >
                      Ver análise anterior completa
                    </button>

                    <button
                      className="ghost-button"
                      type="button"
                      onClick={() =>
                        handleOpenComparisonAnalysis(
                          comparison.newer,
                        )
                      }
                    >
                      Ver análise recente completa
                    </button>
                  </div>
                </details>
              </>
            );
          })()}
        </section>
      )}

      {loadingSavedAnalysis && (
        <section className="panel result-panel">
          <p>Carregando resultado salvo...</p>
        </section>
      )}

      {selectedAnalysis && !loadingSavedAnalysis && (
        <section className="panel result-panel">
          <div className="section-header">
            <div>
              <p className="eyebrow">Resultado da análise:</p>
              <h2>{selectedAnalysis.research.startup_name}</h2>
            </div>

            <div className="result-actions">
              <button
                type="button"
                onClick={() =>
                  downloadBriefing(
                    selectedAnalysis.briefing.markdown,
                    selectedAnalysis.research.startup_name,
                  )
                }
              >
                Baixar relatório em .md
              </button>

              <button
                type="button"
                disabled={loadingPdf}
                onClick={() => void handleDownloadPdf()}
              >
                {loadingPdf
                  ? "Preparando PDF..."
                  : "Baixar relatório em PDF"}
              </button>
            </div>
          </div>

          <div className="result-tabs">
            <button
              className={
                activeResultTab === "summary"
                  ? "result-tab active"
                  : "result-tab"
              }
              type="button"
              onClick={() => setActiveResultTab("summary")}
            >
              Visão geral
            </button>

            <button
              className={
                activeResultTab === "recommendations"
                  ? "result-tab active"
                  : "result-tab"
              }
              type="button"
              onClick={() => setActiveResultTab("recommendations")}
            >
              Tecnologias NVIDIA
            </button>

            <button
              className={
                activeResultTab === "flight-plan"
                  ? "result-tab active"
                  : "result-tab"
              }
              type="button"
              onClick={() => setActiveResultTab("flight-plan")}
            >
              Plano de 90 dias
            </button>

            <button
              className={
                activeResultTab === "nvidia-context"
                  ? "result-tab active"
                  : "result-tab"
              }
              type="button"
              onClick={() => setActiveResultTab("nvidia-context")}
            >
              Documentação NVIDIA
            </button>

            <button
              className={
                activeResultTab === "evidences"
                  ? "result-tab active"
                  : "result-tab"
              }
              type="button"
              onClick={() => setActiveResultTab("evidences")}
            >
              Fontes e informações
            </button>

            <button
              className={
                activeResultTab === "briefing"
                  ? "result-tab active"
                  : "result-tab"
              }
              type="button"
              onClick={() => setActiveResultTab("briefing")}
            >
              Relatório completo
            </button>
          </div>

          {activeResultTab === "summary" && (
            <div className="tab-content">
              <div className="score-grid">
                <article>
                  <span>Perfil identificado:</span>
                  <strong>
                    {formatClassification(
                      selectedAnalysis.research.classification.category,
                    )}
                  </strong>
                </article>

                <article>
                  <span>Papel da IA no produto:</span>
                  <strong>
                    {describeAiRole(
                      selectedAnalysis.research.classification
                        .ai_native_score,
                    )}
                  </strong>
                </article>

                <article>
                  <span>Dependência de soluções externas:</span>
                  <strong>
                    {describeExternalDependency(
                      selectedAnalysis.research.classification
                        .wrapper_risk_score,
                    )}
                  </strong>
                </article>

                <article>
                  <span>Potencial de colaboração com NVIDIA:</span>
                  <strong>
                    {describeNvidiaPotential(
                      selectedAnalysis.research.classification
                        .nvidia_opportunity_score,
                    )}
                  </strong>
                </article>
              </div>

              <div className="summary-details">
                <article>
                  <span>Fontes consultadas:</span>
                  <strong>
                    {selectedAnalysis.research.sources_successful}
                  </strong>
                </article>

                <article>
                  <span>Informações verificáveis encontradas:</span>
                  <strong>
                    {selectedAnalysis.research.evidences.length}
                  </strong>
                </article>

                <article>
                  <span>Pontos que precisam de validação:</span>
                  <strong>
                    {selectedAnalysis.research.gaps.length}
                  </strong>
                </article>
              </div>

              <h3>Pontos que ainda precisam de validação:</h3>

              {selectedAnalysis.research.gaps.length === 0 && (
                <p>
                  Nenhum ponto relevante ficou sem informação pública.
                </p>
              )}

              <div className="gap-list">
                {selectedAnalysis.research.gaps.map((gap, index) => (
                  <article
                    className="gap-card"
                    key={`${gap.category}-${index}`}
                  >
                    <strong>{formatTopic(gap.category)}:</strong>
                    <p>{ensurePeriod(gap.message)}</p>
                  </article>
                ))}
              </div>
            </div>
          )}

          {activeResultTab === "recommendations" && (
            <div className="tab-content">
              <h3>Tecnologias NVIDIA sugeridas:</h3>

              <div className="recommendation-list">
                {selectedAnalysis.recommendations.recommendations.map(
                  (recommendation) => (
                    <article
                      className="recommendation-card"
                      key={recommendation.technology_id}
                    >
                      <div className="recommendation-header">
                        <h4>{recommendation.technology_name}</h4>

                        <span>
                          {formatPriority(recommendation.priority)}
                        </span>
                      </div>

                      <p>
                        <strong>Complexidade de adoção:</strong>{" "}
                        {formatComplexity(recommendation.complexity)}.
                      </p>

                      <p>
                        <strong>Por que faz sentido tecnicamente:</strong>{" "}
                        {ensurePeriod(recommendation.technical_reason)}
                      </p>

                      <p>
                        <strong>Valor esperado para o negócio:</strong>{" "}
                        {ensurePeriod(recommendation.business_reason)}
                      </p>

                      <p>
                        <strong>Próximo passo sugerido:</strong>{" "}
                        {ensurePeriod(recommendation.next_action)}
                      </p>

                      <details className="recommendation-evidences">
                        <summary>
                          Ver informações que apoiam esta sugestão
                        </summary>

                        <div className="recommendation-evidence-grid">
                          <section>
                            <h5>Informações sobre a startup:</h5>

                            {recommendation.startup_evidences.map(
                              (evidence, index) => (
                                <article
                                  className="recommendation-evidence-card"
                                  key={`${evidence.source_url}-${index}`}
                                >
                                  <blockquote>
                                    {evidence.quote}
                                  </blockquote>

                                  <a
                                    href={evidence.source_url}
                                    target="_blank"
                                    rel="noreferrer"
                                  >
                                    Abrir fonte
                                  </a>
                                </article>
                              ),
                            )}
                          </section>

                          <section>
                            <h5>Documentação oficial NVIDIA:</h5>

                            {recommendation.nvidia_evidences.map(
                              (evidence, index) => (
                                <article
                                  className="recommendation-evidence-card"
                                  key={`${evidence.source_url}-${index}`}
                                >
                                  <blockquote>
                                    {evidence.quote}
                                  </blockquote>

                                  <a
                                    href={evidence.source_url}
                                    target="_blank"
                                    rel="noreferrer"
                                  >
                                    Abrir documentação NVIDIA
                                  </a>
                                </article>
                              ),
                            )}
                          </section>
                        </div>
                      </details>
                    </article>
                  ),
                )}
              </div>
            </div>
          )}

          {activeResultTab === "flight-plan" && (
            <div className="tab-content">
              {!selectedAnalysis.briefing.flight_plan ||
                selectedAnalysis.briefing.flight_plan.phases.length === 0 ? (
                <p>
                  Esta análise foi salva antes da criação do plano de 90
                  dias. Faça uma nova análise para gerar o plano.
                </p>
              ) : (
                <>
                  <div className="flight-plan-intro">
                    <div>
                      <p className="eyebrow">
                        Plano técnico e comercial:
                      </p>

                      <h3>
                        {selectedAnalysis.briefing.flight_plan.title}
                      </h3>
                    </div>

                    <span>
                      {
                        selectedAnalysis.briefing.flight_plan.phases
                          .length
                      }{" "}
                      fases
                    </span>
                  </div>

                  <p className="flight-plan-summary">
                    {ensurePeriod(
                      selectedAnalysis.briefing.flight_plan.summary,
                    )}
                  </p>

                  <div className="flight-plan-timeline">
                    {selectedAnalysis.briefing.flight_plan.phases.map(
                      (phase, index) => (
                        <article
                          className="flight-plan-phase"
                          key={phase.period}
                        >
                          <div className="flight-plan-marker">
                            <span>{index + 1}</span>
                            <strong>{phase.period}</strong>
                          </div>

                          <div className="flight-plan-card">
                            <h4>{phase.title}</h4>

                            <p>
                              <strong>Objetivo:</strong>{" "}
                              {ensurePeriod(phase.objective)}
                            </p>

                            <div className="flight-plan-section">
                              <strong>Ações sugeridas:</strong>

                              <ul>
                                {phase.actions.map((action) => (
                                  <li key={action}>
                                    {ensurePeriod(action)}
                                  </li>
                                ))}
                              </ul>
                            </div>

                            <div className="flight-plan-section">
                              <strong>
                                Tecnologias NVIDIA relacionadas:
                              </strong>

                              <div className="flight-plan-technologies">
                                {phase.nvidia_technologies.map(
                                  (technology) => (
                                    <span key={technology}>
                                      {technology}
                                    </span>
                                  ),
                                )}
                              </div>
                            </div>

                            <div className="flight-plan-section">
                              <strong>Como saber se deu certo:</strong>

                              <ul>
                                {phase.success_criteria.map(
                                  (criterion) => (
                                    <li key={criterion}>
                                      {ensurePeriod(criterion)}
                                    </li>
                                  ),
                                )}
                              </ul>
                            </div>
                          </div>
                        </article>
                      ),
                    )}
                  </div>
                </>
              )}
            </div>
          )}

          {activeResultTab === "nvidia-context" && (
            <div className="tab-content">
              {!selectedAnalysis.nvidia_context && (
                <p>
                  Esta análise não possui documentação NVIDIA associada.
                </p>
              )}

              {selectedAnalysis.nvidia_context && (
                <>
                  <div className="rag-intro">
                    <div>
                      <p className="eyebrow">
                        Documentação oficial consultada:
                      </p>

                      <h3>
                        Tecnologias relacionadas às necessidades
                        identificadas
                      </h3>
                    </div>

                    <span>
                      {
                        selectedAnalysis.nvidia_context.technologies
                          .length
                      }{" "}
                      tecnologias encontradas
                    </span>
                  </div>

                  <details className="rag-queries">
                    <summary>
                      Ver termos usados na pesquisa da documentação
                    </summary>

                    <ol>
                      {selectedAnalysis.nvidia_context.generated_queries.map(
                        (query) => (
                          <li key={query}>{query}</li>
                        ),
                      )}
                    </ol>
                  </details>

                  <div className="rag-technology-list">
                    {selectedAnalysis.nvidia_context.technologies.map(
                      (technology) => (
                        <article
                          className="rag-technology-card"
                          key={technology.technology_id}
                        >
                          <div className="rag-technology-header">
                            <div>
                              <p className="eyebrow">
                                Tecnologia relacionada:
                              </p>

                              <h4>{technology.technology_name}</h4>
                            </div>

                            <span>
                              {technology.evidences.length} trecho
                              {technology.evidences.length !== 1
                                ? "s"
                                : ""}
                            </span>
                          </div>

                          <div className="rag-reasons">
                            <strong>
                              Por que esta tecnologia foi considerada:
                            </strong>

                            <ul>
                              {technology.why_retrieved.map(
                                (reason) => (
                                  <li key={reason}>
                                    {ensurePeriod(reason)}
                                  </li>
                                ),
                              )}
                            </ul>
                          </div>

                          <div className="rag-evidence-list">
                            {technology.evidences.map(
                              (evidence, index) => (
                                <article
                                  className="rag-evidence-card"
                                  key={`${evidence.source_url}-${index}`}
                                >
                                  <div className="rag-evidence-header">
                                    <strong>{evidence.title}</strong>

                                    <span>
                                      Relevância:{" "}
                                      {Math.round(
                                        evidence.rerank_score * 100,
                                      )}
                                      %
                                    </span>
                                  </div>

                                  <div className="rag-tags">
                                    {evidence.tags.map((tag) => (
                                      <span key={tag}>{tag}</span>
                                    ))}
                                  </div>

                                  <blockquote>
                                    {evidence.text.length > 650
                                      ? `${evidence.text.slice(
                                        0,
                                        650,
                                      )}...`
                                      : evidence.text}
                                  </blockquote>

                                  <a
                                    href={evidence.source_url}
                                    target="_blank"
                                    rel="noreferrer"
                                  >
                                    Abrir documentação oficial NVIDIA
                                  </a>
                                </article>
                              ),
                            )}
                          </div>
                        </article>
                      ),
                    )}
                  </div>
                </>
              )}
            </div>
          )}

          {activeResultTab === "evidences" && (
            <div className="tab-content">
              <h3>Fontes públicas consultadas:</h3>

              <div className="source-list">
                {selectedAnalysis.research.sources.map((source) => (
                  <article className="source-card" key={source.url}>
                    <div>
                      <h4>{source.title || "Fonte sem título"}</h4>

                      <p>
                        Situação:{" "}
                        <strong>
                          {formatSourceStatus(source.status)}
                        </strong>
                        .
                      </p>

                      {source.word_count && (
                        <p>
                          {source.word_count} palavras identificadas.
                        </p>
                      )}
                    </div>

                    <a
                      href={source.url}
                      target="_blank"
                      rel="noreferrer"
                    >
                      Abrir fonte
                    </a>
                  </article>
                ))}
              </div>

              <h3>Informações identificadas:</h3>

              <div className="evidence-list">
                {selectedAnalysis.research.evidences.map(
                  (evidence, index) => (
                    <details
                      className="evidence-card"
                      key={`${evidence.source_url}-${index}`}
                    >
                      <summary>
                        <strong>
                          {formatTopic(evidence.category)}:
                        </strong>

                        <span>
                          {ensurePeriod(evidence.claim)}
                        </span>
                      </summary>

                      <p>
                        <strong>Trecho encontrado:</strong>
                      </p>

                      <blockquote>{evidence.quote}</blockquote>

                      <a
                        href={evidence.source_url}
                        target="_blank"
                        rel="noreferrer"
                      >
                        Abrir fonte desta informação
                      </a>
                    </details>
                  ),
                )}
              </div>
            </div>
          )}

          {activeResultTab === "briefing" && (
            <div className="tab-content">
              <div className="briefing-content">
                <ReactMarkdown remarkPlugins={[remarkGfm]}>
                  {selectedAnalysis.briefing.markdown}
                </ReactMarkdown>
              </div>
            </div>
          )}
        </section>
      )}
    </main>
  );
}

export default App;