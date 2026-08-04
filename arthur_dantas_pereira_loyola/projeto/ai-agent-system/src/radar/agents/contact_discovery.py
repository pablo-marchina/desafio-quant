from __future__ import annotations

import re
import time
from datetime import datetime, timezone
from typing import Any

from radar.agents.contact_tracker import get_contact_tracker
from radar.database.repository import get_all_source_documents
from radar.graph.state import RadarState
from radar.schemas import SearchPlan
from radar.schemas.contact import CompanyContact, ContactEntry, ContactSource
from radar.scraping.provider_factory import build_web_collector

EMAIL_PATTERN = re.compile(
    r"[a-zA-Z0-9.!#$%&'*+/=?^_`{|}~-]+@[a-zA-Z0-9-]+(?:\.[a-zA-Z0-9-]+)+"
)
PHONE_PATTERNS = [
    re.compile(r"\(\d{2}\)\s?\d{4,5}-?\d{4}"),
    re.compile(r"\+\d{1,3}\s?\(\d{2}\)\s?\d{4,5}-?\d{4}"),
    re.compile(r"\d{4,5}-\d{4}"),
]
LINKEDIN_PATTERN = re.compile(
    r"(?:https?://)?(?:www\.)?linkedin\.com/(?:in|company)/[a-zA-Z0-9_-]+/?",
    re.IGNORECASE,
)
ADDRESS_PATTERNS = [
    re.compile(
        r"(?:Rua|Av\.|Avenida|Rodovia|Estrada|Alameda|Travessa|Praca)"
        r"\s[\w\s]+\s,\s?\d+\s?-?\s?[\w\s]*[,\.]?\s?[A-Z]{2}?"
    ),
    re.compile(
        r"(?:Rua|Av\.|Avenida)[^,]+,\d+[^,]+,[A-Z]{2}"
    ),
]


def _contact_queries(startup_name: str) -> list[str]:
    base = startup_name.strip()
    return [
        f"{base} email contato",
        f"{base} telefone",
        f"{base} linkedin",
        f"{base} endereco",
        f"{base} founding team",
        f"{base} quem somos",
    ]


def _build_contact_seed_plan(startup_name: str) -> SearchPlan:
    queries = _contact_queries(startup_name)
    return SearchPlan(
        query=startup_name,
        keywords=queries,
        source_types=["official_site", "other"],
        collection_plan=[
            f"Buscando contatos para {startup_name}",
            "Extrair email, telefone, LinkedIn e endereco.",
        ],
    )


def _extract_from_text(
    text: str,
) -> tuple[list[str], list[str], list[str], list[str]]:
    emails = list(set(m.lower() for m in EMAIL_PATTERN.findall(text)))
    phones: list[str] = []
    for pattern in PHONE_PATTERNS:
        phones.extend(pattern.findall(text))
    phones = list(set(p.strip() for p in phones if p.strip()))
    linkedin_urls = list(set(LINKEDIN_PATTERN.findall(text)))
    addrs: list[str] = []
    for pattern in ADDRESS_PATTERNS:
        addrs.extend(m.group().strip() for m in pattern.finditer(text))
    addrs = list(set(addrs))
    return emails, phones, linkedin_urls, addrs


def _extract_from_sources(
    sources: list,
) -> tuple[dict[str, list[str]], dict[str, list[str]], dict[str, list[str]], dict[str, list[str]], list[str]]:
    all_emails: dict[str, list[str]] = {}
    all_phones: dict[str, list[str]] = {}
    all_linkedin: dict[str, list[str]] = {}
    all_addresses: dict[str, list[str]] = {}
    raw_snippets: list[str] = []

    for doc in sources:
        text = doc.get("text") if isinstance(doc, dict) else getattr(doc, "text", "")
        url = doc.get("url") if isinstance(doc, dict) else str(getattr(doc, "url", ""))
        if not text or not text.strip():
            continue
        raw_snippets.append(text[:500])
        emails, phones, linkedin_urls, addrs = _extract_from_text(text)
        for email in emails:
            all_emails.setdefault(email, []).append(url)
        for phone in phones:
            all_phones.setdefault(phone, []).append(url)
        for li in linkedin_urls:
            all_linkedin.setdefault(li, []).append(url)
        for addr in addrs:
            all_addresses.setdefault(addr, []).append(url)

    return all_emails, all_phones, all_linkedin, all_addresses, raw_snippets


def discover_contacts(
    startup_id: str,
    startup_name: str,
    domain: str | None = None,
) -> CompanyContact:
    tracker = get_contact_tracker()

    if tracker:
        tracker.start("preparing_queries", f"Preparando queries para {startup_name}")
    plan = _build_contact_seed_plan(startup_name)
    plan.keywords = _contact_queries(startup_name)

    if tracker:
        tracker.complete("preparing_queries", f"{len(plan.keywords)} queries preparadas")
    _fixture_delay()
    if tracker:
        tracker.start("searching_web", "Buscando paginas com informacoes de contato...")

    collector = build_web_collector()
    if hasattr(collector, "collect_with_errors"):
        sources, _ = collector.collect_with_errors(plan)
    else:
        sources = collector.collect(plan)

    if tracker:
        tracker.complete("searching_web", f"{len(sources)} pagina(s) encontrada(s)")
    _fixture_delay()
    if tracker:
        tracker.start("extracting_contacts", "Extraindo emails, telefones, LinkedIn...")

    all_emails, all_phones, all_linkedin, all_addresses, raw_snippets = _extract_from_sources(sources)

    email_count = len(all_emails)
    phone_count = len(all_phones)
    linkedin_count = len(all_linkedin)
    addr_count = len(all_addresses)

    if tracker:
        tracker.complete(
            "extracting_contacts",
            f"{email_count} email(s), {phone_count} telefone(s), {linkedin_count} LinkedIn, {addr_count} endereco(s)",
        )
    _fixture_delay()
    if tracker:
        tracker.start("fallback_sources", "Verificando fontes existentes no banco...")

    if not all_emails and not all_phones and not all_linkedin:
        existing_sources = get_all_source_documents()
        fb_emails, fb_phones, fb_linkedin, fb_addresses, fb_snippets = _extract_from_sources(existing_sources)
        all_emails.update(fb_emails)
        all_phones.update(fb_phones)
        all_linkedin.update(fb_linkedin)
        all_addresses.update(fb_addresses)
        raw_snippets.extend(fb_snippets)

    if tracker:
        tracker.complete(
            "fallback_sources",
            f"Total: {len(all_emails)} email(s), {len(all_phones)} telefone(s)",
        )
    _fixture_delay()
    if tracker:
        tracker.start("cross_referencing", "Cruzando informacoes entre fontes...")

    entry_count = max(len(all_emails), len(all_phones), len(all_linkedin), len(all_addresses), 1)

    if tracker:
        tracker.complete("cross_referencing", f"{entry_count} entradas consolidadas")
    _fixture_delay()
    if tracker:
        tracker.start("saving_result", "Salvando dados de contato...")

    result = CompanyContact(
        startup_id=startup_id,
        startup_name=startup_name,
        emails=[
            ContactEntry(
                value=email,
                confidence=_cross_ref_confidence(len(urls)),
                sources=[ContactSource(source_url=u, found_at=email) for u in urls],
            )
            for email, urls in sorted(all_emails.items())
        ],
        phones=[
            ContactEntry(
                value=phone,
                confidence=_cross_ref_confidence(len(urls)),
                sources=[ContactSource(source_url=u, found_at=phone) for u in urls],
            )
            for phone, urls in sorted(all_phones.items())
        ],
        linkedin_urls=[
            ContactEntry(
                value=li,
                confidence=_cross_ref_confidence(len(urls)),
                sources=[ContactSource(source_url=u, found_at=li) for u in urls],
            )
            for li, urls in sorted(all_linkedin.items())
        ],
        addresses=[
            ContactEntry(
                value=addr,
                confidence=_cross_ref_confidence(len(urls)),
                sources=[ContactSource(source_url=u, found_at=addr) for u in urls],
            )
            for addr, urls in sorted(all_addresses.items())
        ],
        raw_text_snippets=raw_snippets[:5],
        collected_at=datetime.now(timezone.utc).isoformat(),
    )

    if tracker:
        tracker.complete("saving_result", "Contatos salvos com sucesso")

    return result


def _fixture_delay() -> None:
    from radar.settings import get_settings
    if get_settings().search_provider == "fixture":
        time.sleep(0.5)


def _cross_ref_confidence(source_count: int) -> float:
    if source_count >= 3:
        return 0.9
    if source_count == 2:
        return 0.7
    if source_count == 1:
        return 0.5
    return 0.1


def discover_contacts_from_state(state: RadarState) -> dict[str, Any]:
    query = state.get("query", "startup")
    startup_id = state.get("startup_id", query)
    result = discover_contacts(startup_id=startup_id, startup_name=query)
    return result.model_dump()
