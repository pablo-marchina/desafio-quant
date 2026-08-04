"""Golden set de startups de referência para medir precisão do motor de recomendações.

6 arquétipos cobrindo os principais perfis do portfólio NVIDIA Radar:
  1. LLM inference startup  (AI-native, nlp, production)
  2. API-only AI startup     (AI-enabled, nlp, mvp) — sem modelo próprio
  3. SaaS sem workload NVIDIA (non_ai)
  4. Computer vision startup (AI-native, vision, pilot)
  5. Tabular analytics       (AI-enabled, analytics, production)
  6. Enterprise MLOps        (AI-native, mlops, scale)

Métricas calculadas:
  - precision@3: fração dos top-3 slugs que estão no conjunto esperado
  - false_positives: slugs claramente fora do perfil que apareceram nos resultados
  - strong_count: número de recomendações com nivel="forte" por arquétipo

Atualizar os expected_slugs e banned_slugs quando o catálogo ou os limiares
mudar. Os valores numéricos das asserções são pisos deliberadamente conservadores:
é mais útil falhar quando um arquétipo PERDE uma recomendação esperada do que
quando um artefato de ajuste fino muda um score em 2%.
"""

from uuid import uuid4

import pytest

from apps.api.src.modules.recommendations.domain.policies import (
    EvidenceSignal,
    MatchResult,
    NIVEL_FORTE,
    StartupAIContext,
    TechnologyCandidate,
    match_technologies,
)

# ---------------------------------------------------------------------------
# Catálogo completo (cópia dos valores reais de catalog_data.py).
# Atualizar aqui se o catálogo mudar — manter sincronizado é intencional:
# o golden set deve falhar quando o catálogo mudar de forma inesperada.
# ---------------------------------------------------------------------------

FULL_CATALOG: list[TechnologyCandidate] = [
    TechnologyCandidate(
        slug="nvidia-nim",
        name="NVIDIA NIM",
        category="model_serving",
        use_cases=("servir LLMs e modelos generativos em producao",),
        keywords=("llm", "generative ai", "inference", "api", "deployment", "microservice"),
        complexity="low",
        supported_workloads={"nlp": 0.80, "speech": 0.50, "recommendation": 0.40, "analytics": 0.40, "vision": 0.30, "mlops": 0.50},
    ),
    TechnologyCandidate(
        slug="nvidia-nemo",
        name="NVIDIA NeMo",
        category="model_training",
        use_cases=("fine-tuning de modelos generativos",),
        keywords=("training", "fine tuning", "llm", "agent", "generative ai", "speech"),
        complexity="high",
        supported_workloads={"nlp": 0.90, "speech": 0.70, "mlops": 0.50, "vision": 0.20},
    ),
    TechnologyCandidate(
        slug="triton-inference-server",
        name="NVIDIA Triton Inference Server",
        category="model_serving",
        use_cases=("serving multi-modelo em producao",),
        keywords=("model serving", "kubernetes", "inference", "batching", "pytorch", "onnx"),
        complexity="medium",
        supported_workloads={"mlops": 0.70, "vision": 0.60, "nlp": 0.55, "analytics": 0.50, "speech": 0.50, "recommendation": 0.45},
    ),
    TechnologyCandidate(
        slug="tensorrt-llm",
        name="TensorRT-LLM",
        category="model_optimization",
        use_cases=("otimizar inferencia de LLMs",),
        keywords=("llm", "optimization", "inference", "throughput", "token", "quantization"),
        complexity="high",
        supported_workloads={"nlp": 0.95, "speech": 0.30, "vision": 0.20},
    ),
    TechnologyCandidate(
        slug="tensorrt",
        name="NVIDIA TensorRT",
        category="model_optimization",
        use_cases=("otimizar modelos PyTorch, TensorFlow ou ONNX",),
        keywords=("onnx", "pytorch", "tensorflow", "optimization", "latency", "inference"),
        complexity="high",
        supported_workloads={"vision": 0.70, "mlops": 0.60, "nlp": 0.50, "analytics": 0.40, "speech": 0.30},
    ),
    TechnologyCandidate(
        slug="rapids",
        name="RAPIDS",
        category="data_science",
        use_cases=("acelerar pipelines de data science",),
        keywords=("data science", "analytics", "dataframe", "gpu", "pandas", "spark"),
        complexity="medium",
        supported_workloads={"analytics": 0.95, "recommendation": 0.75, "mlops": 0.60, "vision": 0.20},
    ),
    TechnologyCandidate(
        slug="riva",
        name="NVIDIA Riva",
        category="speech_ai",
        use_cases=("automatic speech recognition",),
        keywords=("speech", "asr", "tts", "voice", "translation", "conversational ai"),
        complexity="medium",
        supported_workloads={"speech": 0.99, "nlp": 0.40},
    ),
    TechnologyCandidate(
        slug="cuda",
        name="NVIDIA CUDA",
        category="accelerated_computing",
        use_cases=("acelerar computacao numerica",),
        keywords=("gpu", "accelerated computing", "c++", "kernel", "hpc", "parallel computing"),
        complexity="high",
        supported_workloads={"analytics": 0.55, "simulation": 0.60, "mlops": 0.50, "vision": 0.45, "nlp": 0.30, "recommendation": 0.30},
    ),
    TechnologyCandidate(
        slug="nvidia-ai-enterprise",
        name="NVIDIA AI Enterprise",
        category="ai_platform",
        use_cases=("padronizar stack corporativa de IA",),
        keywords=("enterprise", "platform", "governance", "deployment", "support", "infrastructure"),
        complexity="medium",
        supported_workloads={"mlops": 0.70, "nlp": 0.55, "analytics": 0.55, "vision": 0.45, "speech": 0.35},
    ),
    TechnologyCandidate(
        slug="monai",
        name="MONAI",
        category="healthcare_ai",
        use_cases=("analise de imagens medicas",),
        keywords=("healthcare", "medical imaging", "monai", "segmentation", "radiology", "clinical ai"),
        complexity="high",
        supported_workloads={"vision": 0.95, "analytics": 0.30},
    ),
    TechnologyCandidate(
        slug="nvidia-inception",
        name="NVIDIA Inception",
        category="startup_program",
        use_cases=("acessar credits de cloud e GPU para startups",),
        keywords=("startup", "inception", "credits", "mentoria", "comunidade", "investidores", "go-to-market"),
        complexity="low",
        supported_workloads={"nlp": 0.40, "vision": 0.40, "analytics": 0.40, "speech": 0.40, "mlops": 0.40, "recommendation": 0.40, "simulation": 0.40},
    ),
    TechnologyCandidate(
        slug="nemo-guardrails",
        name="NeMo Guardrails",
        category="model_training",
        use_cases=("controlar topicos permitidos em assistentes de IA",),
        keywords=("guardrails", "safety", "llm", "agent", "conversational ai", "governance"),
        complexity="medium",
        supported_workloads={"nlp": 0.90, "recommendation": 0.25},
    ),
    TechnologyCandidate(
        slug="nvidia-clara",
        name="NVIDIA Clara",
        category="healthcare_ai",
        use_cases=("acelerar pesquisa em genomica e descoberta de farmacos",),
        keywords=("healthcare", "life sciences", "genomics", "medical imaging", "clara", "drug discovery"),
        complexity="high",
        supported_workloads={"vision": 0.80, "analytics": 0.55},
    ),
    TechnologyCandidate(
        slug="cudf",
        name="cuDF",
        category="data_science",
        use_cases=("acelerar processamento de dataframes em GPU",),
        keywords=("dataframe", "pandas", "gpu", "rapids", "etl", "data science"),
        complexity="low",
        supported_workloads={"analytics": 0.95, "recommendation": 0.55, "mlops": 0.50},
    ),
    TechnologyCandidate(
        slug="cuml",
        name="cuML",
        category="data_science",
        use_cases=("treinar modelos de machine learning classico em GPU",),
        keywords=("machine learning", "scikit-learn", "gpu", "rapids", "clustering", "classification"),
        complexity="low",
        supported_workloads={"analytics": 0.85, "recommendation": 0.70, "mlops": 0.70},
    ),
    TechnologyCandidate(
        slug="nvidia-omniverse",
        name="NVIDIA Omniverse",
        category="robotics_simulation",
        use_cases=("criar digital twins de fabricas e ambientes industriais",),
        keywords=("simulation", "3d", "digital twin", "omniverse", "openusd", "virtual world"),
        complexity="high",
        supported_workloads={"simulation": 0.99, "vision": 0.45},
    ),
    TechnologyCandidate(
        slug="nvidia-isaac",
        name="NVIDIA Isaac",
        category="robotics_simulation",
        use_cases=("simular e treinar robos antes de implantar no mundo real",),
        keywords=("robotics", "isaac", "simulation", "autonomy", "navigation", "perception"),
        complexity="high",
        supported_workloads={"simulation": 0.95, "vision": 0.35},
    ),
    TechnologyCandidate(
        slug="nvidia-morpheus",
        name="NVIDIA Morpheus",
        category="cybersecurity",
        use_cases=("detectar anomalias e ameacas de seguranca em tempo real",),
        keywords=("cybersecurity", "morpheus", "threat detection", "anomaly detection", "security", "incident response"),
        complexity="high",
        supported_workloads={"analytics": 0.65},
    ),
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _slug_rank(results: list[MatchResult], slug: str) -> int | None:
    """Posição (1-based) de um slug nos resultados, ou None se ausente."""
    for i, r in enumerate(results, start=1):
        if r.technology.slug == slug:
            return i
    return None


def _top_k_slugs(results: list[MatchResult], k: int = 3) -> set[str]:
    return {r.technology.slug for r in results[:k]}


def _precision_at_k(results: list[MatchResult], expected: list[str], k: int = 3) -> float:
    """Fração dos top-k resultados que está em expected."""
    top = _top_k_slugs(results, k)
    hits = top & set(expected)
    denominator = min(k, len(expected))
    return len(hits) / denominator if denominator else 0.0


def _false_positive_slugs(results: list[MatchResult], banned: list[str]) -> set[str]:
    """Slugs que aparecem nos resultados mas estão na lista de banidos."""
    result_slugs = {r.technology.slug for r in results}
    return result_slugs & set(banned)


def _evidence(text: str, confidence: float = 0.85) -> EvidenceSignal:
    return EvidenceSignal(evidence_id=uuid4(), text=text.lower(), confidence_score=confidence)


# ---------------------------------------------------------------------------
# Arquétipo 1 — LLM inference startup (AI-native, nlp, production)
# ---------------------------------------------------------------------------


def test_archetype_llm_inference_top3_contains_nim_triton_tensorrt_llm() -> None:
    """Startup que serve LLMs próprios em produção: NIM, Triton e TensorRT-LLM devem aparecer no top-3."""

    results = match_technologies(
        sector="generative ai",
        description=(
            "Platform for running LLM inference as microservices with standardized APIs. "
            "Optimizes token throughput and deployment for production workloads."
        ),
        ai_maturity_level="ai_native",
        ai_context=StartupAIContext(
            ai_workload_type="nlp",
            deployment_stage="production",
            gpu_need="high",
            has_operational_signal=True,
        ),
        evidence_signals=[
            _evidence(
                "Runs PyTorch and ONNX models with batching and Kubernetes orchestration "
                "for model serving. GPU-accelerated inference with quantization and throughput optimization."
            ),
        ],
        technologies=FULL_CATALOG,
    )

    # Pelo menos 2 dos 3 esperados no top-3
    assert _precision_at_k(results, ["nvidia-nim", "triton-inference-server", "tensorrt-llm"]) >= 0.66, (
        f"top-3 obtido: {list(_top_k_slugs(results))}"
    )
    # Nenhum falso positivo claro
    assert _false_positive_slugs(results, ["riva", "monai", "nvidia-clara", "nvidia-omniverse", "nvidia-isaac"]) == set()
    # Startup AI-native com boa evidência deve ter pelo menos 1 recomendação forte
    assert any(r.nivel == NIVEL_FORTE for r in results), "Nenhuma recomendação forte para LLM inference startup"


def test_archetype_llm_inference_results_are_ordered_by_score() -> None:
    results = match_technologies(
        sector="generative ai",
        description="LLM inference platform with API microservices and production deployment pipeline.",
        ai_maturity_level="ai_native",
        ai_context=StartupAIContext(ai_workload_type="nlp", deployment_stage="production", gpu_need="high"),
        evidence_signals=[_evidence("PyTorch ONNX batching model serving kubernetes inference throughput token")],
        technologies=FULL_CATALOG,
    )

    scores = [r.score for r in results]
    assert scores == sorted(scores, reverse=True), "Resultados devem estar ordenados por score decrescente"


# ---------------------------------------------------------------------------
# Arquétipo 2 — API-only AI startup (AI-enabled, consome LLM via API, sem modelo próprio)
# ---------------------------------------------------------------------------


def test_archetype_api_only_has_no_strong_recommendations() -> None:
    """Startup que usa LLM só via API externa não deve ter recomendações fortes de GPU."""

    results = match_technologies(
        sector="saas",
        description=(
            "B2B SaaS with an AI assistant powered by generative AI API calls. "
            "Uses third-party foundation model API for natural language features, no own GPU infrastructure."
        ),
        ai_maturity_level="ai_enabled",
        ai_context=StartupAIContext(
            ai_workload_type="nlp",
            deployment_stage="mvp",
            gpu_need="low",
            has_operational_signal=False,
        ),
        evidence_signals=[],
        technologies=FULL_CATALOG,
    )

    strong = [r for r in results if r.nivel == NIVEL_FORTE]
    assert len(strong) == 0, (
        f"API-only startup não deveria ter recomendações fortes, mas obteve: "
        f"{[r.technology.slug for r in strong]}"
    )

    # NeMo (treinamento) e TensorRT-LLM (infra pesada) não deveriam aparecer
    # para uma startup que apenas consome API
    training_heavy = _false_positive_slugs(results, ["nvidia-nemo", "tensorrt-llm"])
    assert training_heavy == set(), (
        f"Startup API-only não deveria recomendar infra pesada: {training_heavy}"
    )


# ---------------------------------------------------------------------------
# Arquétipo 3 — SaaS sem workload NVIDIA (non_ai)
# ---------------------------------------------------------------------------


def test_archetype_no_ai_workload_gets_no_technical_nvidia_recs() -> None:
    """SaaS puro de RH sem IA técnica não deve receber nenhuma tech NVIDIA pesada."""

    results = match_technologies(
        sector="hr tech",
        description=(
            "Human resources management platform with workflow automation and reporting dashboards. "
            "Helps HR teams manage onboarding, payroll and performance reviews."
        ),
        ai_maturity_level="non_ai",
        ai_context=StartupAIContext(
            ai_workload_type="unknown",
            deployment_stage="production",
            gpu_need="low",
            has_operational_signal=False,
        ),
        evidence_signals=[],
        technologies=FULL_CATALOG,
    )

    technical_slugs = {
        "tensorrt-llm", "nvidia-nemo", "triton-inference-server", "tensorrt",
        "rapids", "riva", "monai", "nvidia-clara", "cuda",
    }
    technical_hits = {r.technology.slug for r in results} & technical_slugs
    assert technical_hits == set(), (
        f"SaaS de RH não deveria receber tech NVIDIA técnica, mas obteve: {technical_hits}"
    )


# ---------------------------------------------------------------------------
# Arquétipo 4 — Computer vision startup (AI-native, vision, pilot)
# ---------------------------------------------------------------------------


def test_archetype_computer_vision_matches_tensorrt_and_triton() -> None:
    """Startup de visão computacional: TensorRT e Triton devem aparecer no top-3."""

    results = match_technologies(
        sector="computer vision",
        description=(
            "AI platform for visual inspection and defect detection in manufacturing. "
            "Uses deep learning for image segmentation and object detection with optimized inference."
        ),
        ai_maturity_level="ai_native",
        ai_context=StartupAIContext(
            ai_workload_type="vision",
            deployment_stage="pilot",
            gpu_need="high",
            has_operational_signal=False,
        ),
        evidence_signals=[
            _evidence(
                "PyTorch models exported to ONNX for latency-optimized inference. "
                "Serving pipeline with batching and model optimization for edge deployment."
            ),
        ],
        technologies=FULL_CATALOG,
    )

    assert _precision_at_k(results, ["tensorrt", "triton-inference-server"], k=3) >= 0.66, (
        f"top-3 obtido: {list(_top_k_slugs(results))}"
    )
    # RAPIDS e Riva são claramente fora do perfil de visão computacional industrial
    assert _false_positive_slugs(results, ["rapids", "riva", "cudf", "cuml"]) == set()


def test_archetype_computer_vision_monai_absent_without_healthcare_signal() -> None:
    """MONAI só deve aparecer se houver sinal de healthcare — visão industrial não qualifica."""

    results = match_technologies(
        sector="computer vision",
        description="Industrial visual inspection AI using deep learning image analysis.",
        ai_maturity_level="ai_native",
        ai_context=StartupAIContext(ai_workload_type="vision", deployment_stage="pilot", gpu_need="high"),
        evidence_signals=[_evidence("pytorch onnx inference optimization latency batching")],
        technologies=FULL_CATALOG,
    )

    assert _false_positive_slugs(results, ["monai", "nvidia-clara"]) == set()


# ---------------------------------------------------------------------------
# Arquétipo 5 — Tabular analytics startup (AI-enabled, analytics, production)
# ---------------------------------------------------------------------------


def test_archetype_tabular_analytics_matches_rapids_cudf_cuml() -> None:
    """Startup de analytics tabular: RAPIDS, cuDF e cuML devem dominar o top-3."""

    results = match_technologies(
        sector="data analytics",
        description=(
            "Data science platform accelerating ML pipelines on large tabular datasets "
            "with GPU-powered pandas and dataframe operations for faster analytics."
        ),
        ai_maturity_level="ai_enabled",
        ai_context=StartupAIContext(
            ai_workload_type="analytics",
            deployment_stage="production",
            gpu_need="high",
            has_operational_signal=True,
        ),
        evidence_signals=[
            _evidence(
                "ETL pipelines migrated from pandas to GPU-accelerated dataframes. "
                "Machine learning with scikit-learn compatible API. "
                "Clustering and classification on data science workflows at scale."
            ),
        ],
        technologies=FULL_CATALOG,
    )

    assert _precision_at_k(results, ["rapids", "cudf", "cuml"]) >= 0.66, (
        f"top-3 obtido: {list(_top_k_slugs(results))}"
    )
    # LLM e speech tech não fazem sentido aqui
    assert _false_positive_slugs(results, ["riva", "monai", "nvidia-clara", "tensorrt-llm", "nvidia-nemo"]) == set()


# ---------------------------------------------------------------------------
# Arquétipo 6 — Enterprise MLOps (AI-native, mlops, scale)
# ---------------------------------------------------------------------------


def test_archetype_enterprise_mlops_matches_ai_enterprise_and_triton() -> None:
    """Plataforma de MLOps enterprise: AI Enterprise e Triton devem aparecer no top-3."""

    results = match_technologies(
        sector="mlops",
        description=(
            "Enterprise AI platform for training, deploying and governing ML models at scale. "
            "Provides infrastructure and support for Kubernetes-based model serving "
            "with enterprise governance and deployment pipelines."
        ),
        ai_maturity_level="ai_native",
        ai_context=StartupAIContext(
            ai_workload_type="mlops",
            deployment_stage="scale",
            gpu_need="high",
            has_operational_signal=True,
        ),
        evidence_signals=[
            _evidence(
                "Kubernetes orchestration with PyTorch and ONNX model serving using batching. "
                "Enterprise support with governance and platform infrastructure for production."
            ),
        ],
        technologies=FULL_CATALOG,
    )

    assert _precision_at_k(results, ["nvidia-ai-enterprise", "triton-inference-server", "nvidia-nemo"], k=3) >= 0.66, (
        f"top-3 obtido: {list(_top_k_slugs(results))}"
    )
    # Healthcare e speech não fazem sentido para MLOps enterprise
    assert _false_positive_slugs(results, ["riva", "monai", "nvidia-clara"]) == set()
    # Enterprise AI-native em escala deve ter pelo menos 1 recomendação forte
    assert any(r.nivel == NIVEL_FORTE for r in results), "Nenhuma recomendação forte para MLOps enterprise em escala"


def test_archetype_enterprise_mlops_nemo_appears_with_training_signals() -> None:
    """NeMo deve aparecer quando há sinais de training/fine-tuning."""

    results = match_technologies(
        sector="mlops",
        description="Enterprise platform for training, fine-tuning and deploying LLM agents at scale.",
        ai_maturity_level="ai_native",
        ai_context=StartupAIContext(ai_workload_type="mlops", deployment_stage="scale", gpu_need="high"),
        evidence_signals=[_evidence("llm fine tuning training agent generative ai governance platform")],
        technologies=FULL_CATALOG,
    )

    nemo_rank = _slug_rank(results, "nvidia-nemo")
    assert nemo_rank is not None, "NeMo deveria aparecer quando há sinais de training/fine-tuning de LLMs"
    assert nemo_rank <= 5, f"NeMo deveria estar no top-5, mas está na posição {nemo_rank}"


# ---------------------------------------------------------------------------
# Eval set — 4 arquétipos reais validados manualmente (tarefa_radar ground truth)
#
# Estes 4 casos foram analisados à mão com dados reais (GitHub, notícias,
# perfis públicos). São a régua principal para detectar regressão no motor:
# se um deles falhar, provavelmente houve mudança de threshold ou catálogo
# que quebrou um perfil real do portfólio NVIDIA Brasil.
# ---------------------------------------------------------------------------


def test_eval_neuralmind_ai_native_nlp_gets_nim_triton_tensorrt_llm() -> None:
    """NeuralMind: startup de pesquisa + deploy de LLMs em PT (BERTimbau, T5, RAG).

    Parceira NVIDIA. Espera NIM/Triton/TensorRT-LLM no top-3; NeMo em alguma posição
    (há sinal de training/fine-tuning). Sem healthcare, speech, robotics.
    """
    results = match_technologies(
        sector="natural language processing",
        description=(
            "AI research lab building and deploying large language models for Portuguese. "
            "Trains transformer models (BERT, T5) and serves them as API microservices "
            "for production NLP inference. Develops RAG pipelines and LLM fine-tuning "
            "with optimized token throughput."
        ),
        ai_maturity_level="ai_native",
        ai_context=StartupAIContext(
            ai_workload_type="nlp",
            deployment_stage="production",
            gpu_need="high",
            has_operational_signal=True,
        ),
        evidence_signals=[
            _evidence(
                "language model llm inference api deployment model serving "
                "pytorch onnx throughput token fine tuning training generative ai "
                "microservice batching kubernetes"
            ),
        ],
        technologies=FULL_CATALOG,
    )

    slugs = {r.technology.slug for r in results}

    # Os 3 principais para deploy de LLMs devem aparecer
    assert "nvidia-nim" in slugs, "NIM ausente — startup serve LLMs como API microservices"
    assert "triton-inference-server" in slugs, "Triton ausente — startup usa model serving com PyTorch/ONNX"
    assert "tensorrt-llm" in slugs, "TensorRT-LLM ausente — startup otimiza throughput/token de LLMs"
    # NeMo porque há sinal de training/fine-tuning de LLMs
    assert "nvidia-nemo" in slugs, "NeMo ausente — startup treina e faz fine-tuning de LLMs"

    # Precision@3: pelo menos 2 dos 3 esperados no topo
    assert _precision_at_k(results, ["nvidia-nim", "triton-inference-server", "tensorrt-llm"]) >= 0.66, (
        f"top-3 obtido: {[r.technology.slug for r in results[:3]]}"
    )

    # Sem falsos positivos óbvios
    assert _false_positive_slugs(results, ["monai", "nvidia-clara", "riva", "nvidia-isaac", "nvidia-omniverse"]) == set()


def test_eval_dynadok_ai_native_idp_gets_nim_triton_tensorrt() -> None:
    """Dynadok: IDP (Intelligent Document Processing) com visão+NLP, clientes enterprise.

    Extrai dados estruturados de documentos via visão computacional e NLP.
    Clientes Afya e Cenibra. Espera NIM/Triton/TensorRT.
    """
    results = match_technologies(
        sector="intelligent document processing",
        description=(
            "AI platform for intelligent document processing combining computer vision "
            "and NLP to extract structured data from invoices, contracts and medical records. "
            "Deploys optimized inference models for enterprise clients with low-latency "
            "document analysis. Uses PyTorch and ONNX for model optimization."
        ),
        ai_maturity_level="ai_native",
        ai_context=StartupAIContext(
            ai_workload_type="vision",
            deployment_stage="production",
            gpu_need="high",
            has_operational_signal=True,
        ),
        evidence_signals=[
            _evidence(
                "inference optimization pytorch onnx latency model serving batching "
                "deployment api document processing extraction"
            ),
        ],
        technologies=FULL_CATALOG,
    )

    slugs = {r.technology.slug for r in results}

    assert "triton-inference-server" in slugs, "Triton ausente — deploy com PyTorch/ONNX e batching"
    assert "tensorrt" in slugs, "TensorRT ausente — otimização de latência com PyTorch/ONNX"
    # NIM porque serve modelos como API com deployment
    assert "nvidia-nim" in slugs, "NIM ausente — startup serve modelos como API microservices"

    # TensorRT ou Triton no top-3
    assert _precision_at_k(results, ["tensorrt", "triton-inference-server", "nvidia-nim"], k=3) >= 0.66, (
        f"top-3 obtido: {[r.technology.slug for r in results[:3]]}"
    )

    # Sem healthcare (sem sinal médico direto) e sem robotics
    assert _false_positive_slugs(results, ["monai", "nvidia-clara", "riva", "nvidia-isaac", "nvidia-omniverse"]) == set()


def test_eval_noleak_ai_native_vision_rl_gets_tensorrt_triton() -> None:
    """Noleak: visão computacional + RL para análise de vídeo em tempo real, GPU alta.

    68 anos de vídeo processados. Edge inference com GPU. Espera TensorRT e Triton.
    Sem healthcare nem speech.
    """
    results = match_technologies(
        sector="computer vision",
        description=(
            "Real-time video intelligence platform using deep learning and reinforcement "
            "learning for security and behavioral monitoring. Processes video streams at "
            "the edge with GPU-accelerated inference. Uses PyTorch models exported to "
            "ONNX for latency-optimized edge deployment."
        ),
        ai_maturity_level="ai_native",
        ai_context=StartupAIContext(
            ai_workload_type="vision",
            deployment_stage="production",
            gpu_need="high",
            has_operational_signal=True,
        ),
        evidence_signals=[
            _evidence(
                "computer vision video real-time inference pytorch onnx optimization "
                "latency edge batching model serving deployment"
            ),
        ],
        technologies=FULL_CATALOG,
    )

    slugs = {r.technology.slug for r in results}

    assert "tensorrt" in slugs, "TensorRT ausente — startup otimiza PyTorch/ONNX para edge com latência baixa"
    assert "triton-inference-server" in slugs, "Triton ausente — model serving com PyTorch/ONNX e batching"

    # Ambos no top-3
    assert _precision_at_k(results, ["tensorrt", "triton-inference-server"], k=3) >= 0.66, (
        f"top-3 obtido: {[r.technology.slug for r in results[:3]]}"
    )

    # Healthcare, speech e robotics industrial claramente fora do perfil de visão em segurança
    assert _false_positive_slugs(results, ["monai", "nvidia-clara", "riva", "nvidia-isaac", "nvidia-omniverse"]) == set()


def test_eval_driva_ai_enabled_analytics_gets_rapids_cudf_cuml() -> None:
    """Driva: analytics financeiro + agentes de IA (AI-enabled, tabular).

    Motor de recomendação para financiamento de veículos. Espera RAPIDS/cuDF/cuML.
    NÃO deve receber infra pesada de treino de LLM (NeMo, TensorRT-LLM).
    """
    results = match_technologies(
        sector="fintech",
        description=(
            "AI-enabled fintech platform for vehicle credit analysis using machine learning "
            "on large tabular datasets. Accelerates data science pipelines with GPU-powered "
            "pandas and dataframe operations. Builds recommendation and classification models "
            "with scikit-learn compatible GPU APIs."
        ),
        ai_maturity_level="ai_enabled",
        ai_context=StartupAIContext(
            ai_workload_type="analytics",
            deployment_stage="production",
            gpu_need="high",
            has_operational_signal=True,
        ),
        evidence_signals=[
            _evidence(
                "analytics dataframe pandas gpu data science machine learning "
                "scikit-learn clustering classification rapids etl recommendation"
            ),
        ],
        technologies=FULL_CATALOG,
    )

    slugs = {r.technology.slug for r in results}

    assert "rapids" in slugs, "RAPIDS ausente — pipeline tabular GPU para data science"
    assert "cudf" in slugs, "cuDF ausente — operações de dataframe/pandas em GPU"
    assert "cuml" in slugs, "cuML ausente — ML clássico (scikit-learn) em GPU"

    # Os 3 esperados devem dominar o top-3
    assert _precision_at_k(results, ["rapids", "cudf", "cuml"]) >= 0.66, (
        f"top-3 obtido: {[r.technology.slug for r in results[:3]]}"
    )

    # Infra pesada de treino de LLM não faz sentido para analytics tabular
    heavy_training = _false_positive_slugs(results, ["nvidia-nemo", "tensorrt-llm"])
    assert heavy_training == set(), (
        f"Startup de analytics tabular não deveria receber infra de LLM: {heavy_training}"
    )

    # Healthcare e robotics claramente fora do perfil
    assert _false_positive_slugs(results, ["monai", "nvidia-clara", "nvidia-isaac", "nvidia-omniverse"]) == set()


# ---------------------------------------------------------------------------
# Métricas consolidadas (relatório, não falha)
# ---------------------------------------------------------------------------


def test_golden_set_overall_metrics(capsys: pytest.CaptureFixture[str]) -> None:
    """Computa e exibe métricas agregadas dos 6 arquétipos. Não falha — é relatório."""

    archetypes = [
        {
            "name": "LLM Inference (AI-native, production)",
            "kwargs": dict(
                sector="generative ai",
                description="Platform for LLM inference as microservices with standardized API deployment and token throughput optimization.",
                ai_maturity_level="ai_native",
                ai_context=StartupAIContext(ai_workload_type="nlp", deployment_stage="production", gpu_need="high", has_operational_signal=True),
                evidence_signals=[_evidence("PyTorch ONNX batching model serving kubernetes inference throughput token quantization")],
            ),
            "expected": ["nvidia-nim", "triton-inference-server", "tensorrt-llm"],
        },
        {
            "name": "API-only SaaS (AI-enabled, mvp)",
            "kwargs": dict(
                sector="saas",
                description="B2B SaaS with AI assistant powered by third-party generative AI API. No own model training.",
                ai_maturity_level="ai_enabled",
                ai_context=StartupAIContext(ai_workload_type="nlp", deployment_stage="mvp", gpu_need="low"),
                evidence_signals=[],
            ),
            "expected": ["nvidia-nim"],
        },
        {
            "name": "SaaS sem IA (non_ai)",
            "kwargs": dict(
                sector="hr tech",
                description="Human resources workflow automation and reporting platform. No AI models.",
                ai_maturity_level="non_ai",
                ai_context=StartupAIContext(ai_workload_type="unknown", deployment_stage="production", gpu_need="low"),
                evidence_signals=[],
            ),
            "expected": [],
        },
        {
            "name": "Computer Vision (AI-native, pilot)",
            "kwargs": dict(
                sector="computer vision",
                description="Industrial visual inspection AI with deep learning for image segmentation and inference optimization.",
                ai_maturity_level="ai_native",
                ai_context=StartupAIContext(ai_workload_type="vision", deployment_stage="pilot", gpu_need="high"),
                evidence_signals=[_evidence("pytorch onnx latency optimization inference batching model serving")],
            ),
            "expected": ["tensorrt", "triton-inference-server"],
        },
        {
            "name": "Tabular Analytics (AI-enabled, production)",
            "kwargs": dict(
                sector="data analytics",
                description="GPU-accelerated data science platform with pandas and dataframe analytics workloads.",
                ai_maturity_level="ai_enabled",
                ai_context=StartupAIContext(ai_workload_type="analytics", deployment_stage="production", gpu_need="high", has_operational_signal=True),
                evidence_signals=[_evidence("pandas dataframe gpu rapids etl machine learning scikit-learn clustering classification data science")],
            ),
            "expected": ["rapids", "cudf", "cuml"],
        },
        {
            "name": "Enterprise MLOps (AI-native, scale)",
            "kwargs": dict(
                sector="mlops",
                description="Enterprise AI platform for model training, deployment, governance and infrastructure support at scale.",
                ai_maturity_level="ai_native",
                ai_context=StartupAIContext(ai_workload_type="mlops", deployment_stage="scale", gpu_need="high", has_operational_signal=True),
                evidence_signals=[_evidence("kubernetes pytorch onnx batching model serving enterprise governance platform infrastructure deployment")],
            ),
            "expected": ["nvidia-ai-enterprise", "triton-inference-server", "nvidia-nemo"],
        },
    ]

    total_p3 = 0.0
    strong_counts = []
    lines = ["\n=== Golden Set — Métricas de Recomendação ==="]

    for archetype in archetypes:
        results = match_technologies(
            technologies=FULL_CATALOG,
            **archetype["kwargs"],
        )
        p3 = _precision_at_k(results, archetype["expected"])
        total_p3 += p3
        strong = sum(1 for r in results if r.nivel == NIVEL_FORTE)
        strong_counts.append(strong)

        top3 = [r.technology.slug for r in results[:3]]
        lines.append(
            f"\n{archetype['name']}\n"
            f"  top-3    : {top3}\n"
            f"  esperado : {archetype['expected']}\n"
            f"  p@3      : {p3:.2f}   fortes: {strong}   total recomendações: {len(results)}"
        )

    avg_p3 = total_p3 / len(archetypes)
    lines.append(f"\nMédia p@3 = {avg_p3:.2f}   (mínimo esperado: 0.50)")
    lines.append("=" * 50)
    print("\n".join(lines))

    # Piso mínimo: média de precision@3 >= 0.50 (3 em 6 arquétipos acertam pelo menos 2/3 esperados)
    assert avg_p3 >= 0.50, f"Média p@3 abaixo do mínimo: {avg_p3:.2f}"
