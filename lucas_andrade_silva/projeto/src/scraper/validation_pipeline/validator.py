from __future__ import annotations

import hashlib
import re
import unicodedata
from typing import Any

STRONG_SOURCES = {"cubo", "liga", "darwin"}
NEWS_SOURCES = {"startups.com.br", "braziljournal"}
AI_TERMS = (
    " inteligencia artificial ", " ia ", " machine learning ", " llm ", " agentes ",
    " automacao ", " nlp ", " computer vision ", " visao computacional ", " chatbot ",
    " data science ", " analytics ", " modelos preditivos ", " recomendacao ",
)
STARTUP_TERMS = (
    " startup", " acelerador", " investimento", " aporte", " rodada", " venture capital",
    " produto escalavel", " plataforma", " saas", " inovacao", " tecnologia proprietaria",
)
BRAZIL_TERMS = (" brasil", " brasileira", " brasileiro", " cnpj", " sao paulo", " rio de janeiro", " belo horizonte", " florianopolis", " curitiba")
FOREIGN_TERMS = ("fundada no mexico", "sediada no mexico", "fundada nos estados unidos", "sediada nos eua", "fundada na argentina", "sediada no chile")
GENERIC_NAMES = {"startup", "startups", "empresa", "tecnologia", "inovacao", "saiba mais", "portfolio", "noticias", "inteligencia artificial"}


def _plain(value: str | None) -> str:
    text = unicodedata.normalize("NFKD", value or "")
    return "".join(c for c in text if not unicodedata.combining(c)).casefold()


def normalize_company_name(name: str | None) -> str:
    value = _plain(name)
    value = re.sub(r"\b(?:ltda|s/?a|sa|inc|llc|tecnologia|technology)\b\.?", " ", value)
    return re.sub(r"[^a-z0-9]+", " ", value).strip()


def detect_noise(candidate: dict[str, Any] | str) -> bool:
    name = candidate if isinstance(candidate, str) else str(candidate.get("company_name") or "")
    normalized = normalize_company_name(name)
    words = normalized.split()
    if not normalized or normalized in GENERIC_NAMES or len(name) > 100 or len(words) > 8:
        return True
    if re.search(r"\b(?:ceo|cto|cfo|founder|fundador|diretor|gerente|presidente|analista|especialista)\b", _plain(name)):
        return True
    if re.search(r"[.!?;:]", name) or re.match(r"^(?:como|porque|quando|onde|quem|o |a |os |as |um |uma )", _plain(name)):
        return True
    person_pattern = len(words) in {2, 3, 4} and all(word[:1].isalpha() for word in words)
    person_context = _plain((candidate if isinstance(candidate, dict) else {}).get("description") if isinstance(candidate, dict) else "")
    if person_pattern and re.search(r"\b(?:fundador|ceo|diretor|executivo|jornalista)\b", person_context) and "startup" not in person_context:
        return True
    return False


def _source_name(candidate: dict[str, Any]) -> str:
    explicit = _plain(str(candidate.get("source_name") or ""))
    text = explicit
    if "cubo" in text: return "cubo"
    if "liga" in text: return "liga"
    if "darwin" in text: return "darwin"
    if "startups.com.br" in text: return "startups.com.br"
    if "braziljournal" in text: return "braziljournal"
    return explicit or "unknown"


def _year(candidate: dict[str, Any]) -> int | None:
    value = str(candidate.get("foundation_year") or candidate.get("founding_year") or "")
    match = re.search(r"\b(19\d{2}|20\d{2})\b", value)
    return int(match.group(1)) if match else None


def infer_brazilian(candidate: dict[str, Any]) -> bool | None:
    text = f" {_plain(str(candidate.get('description') or ''))} "
    source = _source_name(candidate)
    if any(term in text for term in FOREIGN_TERMS) and not any(term in text for term in BRAZIL_TERMS):
        return False
    if source in STRONG_SOURCES or any(term in text for term in BRAZIL_TERMS):
        return True
    return None


def infer_startup(candidate: dict[str, Any]) -> bool | None:
    if _source_name(candidate) in STRONG_SOURCES:
        return True
    text = f" {_plain(str(candidate.get('description') or ''))} "
    return True if any(term in text for term in STARTUP_TERMS) else None


def infer_ai_usage(candidate: dict[str, Any]) -> tuple[bool | None, str]:
    description = _plain(str(candidate.get("description") or ""))
    text = f" {description} "
    if not description or len(description) < 25:
        return False, "NON_AI"
    matches = [term for term in AI_TERMS if term in text]
    if not matches:
        return False, "NON_AI"
    central = re.search(r"(?:plataforma|produto|solucao|startup|software).{0,50}(?:inteligencia artificial|\bia\b|machine learning|llm)|(?:ai-native|nativa de ia)", text)
    return True, "AI_NATIVE" if central else "AI_ENABLED"


def assign_priority(foundation_year: int | None) -> str:
    if foundation_year is None: return "REVIEW"
    if foundation_year >= 2025: return "HIGH"
    if foundation_year >= 2020: return "MEDIUM"
    return "LOW"


def calculate_score(*, real: bool, brazilian: bool | None, startup: bool | None,
                    uses_ai: bool | None, strong_source: bool, foundation_year: int | None,
                    noise: bool, article_only: bool) -> int:
    score = 25 if real else 0
    score += 20 if brazilian is True else 0
    score += 20 if startup is True else 0
    score += 20 if uses_ai is True else 0
    score += 10 if strong_source else 0
    score += 5 if foundation_year is not None and foundation_year >= 2025 else 0
    score -= 30 if noise else 0
    score -= 20 if article_only else 0
    score -= 30 if brazilian is False else 0
    return max(0, min(100, score))


def assign_status(*, real: bool, brazilian: bool | None, startup: bool | None,
                  score: int, noise: bool) -> str:
    if noise or not real or brazilian is False:
        return "REJECTED"
    if real and brazilian is True and startup is True and score >= 70:
        return "APPROVED"
    return "REVIEW" if score >= 40 or None in {brazilian, startup} else "REJECTED"


def validate_candidate(candidate: dict[str, Any]) -> dict[str, Any]:
    name = re.sub(r"\s+", " ", str(candidate.get("company_name") or "")).strip()
    normalized = normalize_company_name(name)
    noise = detect_noise(candidate)
    real = bool(normalized and not noise)
    source = _source_name(candidate)
    brazilian = infer_brazilian(candidate)
    startup = infer_startup(candidate)
    uses_ai, ai_classification = infer_ai_usage(candidate)
    foundation_year = _year(candidate)
    score = calculate_score(real=real, brazilian=brazilian, startup=startup, uses_ai=uses_ai,
        strong_source=source in STRONG_SOURCES, foundation_year=foundation_year, noise=noise,
        article_only=source in NEWS_SOURCES)
    status = assign_status(real=real, brazilian=brazilian, startup=startup, score=score, noise=noise)
    reasons = []
    if noise: reasons.append("clear_noise_or_non_company_name")
    if brazilian is False: reasons.append("foreign_without_brazil_evidence")
    if status == "REJECTED" and not reasons: reasons.append("insufficient_company_or_startup_evidence")
    raw_id = candidate.get("raw_company_id") or candidate.get("id")
    if raw_id is None:
        raw_id = hashlib.sha256(f"{name}|{candidate.get('source_url','')}".encode()).hexdigest()
    description = str(candidate.get("description") or "").strip()
    source_url = str(candidate.get("source_url") or "").strip() or None
    return {
        "raw_company_id": str(raw_id), "company_name": name, "normalized_name": normalized,
        "source_name": source, "source_url": source_url, "is_valid_company": real,
        "is_brazilian": brazilian, "is_startup": startup, "uses_ai_potentially": uses_ai,
        "ai_classification": ai_classification, "foundation_year": foundation_year,
        "priority": assign_priority(foundation_year), "validation_status": status,
        "rejection_reason": "; ".join(reasons) or None, "evidence_text": description[:4000] or None,
        "evidence_urls": [source_url] if source_url else [], "confidence_score": score,
    }
