from app.diagnostics.schemas import GapDiagnosis
from app.llm.client import LlmUnavailableError, generate_openai_json, is_llm_enabled
from app.models.enums import ImplementationComplexity, RecommendationPriority
from app.rag.catalog import NVIDIA_TECHNOLOGY_CATALOG, NvidiaTechnologyCatalogItem
from app.recommendations.schemas import RecommendationReport, TechnologyRecommendation
from app.settings import get_settings

GAP_TECHNOLOGY_MAP = {
    "external_api_dependency": ("NVIDIA NIM", "NVIDIA Triton Inference Server"),
    "inference_latency_or_cost": ("TensorRT-LLM", "NVIDIA Triton Inference Server", "NVIDIA NIM"),
    "model_serving_maturity": ("NVIDIA Triton Inference Server", "NVIDIA NIM"),
    "agent_governance": ("NeMo Guardrails", "NVIDIA NeMo"),
    "data_pipeline_scale": ("NVIDIA RAPIDS", "cuDF", "cuML"),
    "voice_ai_maturity": ("NVIDIA Riva", "NVIDIA NIM"),
    "healthcare_production_readiness": (
        "NVIDIA Clara",
        "NeMo Guardrails",
        "NVIDIA AI Enterprise",
    ),
    "robotics_or_simulation": ("NVIDIA Isaac", "NVIDIA Omniverse"),
    "cybersecurity_ai": ("NVIDIA Morpheus",),
}


COMPLEXITY_BY_TECHNOLOGY = {
    "NVIDIA Inception": ImplementationComplexity.LOW,
    "NVIDIA NIM": ImplementationComplexity.MEDIUM,
    "NVIDIA NeMo": ImplementationComplexity.HIGH,
    "NeMo Guardrails": ImplementationComplexity.MEDIUM,
    "NVIDIA Triton Inference Server": ImplementationComplexity.HIGH,
    "TensorRT-LLM": ImplementationComplexity.HIGH,
    "NVIDIA RAPIDS": ImplementationComplexity.MEDIUM,
    "cuDF": ImplementationComplexity.MEDIUM,
    "cuML": ImplementationComplexity.MEDIUM,
    "CUDA": ImplementationComplexity.HIGH,
    "NVIDIA Riva": ImplementationComplexity.MEDIUM,
    "NVIDIA Omniverse": ImplementationComplexity.HIGH,
    "NVIDIA Isaac": ImplementationComplexity.HIGH,
    "NVIDIA Clara": ImplementationComplexity.MEDIUM,
    "NVIDIA Morpheus": ImplementationComplexity.MEDIUM,
    "NVIDIA AI Enterprise": ImplementationComplexity.MEDIUM,
}


def generate_recommendations(gaps: tuple[GapDiagnosis, ...]) -> RecommendationReport:
    settings = get_settings()
    if is_llm_enabled(settings):
        try:
            llm_report = _generate_recommendations_with_llm(gaps)
            if llm_report.recommendations:
                return llm_report
        except (LlmUnavailableError, KeyError, TypeError, ValueError):
            pass

    return _generate_recommendations_with_heuristics(gaps)


def _generate_recommendations_with_heuristics(
    gaps: tuple[GapDiagnosis, ...],
) -> RecommendationReport:
    recommendations: list[TechnologyRecommendation] = []

    for gap in gaps:
        for technology_name in GAP_TECHNOLOGY_MAP.get(gap.gap_type, ()):
            catalog_item = _find_catalog_item(technology_name)
            if not catalog_item:
                continue

            recommendations.append(_build_recommendation(gap, catalog_item))

    deduplicated_recommendations = _deduplicate_recommendations(recommendations)
    return RecommendationReport(
        recommendations=tuple(deduplicated_recommendations),
        summary=_build_summary(deduplicated_recommendations),
    )


def _generate_recommendations_with_llm(
    gaps: tuple[GapDiagnosis, ...],
) -> RecommendationReport:
    settings = get_settings()
    catalog_names = [item.name for item in NVIDIA_TECHNOLOGY_CATALOG]
    response = generate_openai_json(
        settings=settings,
        system_prompt=(
            "Você é um especialista NVIDIA. Recomende apenas tecnologias presentes "
            "no catálogo fornecido. Responda somente JSON válido."
        ),
        user_prompt=(
            "Retorne JSON no formato: "
            '{"summary": string, "recommendations": ['
            '{"gap_type": string, "technology_name": string, "priority": "high|medium|low", '
            '"complexity": "low|medium|high", "technical_rationale": string, '
            '"business_rationale": string, "next_action": string}'
            "]}. "
            f"Catálogo permitido: {catalog_names}. "
            f"Gaps detectados: {[gap.__dict__ for gap in gaps]}"
        ),
    )
    recommendations = [
        recommendation
        for recommendation in (
            _recommendation_from_llm(item)
            for item in _list_value(response.get("recommendations"))
            if isinstance(item, dict)
        )
        if recommendation is not None
    ]
    return RecommendationReport(
        recommendations=tuple(_deduplicate_recommendations(recommendations)),
        summary=_string_value(response.get("summary")) or _build_summary(recommendations),
    )


def _recommendation_from_llm(
    raw_recommendation: dict[str, object],
) -> TechnologyRecommendation | None:
    technology_name = _string_value(raw_recommendation.get("technology_name"))
    if not technology_name:
        return None
    catalog_item = _find_catalog_item(technology_name)
    if not catalog_item:
        return None

    return TechnologyRecommendation(
        gap_type=_string_value(raw_recommendation.get("gap_type")) or "general_ai_stack_gap",
        technology_name=catalog_item.name,
        source_url=catalog_item.source_url,
        priority=_priority_value(raw_recommendation.get("priority")),
        complexity=_complexity_value(raw_recommendation.get("complexity")),
        technical_rationale=(
            _string_value(raw_recommendation.get("technical_rationale"))
            or f"{catalog_item.name} pode endereçar o gap identificado."
        ),
        business_rationale=(
            _string_value(raw_recommendation.get("business_rationale"))
            or "A recomendação cria um caminho técnico concreto para qualificação NVIDIA."
        ),
        next_action=(
            _string_value(raw_recommendation.get("next_action"))
            or f"Validar fit de {catalog_item.name} em conversa técnica."
        ),
    )


def _priority_value(value: object) -> str:
    priority = _string_value(value)
    if priority in {
        RecommendationPriority.HIGH,
        RecommendationPriority.MEDIUM,
        RecommendationPriority.LOW,
    }:
        return priority
    return RecommendationPriority.MEDIUM


def _complexity_value(value: object) -> str:
    complexity = _string_value(value)
    if complexity in {
        ImplementationComplexity.LOW,
        ImplementationComplexity.MEDIUM,
        ImplementationComplexity.HIGH,
    }:
        return complexity
    return ImplementationComplexity.MEDIUM


def _string_value(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    stripped = value.strip()
    return stripped or None


def _list_value(value: object) -> list[object]:
    return value if isinstance(value, list) else []


def _build_recommendation(
    gap: GapDiagnosis,
    catalog_item: NvidiaTechnologyCatalogItem,
) -> TechnologyRecommendation:
    return TechnologyRecommendation(
        gap_type=gap.gap_type,
        technology_name=catalog_item.name,
        source_url=catalog_item.source_url,
        priority=gap.priority,
        complexity=COMPLEXITY_BY_TECHNOLOGY.get(
            catalog_item.name,
            ImplementationComplexity.MEDIUM,
        ),
        technical_rationale=_technical_rationale(gap, catalog_item),
        business_rationale=_business_rationale(gap, catalog_item),
        next_action=_next_action(gap, catalog_item),
    )


def _technical_rationale(
    gap: GapDiagnosis,
    catalog_item: NvidiaTechnologyCatalogItem,
) -> str:
    return (
        f"{catalog_item.name} ajuda a endereçar {_gap_label(gap.gap_type)} por atuar em "
        f"{_category_label(catalog_item.category)}. Racional do gap: {gap.rationale}"
    )


def _business_rationale(
    gap: GapDiagnosis,
    catalog_item: NvidiaTechnologyCatalogItem,
) -> str:
    return (
        f"Usar {catalog_item.name} ajuda a NVIDIA a posicionar um caminho técnico concreto "
        f"para uma necessidade de prioridade {_priority_label(gap.priority)} da startup."
    )


def _next_action(
    gap: GapDiagnosis,
    catalog_item: NvidiaTechnologyCatalogItem,
) -> str:
    if gap.priority == RecommendationPriority.HIGH:
        return (
            f"Oferecer um workshop técnico focado em {catalog_item.name} "
            f"e {_gap_label(gap.gap_type)}."
        )

    return (
        f"Compartilhar materiais de {catalog_item.name} e validar fit no próximo contato "
        "com a startup."
    )


def _find_catalog_item(technology_name: str) -> NvidiaTechnologyCatalogItem | None:
    for catalog_item in NVIDIA_TECHNOLOGY_CATALOG:
        if catalog_item.name == technology_name:
            return catalog_item

    return None


def _deduplicate_recommendations(
    recommendations: list[TechnologyRecommendation],
) -> list[TechnologyRecommendation]:
    best_by_technology: dict[str, TechnologyRecommendation] = {}

    for recommendation in recommendations:
        existing = best_by_technology.get(recommendation.technology_name)
        is_higher_priority = _priority_rank(recommendation.priority) > _priority_rank(
            existing.priority
        ) if existing else True
        if is_higher_priority:
            best_by_technology[recommendation.technology_name] = recommendation

    return sorted(
        best_by_technology.values(),
        key=lambda recommendation: (
            _priority_rank(recommendation.priority),
            recommendation.technology_name,
        ),
        reverse=True,
    )


def _priority_rank(priority: str) -> int:
    return {
        RecommendationPriority.HIGH: 3,
        RecommendationPriority.MEDIUM: 2,
        RecommendationPriority.LOW: 1,
    }.get(priority, 0)


def _build_summary(recommendations: list[TechnologyRecommendation]) -> str:
    if not recommendations:
        return "Nenhuma recomendação de tecnologia NVIDIA foi gerada a partir dos gaps detectados."

    high_priority_count = sum(
        1
        for recommendation in recommendations
        if recommendation.priority == RecommendationPriority.HIGH
    )
    return (
        f"Foram geradas {len(recommendations)} recomendações NVIDIA, incluindo "
        f"{high_priority_count} recomendação(ões) de alta prioridade."
    )


def _gap_label(gap_type: str) -> str:
    return {
        "external_api_dependency": "dependência de API externa",
        "inference_latency_or_cost": "custo ou latência de inferência",
        "model_serving_maturity": "maturidade de serving",
        "agent_governance": "governança de agentes",
        "data_pipeline_scale": "escala de dados",
        "voice_ai_maturity": "maturidade em voz",
        "healthcare_production_readiness": "prontidão de saúde em produção",
        "robotics_or_simulation": "robótica ou simulação",
        "cybersecurity_ai": "IA para cibersegurança",
    }.get(gap_type, gap_type)


def _priority_label(priority: str) -> str:
    return {
        RecommendationPriority.HIGH: "alta",
        RecommendationPriority.MEDIUM: "média",
        RecommendationPriority.LOW: "baixa",
    }.get(priority, priority)


def _category_label(category: str) -> str:
    return {
        "startup_program": "programas para startups",
        "model_serving": "serving de modelos",
        "generative_ai": "IA generativa",
        "ai_governance": "governança de IA",
        "inference_optimization": "otimização de inferência",
        "data_acceleration": "aceleração de dados",
        "machine_learning": "machine learning",
        "gpu_programming": "programação em GPU",
        "speech_ai": "IA de voz",
        "simulation": "simulação",
        "robotics": "robótica",
        "healthcare": "saúde",
        "cybersecurity": "cibersegurança",
        "enterprise_ai": "IA empresarial",
    }.get(category, category.replace("_", " "))
