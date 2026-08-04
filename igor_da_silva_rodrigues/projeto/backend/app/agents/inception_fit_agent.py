from __future__ import annotations

import re
from typing import Any

from app.core.contracts import validate_contract
from app.core.schemas import InceptionFitInput, InceptionFitOutput


INCEPTION_URL = "https://www.nvidia.com/en-us/startups/"
NEED_KEYWORDS = {
    "credits": ("credito", "crédito", "custo", "budget", "cloud"),
    "technical_support": (
        "latencia",
        "latência",
        "deploy",
        "inferencia",
        "inferência",
        "otimiz",
        "modelo",
        "mlops",
    ),
    "infrastructure": ("gpu", "infra", "escal", "compute", "processamento"),
    "go_to_market": ("mercado", "cliente", "vendas", "go-to-market", "comercial"),
    "networking": ("parceiro", "network", "ecossistema", "investidor", "conex"),
}
BENEFITS = {
    "credits": "Créditos e ofertas de parceiros",
    "technical_support": "Recursos e suporte técnico NVIDIA",
    "infrastructure": "Acesso ao ecossistema de tecnologia NVIDIA",
    "go_to_market": "Suporte de go-to-market e visibilidade",
    "networking": "Comunidade e conexões do NVIDIA Inception",
}


class InceptionFitAgent:
    """Map explicit startup signals to Inception needs without assuming eligibility."""

    def assess(self, payload: InceptionFitInput | dict[str, Any]) -> dict[str, Any]:
        data = validate_contract(InceptionFitInput, payload)
        profile = data.startup_profile
        additional = profile.get("dados_adicionais") or {}
        inception_data = additional.get("inception") or {}
        eligibility, eligibility_reason = _eligibility(inception_data)
        stage, stage_reason = _stage(inception_data, additional)
        evidence_urls = _evidence_urls(data)
        needs_text = " ".join(data.classificacao_ia.necessidades_limitacoes).lower()
        needs = []
        benefit_matches = []
        for need, keywords in NEED_KEYWORDS.items():
            matched = sorted({word for word in keywords if word in needs_text})
            if matched:
                justification = (
                    "Necessidade identificada nas limitações técnicas validadas: "
                    + ", ".join(matched)
                    + "."
                )
                status = "identified"
                benefit_matches.append(
                    {
                        "benefit": BENEFITS[need],
                        "match_status": "strong" if evidence_urls else "possible",
                        "justification": justification,
                        "source_urls": [INCEPTION_URL, *evidence_urls[:2]],
                        "confidence": 0.8 if evidence_urls else 0.55,
                    }
                )
            else:
                justification = "Os dados coletados não confirmam esta necessidade."
                status = "unknown"
            needs.append(
                {
                    "need": need,
                    "status": status,
                    "justification": justification,
                    "evidence_urls": evidence_urls[:3] if matched else [],
                }
            )

        questions = _open_questions(eligibility, stage, needs)
        output = {
            "startup": data.classificacao_ia.startup,
            "eligibility_status": eligibility,
            "eligibility_justification": eligibility_reason,
            "startup_stage": stage,
            "stage_justification": stage_reason,
            "needs": needs,
            "benefit_matches": benefit_matches,
            "open_questions": questions,
        }
        return validate_contract(InceptionFitOutput, output).model_dump(mode="json")


def avaliar_fit_inception(payload: InceptionFitInput | dict[str, Any]) -> dict[str, Any]:
    return InceptionFitAgent().assess(payload)


def _eligibility(inception_data: dict[str, Any]) -> tuple[str, str]:
    confirmed = inception_data.get("eligibility_confirmed")
    if confirmed is True or inception_data.get("member") is True:
        return "eligible", "Elegibilidade ou participação informada explicitamente nos dados da startup."
    if confirmed is False:
        return "ineligible", "Inelegibilidade informada explicitamente nos dados da startup."
    return "unknown", "As fontes coletadas não comprovam todos os critérios de elegibilidade do programa."


def _stage(inception_data: dict[str, Any], additional: dict[str, Any]) -> tuple[str, str]:
    explicit = inception_data.get("startup_stage") or additional.get("startup_stage")
    if explicit in {"early", "growth", "scale"}:
        return explicit, "Estágio informado explicitamente nos dados estruturados da startup."
    funding = str(additional.get("funding_round") or "").lower().replace(" ", "_")
    if funding in {"pre_seed", "seed"}:
        return "early", f"Estágio derivado da rodada explicitamente informada: {funding}."
    if funding in {"series_a", "series_b"}:
        return "growth", f"Estágio derivado da rodada explicitamente informada: {funding}."
    if re.fullmatch(r"series_[c-z]", funding):
        return "scale", f"Estágio derivado da rodada explicitamente informada: {funding}."
    return "unknown", "Não há rodada ou estágio confirmado nas fontes fornecidas."


def _evidence_urls(data: InceptionFitInput) -> list[str]:
    urls = list(data.classificacao_ia.evidencias_suporte)
    if data.validacao_evidencias:
        urls.extend(
            evidence.url
            for evidence in (
                data.validacao_evidencias.evidencias_validadas
                + data.validacao_evidencias.evidencias_medias
            )
        )
    return list(dict.fromkeys(str(url) for url in urls if str(url).startswith(("http://", "https://"))))


def _open_questions(eligibility: str, stage: str, needs: list[dict[str, Any]]) -> list[str]:
    questions = []
    if eligibility == "unknown":
        questions.append("A startup atende atualmente aos critérios oficiais de elegibilidade do NVIDIA Inception?")
    if stage == "unknown":
        questions.append("Qual é o estágio atual da startup e sua rodada de financiamento mais recente?")
    unknown_needs = [item["need"] for item in needs if item["status"] == "unknown"]
    if unknown_needs:
        questions.append("Quais necessidades são prioritárias: " + ", ".join(unknown_needs) + "?")
    return questions
