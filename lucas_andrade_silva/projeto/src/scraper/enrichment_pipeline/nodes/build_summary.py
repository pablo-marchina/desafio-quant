"""Build deterministic evidence summaries from validated sources only."""

from __future__ import annotations

import re

from .. import config
from typing import Any

from ..state import EnrichmentState

AI_TERMS = ("inteligencia artificial", " ia ", " ai ", "machine learning", "llm", "chatbot", "agente", "computer vision", "analytics")
BR_TERMS = ("brasil", "brasileira", "brasileiro", "sao paulo", "rio de janeiro", "cnpj", "ltda", "startup brasileira")


def _plain(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _sentences_with_terms(texts: dict[str, str], terms: tuple[str, ...], limit: int = 5) -> list[str]:
    matches: list[str] = []
    for url, text in texts.items():
        for sentence in re.split(r"(?<=[.!?])\s+", text):
            normalized = f" {sentence.casefold()} "
            if any(term in normalized for term in terms):
                matches.append(f"{url}: {_plain(sentence)[:300]}")
                if len(matches) >= limit:
                    return matches
    return matches


def _strong_sources(urls: list[str]) -> list[str]:
    return [url for url in urls if any(domain in url.casefold() for domain in config.STRONG_SOURCE_DOMAINS)]


def build_evidence_summary(state: EnrichmentState) -> str:
    candidate = state.get("candidate", {})
    cnpj = state.get("cnpj_data", {})
    raw_texts = state.get("web_context", {}) or state.get("raw_texts", {})
    urls = state.get("validated_urls") or state.get("evidence_urls", [])
    ai_signals = _sentences_with_terms(raw_texts, AI_TERMS)
    br_mentions = _sentences_with_terms(raw_texts, BR_TERMS)
    inconsistencies: list[str] = []
    if cnpj and cnpj.get("ativa") is False:
        inconsistencies.append(f"CNPJ nao ativo: {cnpj.get('situacao')}")
    if candidate.get("company_name") and cnpj.get("razao_social"):
        candidate_name = str(candidate["company_name"]).split()[0].casefold()
        if candidate_name and candidate_name not in str(cnpj["razao_social"]).casefold():
            inconsistencies.append("Nome do candidato nao aparece claramente na razao social.")

    web_lines = [f"{url}: {_plain(text)[:500]}" for url, text in list(raw_texts.items())[:4]]
    sections = [
        "Candidato:",
        f"- nome: {candidate.get('company_name') or candidate.get('nome') or 'nao informado'}",
        f"- nome_normalizado: {state.get('normalized_company_name') or 'nao informado'}",
        f"- fonte_original: {candidate.get('source_url') or candidate.get('website') or candidate.get('website_url') or 'nao informada'}",
        "",
        "CNPJ:",
        f"- razao_social: {cnpj.get('razao_social') or 'nao encontrado'}",
        f"- situacao: {cnpj.get('situacao') or 'nao encontrado'}",
        f"- municipio_uf: {cnpj.get('municipio') or 'nao encontrado'}/{cnpj.get('uf') or 'nao encontrado'}",
        f"- cnae: {cnpj.get('cnae') or 'nao encontrado'} {cnpj.get('cnae_descricao') or ''}".strip(),
        f"- data_inicio_atividade: {cnpj.get('data_inicio_atividade') or 'nao encontrado'}",
        f"- capital_social: {cnpj.get('capital_social') or 'nao encontrado'}",
        "",
        "Fontes validadas:",
        *([f"- {url}" for url in urls] or ["- nenhuma fonte validada encontrada"]),
        "",
        "Web validada:",
        *(web_lines or ["- nenhuma evidencia web validada encontrada"]),
        "",
        "Sinais IA:",
        *(ai_signals or ["- nenhum sinal verificavel encontrado"]),
        "",
        "Mencoes BR:",
        *(br_mentions or ["- nenhuma mencao verificavel encontrada"]),
        "",
        "Fontes fortes:",
        *(_strong_sources(urls) or ["- nenhuma fonte forte encontrada"]),
        "",
        "Inconsistencias:",
        *(inconsistencies or ["- nenhuma inconsistencia verificavel encontrada"]),
    ]
    text = "\n".join(sections)
    return text[: config.MAX_SUMMARY_TOKENS * 4]


def build_summary_node(state: EnrichmentState) -> dict[str, Any]:
    if state.get("run_deep_enrichment") is False or ("validated_url" in state and not state.get("validated_url")):
        return {"evidence_summary": state.get("evidence_summary") or ""}
    return {"evidence_summary": build_evidence_summary(state)}
