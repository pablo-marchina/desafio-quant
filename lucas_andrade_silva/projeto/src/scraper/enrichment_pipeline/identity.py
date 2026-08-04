from __future__ import annotations

import re
import unicodedata
from urllib.parse import urlsplit

from . import config
from .signals import BRAZIL_MARKERS, detect_country, detect_language, normalize_text

GENERIC_BRAND_TOKENS = {
    "ai",
    "ia",
    "tech",
    "labs",
    "lab",
    "app",
    "digital",
    "software",
    "systems",
    "system",
    "startup",
    "brasil",
    "brazil",
}
OFFICIAL_PATH_HINTS = ("/company/", "/empresa/", "/careers/", "/jobs/", "/vagas/")
WRONG_COMPANY_THRESHOLD = 25
FOREIGN_TLDS = (
    ".ar",
    ".bg",
    ".cl",
    ".cn",
    ".cz",
    ".de",
    ".fr",
    ".hu",
    ".it",
    ".jp",
    ".mx",
    ".pl",
    ".ro",
    ".ru",
    ".sk",
    ".tr",
    ".ua",
    ".uk",
    ".us",
)
BRAZIL_COMPANY_PATTERNS = (
    r"\b(?:empresa|startup|companhia|negocio)\s+brasileir[ao]\b",
    r"\bbrazilian\s+(?:company|startup|business)\b",
    r"\b(?:empresa|startup|companhia)\s+(?:do|no)\s+brasil\b",
    r"\b(?:sediad[ao]|fundad[ao])\s+(?:no|em)\s+brasil\b",
    r"\b(?:based|headquartered|founded)\s+in\s+brazil\b",
    r"\bcnpj\b",
)


def normalize_company_name(name: str | None) -> str:
    text = unicodedata.normalize("NFKD", name or "")
    text = "".join(char for char in text if not unicodedata.combining(char))
    text = re.sub(r"\b(?:ltda|s/?a|sa|inc|llc|corp|tecnologia|technology)\b\.?", " ", text, flags=re.I)
    return re.sub(r"[^a-zA-Z0-9]+", " ", text).strip().casefold()


def company_tokens(name: str | None) -> list[str]:
    tokens = [token for token in normalize_company_name(name).split() if len(token) >= 3 and token not in GENERIC_BRAND_TOKENS]
    return tokens[:4]


def build_validation_result(
    classification: str,
    confidence: int,
    reason: str,
    matched_signals: list[str],
    negative_signals: list[str],
) -> dict[str, object]:
    bounded = max(0, min(100, int(confidence)))
    normalized_class = classification if classification in config.IDENTITY_CLASSIFICATIONS else "INSUFFICIENT_EVIDENCE"
    return {
        "classification": normalized_class,
        "confidence": bounded,
        "reason": reason,
        "matched_signals": sorted(dict.fromkeys(matched_signals)),
        "negative_signals": sorted(dict.fromkeys(negative_signals)),
        "should_update_database": normalized_class == "MATCH" and bounded >= config.IDENTITY_MATCH_THRESHOLD,
    }


def _brand_in_text(tokens: list[str], text: str) -> bool:
    normalized = normalize_text(text)
    return bool(tokens) and all(token in normalized for token in tokens)


def _host_brand_match(tokens: list[str], host: str) -> bool:
    normalized_host = normalize_text(host).replace("-", " ").replace(".", " ")
    return bool(tokens) and any(token in normalized_host for token in tokens)


def _product_overlap(candidate: dict[str, object], text: str) -> bool:
    summary = normalize_text(
        str(candidate.get("description") or "")
        + " "
        + str(candidate.get("segment") or "")
        + " "
        + str(candidate.get("stage") or "")
    )
    if not summary or not text:
        return False
    seed_terms = [term for term in re.findall(r"[a-z0-9]{4,}", summary) if term not in GENERIC_BRAND_TOKENS]
    if not seed_terms:
        return False
    normalized_text = normalize_text(text)
    overlap = sum(term in normalized_text for term in seed_terms[:8])
    return overlap >= 2


def _looks_foreign(host: str, text: str) -> bool:
    country = detect_country(text, host)
    return bool(country and country != "BR")


def _has_brazil_company_evidence(host: str, text: str) -> bool:
    if host.endswith(".br"):
        return True
    normalized = unicodedata.normalize("NFKD", normalize_text(text))
    normalized = "".join(
        char for char in normalized if not unicodedata.combining(char)
    )
    if any(re.search(pattern, normalized) for pattern in BRAZIL_COMPANY_PATTERNS):
        return True
    has_company_context = bool(
        re.search(
            r"\b(?:empresa|startup|company|sede|headquarters|escritorio|office)\b",
            normalized,
        )
    )
    has_brazilian_location = any(
        marker in f" {normalized} "
        for marker in BRAZIL_MARKERS
        if marker.strip() not in {"brasil", "brasileira", "brasileiro", "cnpj"}
    )
    return has_company_context and has_brazilian_location


def validate_source_identity(candidate: dict[str, object], source: dict[str, object]) -> dict[str, object]:
    name = str(candidate.get("company_name") or candidate.get("nome") or "")
    tokens = company_tokens(name)
    host = (urlsplit(str(source.get("url") or "")).hostname or "").removeprefix("www.").casefold()
    title = str(source.get("title") or "")
    snippet = str(source.get("snippet") or "")
    raw_text = str(source.get("raw_text") or "")
    metadata = source.get("metadata") or {}
    metadata_text = " ".join(str(value) for value in metadata.values() if isinstance(value, (str, int, float)))
    corpus = " ".join(part for part in [title, snippet, raw_text[:4000], metadata_text] if part).strip()
    country = detect_country(corpus, host)
    brazil_company_evidence = _has_brazil_company_evidence(host, corpus)
    language = detect_language(corpus)
    tld = next((suffix for suffix in FOREIGN_TLDS if host.endswith(suffix)), None)

    matched_signals: list[str] = []
    negative_signals: list[str] = []
    score = 0

    if _brand_in_text(tokens, title):
        matched_signals.append("brand_in_title")
        score += 30
    if _brand_in_text(tokens, snippet):
        matched_signals.append("brand_in_snippet")
        score += 15
    if _brand_in_text(tokens, raw_text[:1200]):
        matched_signals.append("brand_in_body")
        score += 20
    if _host_brand_match(tokens, host):
        matched_signals.append("brand_in_host")
        score += 25

    normalized_path = urlsplit(str(source.get("url") or "")).path.casefold()
    if any(hint in normalized_path for hint in OFFICIAL_PATH_HINTS):
        matched_signals.append("official_path_hint")
        score += 8

    if brazil_company_evidence:
        matched_signals.append("brazil_context")
        score += 20
    elif country == "BR":
        matched_signals.append("brazil_mention")
        score += 5
        negative_signals.append("brazil_company_context_unconfirmed")
    elif country:
        negative_signals.append(f"foreign_country:{country}")
        score -= 55

    if language == "pt-BR":
        matched_signals.append("portuguese_context")
        score += 8
    elif language == "en" and " brasil" not in normalize_text(corpus) and " brazil" not in normalize_text(corpus):
        negative_signals.append("english_without_brazil_context")
        score -= 12

    if _product_overlap(candidate, corpus):
        matched_signals.append("product_overlap")
        score += 12

    if not matched_signals:
        negative_signals.append("no_brand_match")
        score -= 10

    if _looks_foreign(host, corpus) and country != "BR":
        negative_signals.append("foreign_domain_or_context")
        score -= 30

    if tld:
        negative_signals.append(f"foreign_tld:{tld.removeprefix('.')}")
        score -= 25

    if not _host_brand_match(tokens, host) and host and not any(marker in f" {normalize_text(corpus)} " for marker in BRAZIL_MARKERS):
        negative_signals.append("host_without_brand_or_brazil_context")
        score -= 10

    source_type = str(source.get("source_type") or "")
    if source_type == "github" and metadata.get("login") and _brand_in_text(tokens, str(metadata.get("login"))):
        matched_signals.append("github_login_match")
        score += 20
    if source_type == "gupy" and ("gupy" in host or "jobs" in normalized_path or "vagas" in normalized_path):
        matched_signals.append("jobs_context")
        score += 10
    if source_type == "linkedin" and "linkedin.com" in host:
        matched_signals.append("linkedin_company_context")
        score += 6

    reason = "insufficient evidence"
    incompatible_foreign = any(
        signal.startswith(
            ("foreign_country:", "foreign_tld:", "foreign_domain_or_context")
        )
        for signal in negative_signals
    )

    has_brand_evidence = any(
        signal in matched_signals
        for signal in (
            "brand_in_title",
            "brand_in_snippet",
            "brand_in_body",
            "brand_in_host",
        )
    )

    if incompatible_foreign and not brazil_company_evidence:
        reason = "dominio, idioma ou pais incompativel com uma startup brasileira"
        classification = "WRONG_COMPANY"
    elif (
        score >= config.IDENTITY_MATCH_THRESHOLD
        and has_brand_evidence
        and brazil_company_evidence
    ):
        reason = "brand identity and Brazilian company context are consistent"
        classification = "MATCH"
    elif has_brand_evidence and not brazil_company_evidence:
        reason = (
            "brand matches, but there is no evidence that the source represents "
            "a Brazilian company"
        )
        classification = "POSSIBLE_MATCH"
    elif score >= config.IDENTITY_POSSIBLE_THRESHOLD:
        reason = "partial brand/context match; requires manual review"
        classification = "POSSIBLE_MATCH"
    elif score <= WRONG_COMPANY_THRESHOLD or any(signal.startswith("foreign_country") for signal in negative_signals):
        reason = "source points to a different company or foreign context"
        classification = "WRONG_COMPANY"
    else:
        reason = "not enough trusted identity evidence"
        classification = "INSUFFICIENT_EVIDENCE"

    return build_validation_result(classification, score, reason, matched_signals, negative_signals)
