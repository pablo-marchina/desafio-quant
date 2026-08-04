import json
import os
from typing import Any

import httpx
from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, Field

from app.rag.schemas import (
    NvidiaRecommendation,
    RecommendationCitation,
    RecommendationResponse,
    ResearchWithNvidiaContextResponse,
)


NVIDIA_CHAT_URL = (
    "https://integrate.api.nvidia.com/v1/chat/completions"
)

MAX_STARTUP_EVIDENCES = 30
MAX_NVIDIA_TEXT_CHARS = 1200
MAX_RECOMMENDATIONS = 3

TECHNOLOGY_GUIDANCE = {
    "nemo_guardrails": {
        "preferred_categories": [
            "governance_security",
        ],
        "keywords": [
            "validação",
            "revisão",
            "controle",
            "governança",
            "segurança",
            "rastreabilidade",
            "retenção",
        ],
        "focus": (
            "Use para controles programáveis, validação humana, "
            "segurança, rastreabilidade e proteção de aplicações "
            "baseadas em LLM."
        ),
    },
    "tensorrt_llm": {
        "preferred_categories": [
            "workflow_depth",
            "scale_traction",
        ],
        "keywords": [
            "tokens",
            "bilhões",
            "volume",
            "escala",
            "casos",
            "operação",
        ],
        "focus": (
            "Use para eficiência de inferência de LLM, alto volume "
            "de tokens, latência, throughput e custo operacional."
        ),
    },
    "triton_inference_server": {
        "preferred_categories": [
            "workflow_depth",
            "scale_traction",
        ],
        "keywords": [
            "tokens",
            "bilhões",
            "volume",
            "escala",
            "casos",
            "operação",
        ],
        "focus": (
            "Use para serving, batching, métricas de latência, "
            "throughput e operação de modelos em produção."
        ),
    },
    "nemo_retriever": {
        "preferred_categories": [
            "proprietary_data",
            "workflow_depth",
        ],
        "keywords": [
            "documentos internos",
            "documentos",
            "dados proprietários",
            "informações não estruturadas",
            "dados reais",
        ],
        "focus": (
            "Use para RAG, busca semântica, embeddings, reranking "
            "e recuperação sobre documentos internos."
        ),
    },
    "nvidia_ai_enterprise": {
        "preferred_categories": [
            "governance_security",
            "scale_traction",
        ],
        "keywords": [
            "governança",
            "segurança",
            "produção",
            "escala",
        ],
        "focus": (
            "Só recomende quando houver uma necessidade concreta de "
            "plataforma corporativa, suporte, ciclo de vida ou "
            "governança operacional em produção."
        ),
    },
}

def build_technology_guidance(
    research_with_context: ResearchWithNvidiaContextResponse,
    startup_catalog: dict[str, dict[str, str]],
) -> list[dict[str, Any]]:
    guidance_list = []

    for technology in research_with_context.nvidia_context.technologies:
        rule = TECHNOLOGY_GUIDANCE.get(
            technology.technology_id,
            {},
        )

        preferred_categories = rule.get(
            "preferred_categories",
            [],
        )

        keywords = rule.get(
            "keywords",
            [],
        )

        matching_evidences = []

        for evidence_id, evidence in startup_catalog.items():
            quote = evidence["quote"].casefold()

            category_score = int(
                evidence["category"] in preferred_categories
            ) * 10

            keyword_score = sum(
                keyword.casefold() in quote
                for keyword in keywords
            )

            relevance_score = category_score + keyword_score

            if relevance_score > 0:
                matching_evidences.append(
                    (
                        relevance_score,
                        evidence_id,
                    )
                )

        matching_evidences.sort(
            key=lambda item: item[0],
            reverse=True,
        )

        guidance_list.append(
            {
                "technology_id": technology.technology_id,
                "technology_name": technology.technology_name,
                "focus": rule.get("focus", ""),
                "preferred_startup_categories": (
                    preferred_categories
                ),
                "preferred_startup_evidence_ids": [
                    evidence_id
                    for _, evidence_id in matching_evidences[:4]
                ],
            }
        )

    return guidance_list

class LLMRecommendation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    technology_id: str
    priority: str
    technical_reason: str
    business_reason: str
    complexity: str
    next_action: str
    startup_evidence_ids: list[str] = Field(min_length=1)
    nvidia_evidence_ids: list[str] = Field(min_length=1)


class LLMRecommendationOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    recommendations: list[LLMRecommendation] = Field(
        min_length=1,
        max_length=MAX_RECOMMENDATIONS,
    )
    limitations: list[str] = Field(default_factory=list)


def build_startup_evidence_catalog(
    research_with_context: ResearchWithNvidiaContextResponse,
) -> dict[str, dict[str, str]]:
    catalog: dict[str, dict[str, str]] = {}

    for index, evidence in enumerate(
        research_with_context.research.evidences[
            :MAX_STARTUP_EVIDENCES
        ],
        start=1,
    ):
        evidence_id = f"startup-{index}"

        catalog[evidence_id] = {
            "source_url": str(evidence.source_url),
            "quote": evidence.quote,
            "category": evidence.category,
        }

    return catalog


def build_nvidia_evidence_catalog(
    research_with_context: ResearchWithNvidiaContextResponse,
) -> dict[str, dict[str, str]]:
    catalog: dict[str, dict[str, str]] = {}

    for technology in research_with_context.nvidia_context.technologies:
        for index, evidence in enumerate(
            technology.evidences,
            start=1,
        ):
            evidence_id = (
                f"nvidia-{technology.technology_id}-{index}"
            )

            catalog[evidence_id] = {
                "technology_id": technology.technology_id,
                "technology_name": technology.technology_name,
                "source_url": evidence.source_url,
                "quote": evidence.text[:MAX_NVIDIA_TEXT_CHARS],
            }

    return catalog


def build_llm_context(
    research_with_context: ResearchWithNvidiaContextResponse,
    startup_catalog: dict[str, dict[str, str]],
    nvidia_catalog: dict[str, dict[str, str]],
) -> dict[str, Any]:
    allowed_technologies = [
        {
            "technology_id": technology.technology_id,
            "technology_name": technology.technology_name,
            "why_retrieved": technology.why_retrieved,
        }
        for technology in research_with_context.nvidia_context.technologies
    ]

    technology_guidance = build_technology_guidance(
        research_with_context=research_with_context,
        startup_catalog=startup_catalog,
    )

    return {
        "startup": {
            "name": research_with_context.research.startup_name,
            "classification": (
                research_with_context.research.classification
                .model_dump()
            ),
            "gaps": [
                gap.model_dump()
                for gap in research_with_context.research.gaps
            ],
        },
        "allowed_technologies": allowed_technologies,
        "technology_guidance": technology_guidance,
        "startup_evidences": startup_catalog,
        "nvidia_evidences": nvidia_catalog,
    }


def build_messages(
    llm_context: dict[str, Any],
) -> list[dict[str, str]]:
    system_prompt = """
Você é o Recommendation Agent do NVIDIA Startup AI Radar.

Gere recomendações apenas com base no JSON fornecido.

REGRAS OBRIGATÓRIAS:
1. Use apenas tecnologias presentes em allowed_technologies.
2. Retorne de uma a três recomendações. Não complete três itens
   artificialmente se houver apenas uma ou duas recomendações fortes.
3. Cada recomendação deve citar ao menos uma startup_evidence
   e uma nvidia_evidence pelos respectivos IDs.
4. Para cada tecnologia, priorize os IDs presentes em
   technology_guidance.preferred_startup_evidence_ids.
5. Use as categorias indicadas em
   technology_guidance.preferred_startup_categories.
6. Não invente métricas, arquitetura, clientes, integrações,
   ganhos, custos ou detalhes internos da startup.
7. Trate gaps como ausência de evidência pública, não como falha.
8. Prioridade deve representar aderência entre necessidade pública,
   evidência disponível e tecnologia recuperada.
9. Não use "implementar a tecnologia" como próxima ação.
   Prefira ações concretas como assessment, benchmark, piloto,
   mapeamento de requisitos, teste controlado ou validação técnica.
10. Não recomende NVIDIA AI Enterprise de forma genérica.
    Use-a apenas se houver justificativa concreta para suporte,
    governança operacional, ciclo de vida ou produção corporativa.
11. Escreva technical_reason, business_reason e next_action
    em português do Brasil.
12. Retorne apenas JSON válido, sem markdown e sem texto externo.

Formato obrigatório:
{
  "recommendations": [
    {
      "technology_id": "string",
      "priority": "ALTA | MEDIA | BAIXA",
      "technical_reason": "string",
      "business_reason": "string",
      "complexity": "BAIXA | MEDIA | ALTA",
      "next_action": "string",
      "startup_evidence_ids": ["startup-1"],
      "nvidia_evidence_ids": ["nvidia-tecnologia-1"]
    }
  ],
  "limitations": ["string"]
}
""".strip()

    user_prompt = json.dumps(
        llm_context,
        ensure_ascii=False,
        indent=2,
    )

    return [
        {
            "role": "system",
            "content": system_prompt,
        },
        {
            "role": "user",
            "content": user_prompt,
        },
    ]


def extract_json_from_content(content: str) -> dict[str, Any]:
    cleaned_content = content.strip()

    if cleaned_content.startswith("```"):
        cleaned_content = cleaned_content.removeprefix("```json")
        cleaned_content = cleaned_content.removeprefix("```")
        cleaned_content = cleaned_content.removesuffix("```")
        cleaned_content = cleaned_content.strip()

    try:
        return json.loads(cleaned_content)
    except json.JSONDecodeError as error:
        raise HTTPException(
            status_code=502,
            detail=(
                "A LLM retornou um formato que não é JSON válido: "
                f"{error.msg}"
            ),
        ) from error


def normalize_priority(value: str) -> str:
    normalized = value.strip().upper()

    if normalized == "MÉDIA":
        return "MEDIA"

    return normalized


def validate_and_build_recommendations(
    llm_output: LLMRecommendationOutput,
    research_with_context: ResearchWithNvidiaContextResponse,
    startup_catalog: dict[str, dict[str, str]],
    nvidia_catalog: dict[str, dict[str, str]],
) -> list[NvidiaRecommendation]:
    technologies_by_id = {
        technology.technology_id: technology
        for technology in research_with_context.nvidia_context.technologies
    }

    validated_recommendations: list[NvidiaRecommendation] = []

    for recommendation in llm_output.recommendations:
        technology = technologies_by_id.get(
            recommendation.technology_id
        )

        if technology is None:
            continue

        startup_evidences = [
            RecommendationCitation(
                evidence_id=evidence_id,
                source_type="startup",
                source_url=startup_catalog[evidence_id]["source_url"],
                quote=startup_catalog[evidence_id]["quote"],
            )
            for evidence_id in recommendation.startup_evidence_ids
            if evidence_id in startup_catalog
        ]

        nvidia_evidences = [
            RecommendationCitation(
                evidence_id=evidence_id,
                source_type="nvidia",
                source_url=nvidia_catalog[evidence_id]["source_url"],
                quote=nvidia_catalog[evidence_id]["quote"],
            )
            for evidence_id in recommendation.nvidia_evidence_ids
            if (
                evidence_id in nvidia_catalog
                and nvidia_catalog[evidence_id]["technology_id"]
                == recommendation.technology_id
            )
        ]

        if not startup_evidences or not nvidia_evidences:
            continue

        preferred_categories = set(
            TECHNOLOGY_GUIDANCE.get(
                recommendation.technology_id,
                {},
            ).get(
                "preferred_categories",
                [],
            )
        )

        has_relevant_startup_evidence = any(
            startup_catalog[evidence.evidence_id]["category"]
            in preferred_categories
            for evidence in startup_evidences
        )

        if preferred_categories and not has_relevant_startup_evidence:
            continue

        priority = normalize_priority(recommendation.priority)
        complexity = normalize_priority(recommendation.complexity)

        if priority not in {"ALTA", "MEDIA", "BAIXA"}:
            continue

        if complexity not in {"ALTA", "MEDIA", "BAIXA"}:
            continue

        validated_recommendations.append(
            NvidiaRecommendation(
                technology_id=technology.technology_id,
                technology_name=technology.technology_name,
                priority=priority,
                technical_reason=recommendation.technical_reason,
                business_reason=recommendation.business_reason,
                complexity=complexity,
                next_action=recommendation.next_action,
                startup_evidences=startup_evidences,
                nvidia_evidences=nvidia_evidences,
            )
        )

    if not validated_recommendations:
        raise HTTPException(
            status_code=502,
            detail=(
                "A LLM não retornou recomendações com tecnologia "
                "e evidências válidas."
            ),
        )

    return validated_recommendations


async def generate_recommendations(
    research_with_context: ResearchWithNvidiaContextResponse,
) -> RecommendationResponse:
    api_key = os.getenv("NVIDIA_API_KEY")
    model = os.getenv(
        "NVIDIA_LLM_MODEL",
        "meta/llama-3.1-8b-instruct",
    )

    if not api_key:
        raise HTTPException(
            status_code=503,
            detail=(
                "NVIDIA_API_KEY não configurada no arquivo .env."
            ),
        )

    startup_catalog = build_startup_evidence_catalog(
        research_with_context
    )

    nvidia_catalog = build_nvidia_evidence_catalog(
        research_with_context
    )

    llm_context = build_llm_context(
        research_with_context=research_with_context,
        startup_catalog=startup_catalog,
        nvidia_catalog=nvidia_catalog,
    )

    payload = {
        "model": model,
        "messages": build_messages(llm_context),
        "temperature": 0.1,
        "top_p": 0.9,
        "max_tokens": 1600,
    }

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Accept": "application/json",
        "Content-Type": "application/json",
    }

    try:
        async with httpx.AsyncClient(timeout=90.0) as client:
            response = await client.post(
                NVIDIA_CHAT_URL,
                headers=headers,
                json=payload,
            )

        response.raise_for_status()

    except httpx.HTTPStatusError as error:
        detail = error.response.text[:300]

        raise HTTPException(
            status_code=502,
            detail=(
                "Falha na NVIDIA NIM API "
                f"({error.response.status_code}): {detail}"
            ),
        ) from error

    except httpx.HTTPError as error:
        raise HTTPException(
            status_code=502,
            detail=(
                "Não foi possível acessar a NVIDIA NIM API: "
                f"{error}"
            ),
        ) from error

    response_data = response.json()

    try:
        content = response_data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as error:
        raise HTTPException(
            status_code=502,
            detail=(
                "A resposta da NVIDIA NIM não trouxe conteúdo "
                "de chat no formato esperado."
            ),
        ) from error

    parsed_json = extract_json_from_content(content)

    try:
        llm_output = LLMRecommendationOutput.model_validate(
            parsed_json
        )
    except Exception as error:
        raise HTTPException(
            status_code=502,
            detail=(
                "A LLM retornou JSON fora do contrato esperado: "
                f"{error}"
            ),
        ) from error

    recommendations = validate_and_build_recommendations(
        llm_output=llm_output,
        research_with_context=research_with_context,
        startup_catalog=startup_catalog,
        nvidia_catalog=nvidia_catalog,
    )

    return RecommendationResponse(
        model=model,
        recommendations=recommendations,
        limitations=llm_output.limitations,
    )