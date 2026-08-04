from __future__ import annotations

import re
import unicodedata
from typing import Any

from .validator import normalize_company_name

AI_TERMS = (
    " ia ", " inteligencia artificial", " machine learning", " llm", " agentes", " automacao inteligente",
    " nlp", " computer vision", " visao computacional", " chatbot", " data science", " analytics",
    " modelos preditivos", " recomendacao", " rpa", " hiperautomacao",
)
AI_RELATED = ("data", "dados", "analytics", "automacao", "software", "saas", "cyber", "antifraude", "algoritmo", "robot")
ROLE_TERMS = ("ceo", "cto", "coo", "cfo", "founder", "officer", "partner", "investidor", "diretor", "diretora", "executivo", "executiva", "presidente", "gerente")
VERB_TERMS = (
    " possuem ", " possui ", " oferece ", " oferecem ", " ajuda ", " ajudam ", " permite ", " anunciou ",
    " anuncia ", " recebeu ", " recebe ", " captou ", " quer ", " busca ", " prepara ", " assume ", " nomeia ",
    " construir ", " analisar ", " reduzir ", " aumentar ", " transformar ", " utilizar ", " utilizam ",
)
STRONG_SOURCES = {"cubo", "liga", "darwin"}


def _plain(value: str | None) -> str:
    normalized = unicodedata.normalize("NFKD", value or "")
    return "".join(c for c in normalized if not unicodedata.combining(c)).casefold()


def _source(record: dict[str, Any]) -> str:
    value = _plain(str(record.get("source_name") or ""))
    url = _plain(str(record.get("source_url") or ""))
    for source in ("cubo", "liga", "darwin"):
        if source in value or source in url:
            return source
    return value


def clean_company_name(name: str | None) -> str:
    value = re.sub(r"\s+", " ", name or "").strip()
    match = re.match(r"^(A|O|As|Os)\s+(.+)$", value)
    if not match:
        return value
    remainder = match.group(2).strip()
    words = remainder.split()
    if 1 <= len(words) <= 4 and remainder[:1].isupper() and not re.search(r"[.!?;:]", remainder):
        plain = f" {_plain(remainder)} "
        if not any(term in plain for term in VERB_TERMS):
            return remainder
    return value


def is_text_fragment(record: dict[str, Any]) -> bool:
    name = str(record.get("company_name") or "").strip()
    plain = f" {_plain(name)} "
    if not name:
        return True
    if re.search(r"\.\s*(?:A|O|Nessa)$", name, re.I) or re.search(r"\b(?:AI-first|Tel Aviv|Meta)\.\s*A$", name, re.I):
        return True
    if any(fragment in plain for fragment in (" hoje ja possuem ", " proximo cliente ", " capital proprio ", " multas e outras ")):
        return True
    if name.endswith(".") or len(name.split()) > 8:
        return True
    if name[:1].islower() and len(name.split()) >= 3:
        return True
    if any(term in plain for term in VERB_TERMS) and len(name.split()) >= 3:
        return True
    if re.match(r"^(A|O|As|Os)\s+", name) and clean_company_name(name) == name and len(name.split()) >= 4:
        return True
    if re.search(r"\.(?:\s+|$)", name) and len(name.split()) >= 3:
        return True
    return False


def is_person_or_role(record: dict[str, Any]) -> bool:
    name = str(record.get("company_name") or "").strip()
    plain_name = f" {_plain(name)} "
    if any(re.search(rf"\b{re.escape(role)}\b", plain_name) for role in ROLE_TERMS):
        return True
    words = re.findall(r"[A-Za-zÀ-ÿ'-]+", name)
    looks_like_full_name = 2 <= len(words) <= 4 and all(word[:1].isupper() for word in words)
    evidence = _plain(str(record.get("evidence_text") or ""))
    appointment = re.search(r"\b(?:assume|nomeia|contrata|executivo|executiva|ex-ceo|fundador|diretor|presidente)\b", evidence)
    company_signal = re.search(r"\b(?:startup|empresa|plataforma|fintech|healthtech|software)\b", evidence)
    return bool(looks_like_full_name and appointment and not company_signal)


def is_foreign_without_brazil(record: dict[str, Any]) -> bool:
    evidence = f" {_plain(str(record.get('evidence_text') or ''))} "
    foreign = re.search(
        r"\b(?:fundad[ao]|sediad[ao]|nasceu|com sede)\s+(?:em|no|na|nos|nas)\s+"
        r"(?:eua|estados unidos|europa|tel aviv|israel|belgica|mexico|argentina|chile|colombia|china|india|reino unido|franca|alemanha)\b",
        evidence,
    )
    brazil = re.search(r"\b(?:brasil|brasileir[ao]s?|cnpj|sede no brasil|opera(?:cao|ções|coes)? no brasil|clientes no brasil)\b", evidence)
    return bool(foreign and not brazil)


def is_confirmed_non_ai(record: dict[str, Any]) -> bool:
    if record.get("ai_classification") != "NON_AI" or record.get("uses_ai_potentially") is not False:
        return False
    if _source(record) in STRONG_SOURCES:
        return False
    evidence = f" {_plain(str(record.get('evidence_text') or ''))} "
    if any(term in evidence for term in AI_TERMS) or any(term in evidence for term in AI_RELATED):
        return False
    clearly_unrelated = re.search(r"\b(?:restaurante|rede de lojas fisicas|mineracao tradicional|combustivel|incorporadora imobiliaria|producao de alimentos|varejista tradicional)\b", evidence)
    return bool(clearly_unrelated and len(evidence) >= 250)


def should_reject_candidate(record: dict[str, Any]) -> str | None:
    if is_person_or_role(record):
        return "person_or_role"
    if is_text_fragment(record):
        return "text_fragment"
    if is_foreign_without_brazil(record):
        return "foreign_without_brazil_evidence"
    if is_confirmed_non_ai(record):
        return "non_ai_confirmed"
    return None


def update_validation_record(record: dict[str, Any]) -> dict[str, Any]:
    updated = dict(record)
    cleaned = clean_company_name(str(record.get("company_name") or ""))
    updated["name_corrected"] = cleaned != record.get("company_name")
    updated["company_name"] = cleaned
    updated["normalized_name"] = normalize_company_name(cleaned)
    reason = should_reject_candidate(updated)
    if reason:
        updated["validation_status"] = "REJECTED"
        updated["rejection_reason"] = reason
        return updated
    can_stay_approved = (
        record.get("validation_status") == "APPROVED"
        and record.get("is_valid_company") is True
        and record.get("is_brazilian") is True
        and record.get("is_startup") is True
        and (record.get("uses_ai_potentially") is True or record.get("ai_classification") in {"AI_NATIVE", "AI_ENABLED"})
    )
    updated["validation_status"] = "APPROVED" if can_stay_approved else "REVIEW"
    if updated["validation_status"] != "REJECTED":
        updated["rejection_reason"] = None
    return updated
