from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path
from typing import Any


FRAMEWORKS = {
    "pytorch": "PyTorch",
    "tensorflow": "TensorFlow",
    "jax": "JAX",
    "scikit-learn": "scikit-learn",
    "sklearn": "scikit-learn",
}

MODELS_APIS = {
    "openai api": "OpenAI API",
    "api da openai": "OpenAI API",
    "chatgpt": "ChatGPT",
    "gpt": "GPT",
    "gemini": "Gemini",
    "google ai": "Google AI",
    "claude": "Claude",
    "llama": "Llama",
    "bedrock": "Amazon Bedrock",
    "hugging face": "Hugging Face",
}

INFRASTRUCTURE = {
    "gpu nvidia": "GPU NVIDIA",
    "nvidia gpu": "GPU NVIDIA",
    "gpu": "GPU",
    "cuda": "CUDA",
    "nvidia": "NVIDIA",
    "triton": "NVIDIA Triton",
    "tensorrt": "TensorRT",
    "aws": "AWS",
    "amazon web services": "AWS",
    "azure": "Azure",
    "google cloud": "Google Cloud",
    "gcp": "Google Cloud",
}

MLOPS_TOOLS = {
    "mlflow": "MLflow",
    "kubeflow": "Kubeflow",
    "weights & biases": "Weights & Biases",
    "wandb": "Weights & Biases",
    "sagemaker": "SageMaker",
}

INTERNAL_DEVELOPMENT_SIGNALS = (
    "modelo proprietario",
    "modelos proprietarios",
    "modelo proprio",
    "modelos proprios",
    "treinamento de modelo",
    "treinamos modelos",
    "treina modelos",
    "fine-tuning",
    "fine tuning",
    "pytorch",
    "tensorflow",
    "jax",
    "ml engineer",
    "machine learning engineer",
    "data scientist",
    "equipe de ml",
    "equipe de machine learning",
    "cuda",
    "tensorrt",
    "mlops",
)

API_SIGNALS = tuple(MODELS_APIS)

GENERIC_AI_TERMS = {
    "assistente virtual",
    "automacao inteligente",
    "chatbot",
    "gpt",
    "inteligencia artificial",
    "llm",
}

OPTIMIZATION_SIGNALS = (
    "baixa latencia",
    "latencia",
    "custo de inferencia",
    "otimizacao de modelo",
    "otimizacao de inferencia",
    "performance de inferencia",
    "throughput",
    "triton",
    "tensorrt",
    "cuda",
    "gpu",
)

EXPERIMENTAL_SIGNALS = (
    "explorando ia",
    "teste inicial",
    "prova de conceito",
    "proof of concept",
    "piloto de ia",
)

PRODUCTION_SIGNALS = (
    "em producao",
    "produto",
    "plataforma",
    "clientes",
    "usuarios",
    "integra",
    "utiliza",
    "usa ",
)


def classificar_maturidade_ia(validacao: dict[str, Any]) -> dict[str, Any]:
    startup = _clean(validacao.get("startup"))
    evidences = _usable_evidences(validacao)
    ai_evidences = [item for item in evidences if item.get("contem_evidencia_ia")]
    evidence_text = " ".join(_evidence_text(item) for item in ai_evidences)
    normalized_text = _normalize(evidence_text)

    technologies = _extract_technologies(normalized_text)
    trusted_internal_signals = _trusted_internal_signals(ai_evidences)
    api_signals = _find_signals(normalized_text, API_SIGNALS)
    optimization_signals = _find_signals(normalized_text, OPTIMIZATION_SIGNALS)
    experimental_signals = _find_signals(normalized_text, EXPERIMENTAL_SIGNALS)
    production_signals = _find_signals(normalized_text, PRODUCTION_SIGNALS)

    classification = _classify(ai_evidences, trusted_internal_signals, api_signals)
    maturity = _maturity_level(
        classification,
        internal_signals=trusted_internal_signals,
        optimization_signals=optimization_signals,
        experimental_signals=experimental_signals,
        production_signals=production_signals,
    )
    confidence = _classification_confidence(
        ai_evidences,
        classification,
        internal_signals=trusted_internal_signals,
        api_signals=api_signals,
        validation=validacao,
    )

    return {
        "startup": startup,
        "classificacao": classification,
        "nivel_maturidade": maturity,
        "confianca_classificacao": confidence,
        "justificativa": _build_justification(
            classification,
            ai_evidences,
            trusted_internal_signals,
            api_signals,
        ),
        "tecnologias_utilizadas": technologies,
        "necessidades_limitacoes": _infer_needs(
            classification,
            normalized_text,
            trusted_internal_signals,
            optimization_signals,
        ),
        "sugestao_inicial_stack_nvidia": _preliminary_nvidia_suggestion(
            classification,
            technologies,
            maturity,
        ),
        "evidencias_suporte": _supporting_evidence(ai_evidences),
    }


def salvar_classificacao_maturidade(
    resultado: dict[str, Any],
    output_dir: Path | None = None,
) -> Path:
    output_dir = output_dir or Path("data/curated/_maturidade_ia")
    output_dir.mkdir(parents=True, exist_ok=True)
    slug = re.sub(r"[^a-z0-9]+", "-", _normalize(resultado.get("startup"))).strip("-") or "startup"
    path = output_dir / f"maturidade_ia_{slug}.json"
    path.write_text(json.dumps(resultado, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def _usable_evidences(validation: dict[str, Any]) -> list[dict[str, Any]]:
    evidences = validation.get("evidencias_validadas", []) + validation.get("evidencias_medias", [])
    return [item for item in evidences if float(item.get("score_confianca") or 0) >= 0.4]


def _classify(
    ai_evidences: list[dict[str, Any]],
    internal_signals: list[str],
    api_signals: list[str],
) -> str:
    if not ai_evidences:
        return "Non-AI"
    if internal_signals:
        return "AI-native"

    has_non_api_ai_signal = any(
        technology not in API_SIGNALS and technology not in GENERIC_AI_TERMS
        for item in ai_evidences
        for technology in item.get("tecnologias_detectadas", [])
    )
    if api_signals and not has_non_api_ai_signal:
        return "API-consumer"
    return "AI-enabled"


def _trusted_internal_signals(evidences: list[dict[str, Any]]) -> list[str]:
    """Accept native-development claims only from strong, attributable evidence."""
    trusted: list[str] = []
    for evidence in evidences:
        text = _normalize(_evidence_text(evidence))
        signals = _find_signals(text, INTERNAL_DEVELOPMENT_SIGNALS)
        attributable = (
            evidence.get("tipo_fonte") == "oficial"
            or bool(evidence.get("declaracao_propria"))
            or bool(evidence.get("corroborada"))
        )
        if float(evidence.get("score_confianca") or 0) >= 0.7 and attributable:
            trusted.extend(signals)
    return list(dict.fromkeys(trusted))


def _maturity_level(
    classification: str,
    internal_signals: list[str],
    optimization_signals: list[str],
    experimental_signals: list[str],
    production_signals: list[str],
) -> int:
    if classification == "Non-AI":
        return 0
    if experimental_signals and not production_signals:
        return 1
    if classification == "API-consumer":
        return 2
    if classification == "AI-native":
        return 5 if optimization_signals else 4
    return 3 if production_signals else 2


def _classification_confidence(
    evidences: list[dict[str, Any]],
    classification: str,
    internal_signals: list[str],
    api_signals: list[str],
    validation: dict[str, Any],
) -> float:
    if not evidences:
        quality = float(validation.get("resumo_consolidado", {}).get("nota_geral_qualidade_evidencias") or 0)
        return round(min(0.7, 0.4 + quality * 0.3), 2)

    average = sum(float(item.get("score_confianca") or 0) for item in evidences) / len(evidences)
    corroborated = any(item.get("corroborada") for item in evidences)
    distinctive_signal = bool(internal_signals or api_signals)
    adjusted = average + (0.08 if corroborated else 0.0)
    if classification == "AI-enabled" and not distinctive_signal:
        adjusted -= 0.08
    return round(max(0.0, min(1.0, adjusted)), 2)


def _extract_technologies(text: str) -> dict[str, list[str]]:
    return {
        "frameworks": _canonical_matches(text, FRAMEWORKS),
        "modelos_apis": _canonical_matches(text, MODELS_APIS),
        "infraestrutura": _canonical_matches(text, INFRASTRUCTURE),
        "ferramentas_mlops": _canonical_matches(text, MLOPS_TOOLS),
    }


def _canonical_matches(text: str, mapping: dict[str, str]) -> list[str]:
    found = []
    for signal, canonical in mapping.items():
        if _contains_signal(text, signal) and canonical not in found:
            found.append(canonical)
    return found


def _find_signals(text: str, signals: tuple[str, ...]) -> list[str]:
    return [signal for signal in signals if _contains_signal(text, signal)]


def _contains_signal(text: str, signal: str) -> bool:
    return bool(re.search(rf"(?<!\w){re.escape(signal)}(?!\w)", text))


def _build_justification(
    classification: str,
    evidences: list[dict[str, Any]],
    internal_signals: list[str],
    api_signals: list[str],
) -> str:
    if classification == "Non-AI":
        return "Não foram encontradas evidências de IA com score de confiança igual ou superior a 0,4. A classificação permanece conservadora até que surjam fontes qualificadas."

    source_count = len({item.get("dominio") or item.get("url") for item in evidences})
    if classification == "AI-native":
        signal = internal_signals[0]
        return f"Há evidência qualificada de desenvolvimento interno, incluindo '{signal}', em {source_count} fonte(s). Isso indica que a construção ou operação de modelos faz parte da capacidade técnica da startup."
    if classification == "API-consumer":
        signal = api_signals[0]
        return f"As evidências qualificadas apontam consumo de tecnologia pronta, incluindo '{signal}', sem sinal de desenvolvimento ou adaptação interna. Por cautela, a startup foi classificada como consumidora de APIs."
    return f"Foram encontradas evidências qualificadas de uso relevante de IA em {source_count} fonte(s), mas sem comprovação suficiente de desenvolvimento próprio. A classificação conservadora é AI-enabled."


def _infer_needs(
    classification: str,
    text: str,
    internal_signals: list[str],
    optimization_signals: list[str],
) -> list[str]:
    if classification == "Non-AI":
        return []

    needs = []
    if classification == "API-consumer":
        needs.extend(
            [
                "Possível custo elevado de inferência por dependência de APIs externas",
                "Possível risco de vendor lock-in em fornecedores de modelos",
            ]
        )
    if any(signal in text for signal in ("tempo real", "baixa latencia", "chatbot", "assistente virtual")):
        needs.append("Possível necessidade de reduzir latência de inferência")
    if any(signal in text for signal in ("escala", "milhoes", "crescimento", "picos de uso")):
        needs.append("Possível necessidade de escalar treinamento ou inferência")
    if any(signal in text for signal in ("lgpd", "dados sensiveis", "dados de saude", "dados financeiros")):
        needs.append("Necessidade de governança e privacidade sobre dados utilizados pela IA")
    if internal_signals and not optimization_signals:
        needs.append("Evidências não detalham otimização de performance e custo dos modelos")
    if not any(signal in text for signal in ("data scientist", "ml engineer", "equipe de ml")):
        needs.append("Evidências não detalham uma equipe especializada de ML")
    return needs


def _preliminary_nvidia_suggestion(
    classification: str,
    technologies: dict[str, list[str]],
    maturity: int,
) -> str:
    if classification == "Non-AI":
        return ""
    if classification == "API-consumer":
        return "Avaliar NVIDIA NIM para reduzir dependência de APIs externas; recomendação sujeita à validação pelo RAG."
    if maturity >= 4:
        return "Avaliar Triton Inference Server e TensorRT para servir e otimizar modelos; recomendação sujeita à validação pelo RAG."
    if technologies["modelos_apis"]:
        return "Avaliar NVIDIA NIM e NeMo para integração e adaptação de modelos; recomendação sujeita à validação pelo RAG."
    return "Avaliar NVIDIA NIM para disponibilização de capacidades de IA; recomendação sujeita à validação pelo RAG."


def _supporting_evidence(evidences: list[dict[str, Any]], limit: int = 5) -> list[str]:
    ordered = sorted(evidences, key=lambda item: float(item.get("score_confianca") or 0), reverse=True)
    return [
        f"{item.get('url')}: {_clean(item.get('trecho_evidencia'))}"
        for item in ordered[:limit]
        if item.get("url") and item.get("trecho_evidencia")
    ]


def _evidence_text(evidence: dict[str, Any]) -> str:
    technologies = " ".join(str(item) for item in evidence.get("tecnologias_detectadas", []))
    return f"{_clean(evidence.get('trecho_evidencia'))} {technologies}".strip()


def _normalize(value: Any) -> str:
    clean = _clean(value).lower()
    return "".join(char for char in unicodedata.normalize("NFKD", clean) if not unicodedata.combining(char))


def _clean(value: Any) -> str:
    if value is None:
        return ""
    return " ".join(str(value).split()).strip()
