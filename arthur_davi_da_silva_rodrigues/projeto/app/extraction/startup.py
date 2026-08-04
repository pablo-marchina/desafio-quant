from urllib.parse import urlparse

from app.extraction.schemas import EvidenceClaimDraft, StartupProfileDraft
from app.llm.client import LlmUnavailableError, generate_openai_json, is_llm_enabled
from app.models.enums import ClaimValidationStatus
from app.settings import get_settings

AI_TERMS = (
    "ai",
    "artificial intelligence",
    "inteligencia artificial",
    "inteligência artificial",
    "machine learning",
    "deep learning",
    "llm",
    "generative ai",
    "agent",
    "agents",
    "automation",
    "automação",
)

SECTOR_TERMS = {
    "healthcare": ("healthcare", "health", "medical", "saude", "saúde", "hospital"),
    "finance": ("finance", "financial", "fintech", "banking", "pagamento", "credito"),
    "cybersecurity": ("cybersecurity", "security", "fraud", "threat", "segurança"),
    "retail": ("retail", "commerce", "ecommerce", "marketplace", "varejo"),
    "education": ("education", "edtech", "learning", "ensino", "educação"),
    "legal": ("legal", "law", "juridico", "jurídico", "compliance"),
    "robotics": ("robotics", "robot", "autonomy", "simulação", "simulation"),
}

TECHNOLOGY_TERMS = {
    "LLM": ("llm", "large language model", "gpt", "claude", "language model"),
    "AI agents": ("agent", "agents", "agente", "agentes"),
    "Computer vision": ("computer vision", "image recognition", "visão computacional"),
    "Speech AI": ("voice", "speech", "transcription", "asr", "tts", "voz"),
    "Data pipeline": ("data pipeline", "etl", "analytics", "data platform"),
    "External AI API": ("openai", "anthropic", "gemini", "api"),
}


def extract_startup_profile_from_source(
    url: str,
    title: str | None,
    extracted_text: str | None,
) -> StartupProfileDraft:
    settings = get_settings()
    if is_llm_enabled(settings):
        try:
            return _extract_with_llm(url, title, extracted_text or "")
        except (LlmUnavailableError, KeyError, TypeError, ValueError):
            pass

    return _extract_with_heuristics(url, title, extracted_text)


def _extract_with_heuristics(
    url: str,
    title: str | None,
    extracted_text: str | None,
) -> StartupProfileDraft:
    normalized_text = " ".join((extracted_text or "").split())
    startup_name = _extract_name(url, title)
    description = _first_sentence(normalized_text)
    sectors = _find_matches(normalized_text, SECTOR_TERMS)
    technology_signals = _find_matches(normalized_text, TECHNOLOGY_TERMS)
    evidence_claims = _deduplicate_claims(
        _build_evidence_claims(normalized_text, sectors, technology_signals)
    )
    accepted_claims = tuple(
        claim
        for claim in evidence_claims
        if claim.validation_status == ClaimValidationStatus.ACCEPTED
    )
    review_claims = tuple(
        claim
        for claim in evidence_claims
        if claim.validation_status == ClaimValidationStatus.NEEDS_REVIEW
    )

    return StartupProfileDraft(
        name=startup_name,
        website=url,
        description=description,
        ai_usage_summary=_summarize_ai_usage(normalized_text),
        sectors=tuple(sectors),
        technology_signals=tuple(technology_signals),
        evidence_claims=tuple(evidence_claims),
        accepted_claims=accepted_claims,
        review_claims=review_claims,
    )


def _extract_with_llm(url: str, title: str | None, extracted_text: str) -> StartupProfileDraft:
    settings = get_settings()
    response = generate_openai_json(
        settings=settings,
        system_prompt=(
            "Você é um analista técnico da NVIDIA avaliando startups. "
            "Extraia apenas informações apoiadas no texto fornecido. "
            "Responda em JSON válido, sem markdown."
        ),
        user_prompt=(
            "Analise a fonte pública abaixo e retorne este JSON: "
            "{"
            '"name": string|null, '
            '"description": string|null, '
            '"ai_usage_summary": string|null, '
            '"sectors": string[], '
            '"technology_signals": string[], '
            '"evidence_claims": ['
            '{"claim": string, "claim_type": string, "supporting_text": string, '
            '"confidence": number}'
            "]"
            "}. "
            "Use setores curtos em inglês quando possível, como healthcare, finance, "
            "legal, education, retail, cybersecurity, robotics. "
            "Use sinais tecnológicos curtos, como LLM, AI agents, Computer vision, "
            "Speech AI, Data pipeline, External AI API. "
            f"URL: {url}\nTítulo: {title or ''}\nTexto:\n{extracted_text[:6000]}"
        ),
    )
    evidence_claims = tuple(
        _claim_from_llm(claim)
        for claim in _list_value(response.get("evidence_claims"))
        if isinstance(claim, dict)
    )
    accepted_claims = tuple(
        claim
        for claim in evidence_claims
        if claim.validation_status == ClaimValidationStatus.ACCEPTED
    )
    review_claims = tuple(
        claim
        for claim in evidence_claims
        if claim.validation_status == ClaimValidationStatus.NEEDS_REVIEW
    )

    return StartupProfileDraft(
        name=_optional_string(response.get("name")) or _extract_name(url, title),
        website=url,
        description=_optional_string(response.get("description")),
        ai_usage_summary=_optional_string(response.get("ai_usage_summary")),
        sectors=tuple(_string_list(response.get("sectors"))),
        technology_signals=tuple(_string_list(response.get("technology_signals"))),
        evidence_claims=evidence_claims,
        accepted_claims=accepted_claims,
        review_claims=review_claims,
    )


def _claim_from_llm(raw_claim: dict[str, object]) -> EvidenceClaimDraft:
    confidence = _float_between_zero_and_one(raw_claim.get("confidence"))
    return EvidenceClaimDraft(
        claim=_optional_string(raw_claim.get("claim")) or "Evidência extraída por LLM.",
        claim_type=_optional_string(raw_claim.get("claim_type")) or "general",
        supporting_text=_optional_string(raw_claim.get("supporting_text")) or "",
        confidence=confidence,
        validation_status=_validation_status_for_confidence(confidence),
    )


def _optional_string(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    stripped = value.strip()
    return stripped or None


def _list_value(value: object) -> list[object]:
    return value if isinstance(value, list) else []


def _string_list(value: object) -> list[str]:
    return [
        item.strip()
        for item in _list_value(value)
        if isinstance(item, str) and item.strip()
    ]


def _float_between_zero_and_one(value: object) -> float:
    if not isinstance(value, int | float):
        return 0.55
    return max(0.0, min(float(value), 1.0))


def _extract_name(url: str, title: str | None) -> str | None:
    if title:
        return title.split("|")[0].split("-")[0].strip()

    hostname = urlparse(url).hostname
    if not hostname:
        return None

    domain_parts = hostname.removeprefix("www.").split(".")
    if not domain_parts:
        return None

    return domain_parts[0].replace("-", " ").title()


def _first_sentence(text: str) -> str | None:
    if not text:
        return None

    sentence_endings = [index for index in (text.find("."), text.find("\n")) if index != -1]
    if not sentence_endings:
        return text[:280]

    return text[: min(sentence_endings) + 1][:280]


def _summarize_ai_usage(text: str) -> str | None:
    evidence_span = _find_first_span(text, AI_TERMS)
    if not evidence_span:
        return None

    return evidence_span


def _find_matches(text: str, taxonomy: dict[str, tuple[str, ...]]) -> list[str]:
    normalized_text = text.lower()
    matches: list[str] = []

    for label, terms in taxonomy.items():
        if any(term in normalized_text for term in terms):
            matches.append(label)

    return matches


def _build_evidence_claims(
    text: str,
    sectors: list[str],
    technology_signals: list[str],
) -> list[EvidenceClaimDraft]:
    claims: list[EvidenceClaimDraft] = []

    ai_span = _find_first_span(text, AI_TERMS)
    if ai_span:
        claims.append(
            EvidenceClaimDraft(
                claim="A startup mostra sinais públicos de uso de IA.",
                claim_type="ai_usage",
                supporting_text=ai_span,
                confidence=0.72,
                validation_status=_validation_status_for_confidence(0.72),
            )
        )

    for sector in sectors:
        sector_span = _find_first_span(text, SECTOR_TERMS[sector])
        if sector_span:
            claims.append(
                EvidenceClaimDraft(
                    claim=f"A startup parece relacionada ao setor de {_sector_label(sector)}.",
                    claim_type="sector",
                    supporting_text=sector_span,
                    confidence=0.66,
                    validation_status=_validation_status_for_confidence(0.66),
                )
            )

    for technology_signal in technology_signals:
        signal_span = _find_first_span(text, TECHNOLOGY_TERMS[technology_signal])
        if signal_span:
            signal_label = _signal_label(technology_signal)
            claims.append(
                EvidenceClaimDraft(
                    claim=f"A startup mostra sinal tecnológico de {signal_label}.",
                    claim_type="technology_signal",
                    supporting_text=signal_span,
                    confidence=0.68,
                    validation_status=_validation_status_for_confidence(0.68),
                )
            )

    return claims


def _deduplicate_claims(claims: list[EvidenceClaimDraft]) -> list[EvidenceClaimDraft]:
    claims_by_key: dict[tuple[str, str], EvidenceClaimDraft] = {}

    for claim in claims:
        key = (claim.claim_type, claim.claim.lower())
        existing_claim = claims_by_key.get(key)
        if not existing_claim or claim.confidence > existing_claim.confidence:
            claims_by_key[key] = claim

    return list(claims_by_key.values())


def _validation_status_for_confidence(confidence: float) -> str:
    if confidence >= 0.7:
        return ClaimValidationStatus.ACCEPTED
    if confidence >= 0.55:
        return ClaimValidationStatus.NEEDS_REVIEW
    return ClaimValidationStatus.REJECTED


def _sector_label(sector: str) -> str:
    return {
        "healthcare": "saúde",
        "finance": "finanças",
        "cybersecurity": "cibersegurança",
        "retail": "varejo",
        "education": "educação",
        "legal": "jurídico",
        "robotics": "robótica",
    }.get(sector, sector)


def _signal_label(signal: str) -> str:
    return {
        "AI agents": "agentes de IA",
        "Computer vision": "visão computacional",
        "Speech AI": "IA de voz",
        "Data pipeline": "pipeline de dados",
        "External AI API": "API externa de IA",
    }.get(signal, signal)


def _find_first_span(text: str, terms: tuple[str, ...], context_chars: int = 120) -> str | None:
    normalized_text = text.lower()
    match_indexes: list[int] = []

    for term in terms:
        match_index = normalized_text.find(term)
        if match_index >= 0:
            match_indexes.append(match_index)

    if not match_indexes:
        return None

    match_index = min(match_indexes)
    start_index = max(match_index - context_chars, 0)
    end_index = min(match_index + context_chars, len(text))
    return text[start_index:end_index].strip()
