"""Fallback de dados cadastrais usando as páginas públicas do cnpj.biz."""

from __future__ import annotations

import logging
import os
import re
import time
import unicodedata
from decimal import Decimal, InvalidOperation
from typing import Any, Callable
from urllib.parse import quote, urljoin

import requests
from bs4 import BeautifulSoup

from .. import config

LOGGER = logging.getLogger(__name__)
CNPJ_BIZ_BASE_URL = "https://cnpj.biz"
CNPJ_PATTERN = re.compile(r"(?<!\d)(\d{14})(?!\d)")
CNAE_PATTERN = re.compile(
    r"(\d{2}\.\d{2}-\d-\d{2})\s*-\s*([^\n]+)"
)

STATE_CODES = {
    "acre": "AC",
    "alagoas": "AL",
    "amapa": "AP",
    "amazonas": "AM",
    "bahia": "BA",
    "ceara": "CE",
    "distrito federal": "DF",
    "espirito santo": "ES",
    "goias": "GO",
    "maranhao": "MA",
    "mato grosso": "MT",
    "mato grosso do sul": "MS",
    "minas gerais": "MG",
    "para": "PA",
    "paraiba": "PB",
    "parana": "PR",
    "pernambuco": "PE",
    "piaui": "PI",
    "rio de janeiro": "RJ",
    "rio grande do norte": "RN",
    "rio grande do sul": "RS",
    "rondonia": "RO",
    "roraima": "RR",
    "santa catarina": "SC",
    "sao paulo": "SP",
    "sergipe": "SE",
    "tocantins": "TO",
}


def _normalized(value: Any) -> str:
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = "".join(
        character
        for character in text
        if not unicodedata.combining(character)
    )
    return re.sub(r"\s+", " ", text).strip().casefold()


def _clean(value: Any) -> str | None:
    text = re.sub(r"\s+", " ", str(value or "")).strip(" \t\r\n:-")
    return text or None


def _lines(soup: BeautifulSoup) -> list[str]:
    return [
        text
        for value in soup.stripped_strings
        if (text := _clean(value))
    ]


def _labeled_value(
    lines: list[str], *labels: str, prefix: bool = False
) -> str | None:
    normalized_labels = [_normalized(label) for label in labels]
    for index, line in enumerate(lines):
        normalized_line = _normalized(line)
        for label in normalized_labels:
            matches = (
                normalized_line.startswith(label)
                if prefix
                else normalized_line == label
                or normalized_line.startswith(f"{label}:")
            )
            if not matches:
                continue
            inline = _clean(re.sub(r"^[^:]+:", "", line, count=1))
            if ":" in line and inline:
                return inline
            if index + 1 < len(lines):
                return _clean(lines[index + 1])
    return None


def _section_text(
    lines: list[str], start_terms: tuple[str, ...], end_terms: tuple[str, ...]
) -> str:
    start = None
    for index, line in enumerate(lines):
        if any(term in _normalized(line) for term in start_terms):
            start = index + 1
            break
    if start is None:
        return ""
    end = len(lines)
    for index in range(start, len(lines)):
        if any(term in _normalized(lines[index]) for term in end_terms):
            end = index
            break
    return "\n".join(lines[start:end])


def _state_code(value: str | None) -> str | None:
    text = _clean(value)
    if not text:
        return None
    if re.fullmatch(r"[A-Za-z]{2}", text):
        return text.upper()
    return STATE_CODES.get(_normalized(text))


def _money_value(value: str | None) -> str | None:
    if not value:
        return None
    cleaned = re.sub(r"[^\d,.\-]", "", value)
    if not cleaned:
        return None
    if "," in cleaned:
        cleaned = cleaned.replace(".", "").replace(",", ".")
    try:
        return f"{Decimal(cleaned):.2f}"
    except InvalidOperation:
        return None


def extract_search_results(html: str) -> list[tuple[str, str]]:
    """Extrai URLs e CNPJs da lista de resultados."""

    soup = BeautifulSoup(html, "html.parser")
    results: list[tuple[str, str]] = []
    seen: set[str] = set()
    for anchor in soup.select('ul[role="list"] > li > a[href]'):
        url = urljoin(CNPJ_BIZ_BASE_URL, str(anchor.get("href") or ""))
        match = CNPJ_PATTERN.search(url)
        if not match or match.group(1) in seen:
            continue
        cnpj = match.group(1)
        seen.add(cnpj)
        results.append((f"{CNPJ_BIZ_BASE_URL}/{cnpj}", cnpj))
    return results


def extract_company_details(
    html: str, *, cnpj: str, source_url: str
) -> dict[str, Any]:
    """Extrai os campos cadastrais de uma página de detalhes."""

    soup = BeautifulSoup(html, "html.parser")
    lines = _lines(soup)
    page_text = "\n".join(lines)
    clean_cnpj = (
        (CNPJ_PATTERN.search(page_text) or CNPJ_PATTERN.search(cnpj))
    )
    cnpj_value = clean_cnpj.group(1) if clean_cnpj else re.sub(r"\D", "", cnpj)
    opening_date = _labeled_value(lines, "Data da Abertura")
    main_cnae_match = re.search(
        rf"Principal\s*:\s*{CNAE_PATTERN.pattern}",
        page_text,
        flags=re.IGNORECASE,
    )
    main_cnae = (
        f"{main_cnae_match.group(1)} - {_clean(main_cnae_match.group(2))}"
        if main_cnae_match
        else None
    )

    secondary_text = _section_text(
        lines,
        ("secundaria",),
        ("quadro de socios", "socios e administradores", "contato"),
    )
    secondary_cnaes = [
        {"codigo": match.group(1), "descricao": _clean(match.group(2))}
        for match in CNAE_PATTERN.finditer(secondary_text)
    ]

    partners_text = _section_text(
        lines,
        ("quadro de socios", "socios e administradores"),
        ("contato", "localizacao", "atividades"),
    )
    partner_lines = partners_text.splitlines()
    partners: list[dict[str, str | None]] = []
    current_name: str | None = None
    for line in partner_lines:
        normalized = _normalized(line)
        if normalized.startswith("nome:"):
            current_name = _clean(line.split(":", 1)[1])
        elif normalized.startswith(
            ("qualificacao:", "cargo:")
        ) and current_name:
            partners.append(
                {
                    "nome": current_name,
                    "cargo": _clean(line.split(":", 1)[1]),
                }
            )
            current_name = None
    if current_name:
        partners.append({"nome": current_name, "cargo": None})

    municipality = _labeled_value(lines, "Município")
    state = _state_code(_labeled_value(lines, "Estado"))
    situation = _labeled_value(lines, "Situação", "Situação Cadastral")
    company = {
        "cnpj": cnpj_value if len(cnpj_value) == 14 else None,
        "razao_social": _labeled_value(lines, "Razão Social"),
        "nome_fantasia": _labeled_value(lines, "Nome Fantasia"),
        "data_abertura": opening_date,
        "founding_year": (
            (match.group(1) if (match := re.search(r"(\d{4})", opening_date or "")) else None)
        ),
        "municipio": municipality,
        "estado": state,
        "cep": _labeled_value(lines, "CEP"),
        "logradouro": _labeled_value(lines, "Logradouro"),
        "bairro": _labeled_value(lines, "Bairro"),
        "natureza_juridica": _labeled_value(lines, "Natureza Jurídica"),
        "porte": _labeled_value(lines, "Porte"),
        "capital_social": _money_value(
            _labeled_value(lines, "Capital Social")
        ),
        "situacao_cadastral": situation,
        "inscricao_estadual": _labeled_value(
            lines, "Inscrição Estadual", prefix=True
        ),
        "cnae_principal": main_cnae,
        "cnae_secundarias": secondary_cnaes or None,
        "socios": partners or None,
        "source_url": source_url,
    }
    return company


def catalog_payload(company: dict[str, Any]) -> dict[str, Any]:
    """Mapeia os dados extraídos para startup_ai_radar_catalog."""

    municipality = company.get("municipio")
    state = company.get("estado")
    location = (
        ", ".join(value for value in (municipality, state) if value) or None
    )
    partners = list(company.get("socios") or [])
    partner_names = [
        str(partner.get("nome"))
        for partner in partners
        if partner.get("nome")
    ]
    capital = company.get("capital_social")
    description_parts = []
    if capital:
        description_parts.append(f"Capital Social: R$ {capital}")
    if partner_names:
        description_parts.append(f"Sócios: {', '.join(partner_names)}")
    situation = _clean(company.get("situacao_cadastral"))
    cnpj = str(company.get("cnpj") or "")
    company_name = (
        _clean(company.get("nome_fantasia"))
        or _clean(company.get("razao_social"))
    )
    return {
        "candidate_id": cnpj,
        "company_name": company_name,
        "location": location,
        "founding_year": company.get("founding_year"),
        "ai_technology_focus": company.get("cnae_principal"),
        "source_url": company.get("source_url"),
        "validation_status": situation,
        "enrichment_status": "scraped",
        "is_active": _normalized(situation) == "ativa",
        "description": " | ".join(description_parts) or None,
        "cnpj": cnpj,
        "razao_social": company.get("razao_social"),
        "nome_fantasia": company.get("nome_fantasia"),
        "municipio": municipality,
        "estado": state,
        "cep": company.get("cep"),
        "logradouro": company.get("logradouro"),
        "bairro": company.get("bairro"),
        "natureza_juridica": company.get("natureza_juridica"),
        "porte": company.get("porte"),
        "capital_social": capital,
        "situacao_cadastral": situation,
        "data_abertura": company.get("data_abertura"),
        "inscricao_estadual": company.get("inscricao_estadual"),
        "cnae_principal": company.get("cnae_principal"),
        "cnae_secundarias": company.get("cnae_secundarias"),
        "socios": company.get("socios"),
    }


def _supabase_client():
    from supabase import create_client

    return create_client(config.supabase_url(), config.supabase_key())


def _upsert_company(client: Any, payload: dict[str, Any]) -> str:
    table = client.table(config.ENRICHMENT_RESULTS_TABLE)
    existing = (
        table.select("candidate_id")
        .eq("candidate_id", payload["candidate_id"])
        .limit(1)
        .execute()
    )
    status = "atualizado" if list(existing.data or []) else "inserido"
    (
        client.table(config.ENRICHMENT_RESULTS_TABLE)
        .upsert(payload, on_conflict="candidate_id")
        .execute()
    )
    return status


def scrape_and_upsert(
    startup_name: str,
    *,
    session: requests.Session | None = None,
    supabase_client: Any | None = None,
    sleep_fn: Callable[[float], None] = time.sleep,
) -> list[dict[str, Any]]:
    """Busca todas as empresas, extrai os detalhes e faz UPSERT no catálogo."""

    http = session or requests.Session()
    headers = {
        "User-Agent": config.CNPJ_USER_AGENT,
        "Accept": "text/html,application/xhtml+xml",
        "Accept-Language": "pt-BR,pt;q=0.9",
    }
    search_url = (
        f"{CNPJ_BIZ_BASE_URL}/procura/"
        f"{quote(startup_name.strip(), safe='')}"
    )
    response = http.get(
        search_url,
        headers=headers,
        timeout=config.HTTP_TIMEOUT_SECONDS,
    )
    response.raise_for_status()
    results = extract_search_results(response.text)
    if not results:
        return []

    client = supabase_client
    if client is None and os.getenv("SUPABASE_URL") and os.getenv("SUPABASE_KEY"):
        client = _supabase_client()
    elif client is None:
        LOGGER.info(
            "[CNPJ.biz] SUPABASE_URL/SUPABASE_KEY ausentes; "
            "executando somente coleta sem upsert direto."
        )

    companies: list[dict[str, Any]] = []
    for url, cnpj in results[: config.CNPJ_BIZ_MAX_RESULTS]:
        sleep_fn(1)
        processed_name = startup_name
        try:
            detail_response = http.get(
                url,
                headers=headers,
                timeout=config.HTTP_TIMEOUT_SECONDS,
            )
            detail_response.raise_for_status()
            company = extract_company_details(
                detail_response.text, cnpj=cnpj, source_url=url
            )
            if client is not None:
                payload = catalog_payload(company)
                processed_name = str(payload.get("company_name") or startup_name)
                status = _upsert_company(client, payload)
                LOGGER.info(
                    "[CNPJ.biz] %s | %s | %s",
                    payload["company_name"],
                    cnpj,
                    status,
                )
            else:
                processed_name = str(
                    company.get("nome_fantasia")
                    or company.get("razao_social")
                    or startup_name
                )
                LOGGER.info(
                    "[CNPJ.biz] %s | %s | coletado sem upsert direto",
                    processed_name,
                    cnpj,
                )
            companies.append(company)
        except Exception as error:
            LOGGER.exception(
                "[CNPJ.biz] %s | %s | erro: %s",
                processed_name,
                cnpj,
                error,
            )
    return companies


def normalized_company_data(company: dict[str, Any]) -> dict[str, Any]:
    """Converte o detalhe do cnpj.biz para o contrato usado pela interface."""

    main_cnae = str(company.get("cnae_principal") or "")
    code, _, description = main_cnae.partition(" - ")
    return {
        "cnpj": company.get("cnpj"),
        "razao_social": company.get("razao_social"),
        "nome_fantasia": company.get("nome_fantasia"),
        "situacao": company.get("situacao_cadastral"),
        "ativa": _normalized(company.get("situacao_cadastral")) == "ativa",
        "municipio": company.get("municipio"),
        "uf": company.get("estado"),
        "cnae": code or None,
        "cnae_descricao": description or None,
        "cnaes_secundarios": company.get("cnae_secundarias") or [],
        "data_inicio_atividade": company.get("data_abertura"),
        "capital_social": company.get("capital_social"),
        "porte": company.get("porte"),
        "natureza_juridica": company.get("natureza_juridica"),
        "endereco": {
            "logradouro": company.get("logradouro"),
            "bairro": company.get("bairro"),
            "municipio": company.get("municipio"),
            "uf": company.get("estado"),
            "cep": company.get("cep"),
        },
        "contato": {},
        "socios": [
            {
                "nome": partner.get("nome"),
                "qualificacao": partner.get("cargo"),
            }
            for partner in company.get("socios") or []
        ],
        "inscricao_estadual": company.get("inscricao_estadual"),
        "setor_inferido": description or None,
        "usa_ia_potencialmente": None,
        "classificacao_ia": "NON_AI",
        "justificativa_ia": None,
        "fontes": ["cnpj.biz"],
        "raw_data": company,
    }
