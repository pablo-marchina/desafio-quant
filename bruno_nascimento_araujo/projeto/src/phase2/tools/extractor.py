"""Modulo 2 - Extracao multi-camada de conteudo de startups.

Estrategia em 3 niveis (para no primeiro que retornar conteudo util):
  1. JSON-LD / OpenGraph via extruct (metadados estruturados)
  2. Texto principal via trafilatura (narrativa do site)
  3. SPA fallback via Crawl4AI (renderizacao JS)

Retorna ExtractedStartupData (Pydantic), JSON-serializavel para LangGraph.
"""
from __future__ import annotations

import re
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from ...http_client import make_deep_client, _UA_POOL
from ...logging_conf import get_logger

logger = get_logger("phase2.extractor")

# --- Padroes de uso_cases extraidos de texto via regex ---
_USE_CASE_PATTERNS = [
    re.compile(r"utilizado[s]?\s+para\s+([^.!?]{10,120})", re.IGNORECASE),
    re.compile(r"aplicad[ao][s]?\s+(?:em|a)\s+([^.!?]{10,120})", re.IGNORECASE),
    re.compile(r"permite\s+que\s+([^.!?]{10,120})", re.IGNORECASE),
    re.compile(r"soluc[aã]o\s+para\s+([^.!?]{10,120})", re.IGNORECASE),
    re.compile(r"usado[s]?\s+para\s+([^.!?]{10,120})", re.IGNORECASE),
]


class ExtractedStartupData(BaseModel):
    """Payload estruturado de uma startup apos extracao profunda."""

    url: str
    source_url: str
    core_business: str | None = None
    use_cases: list[str] = Field(default_factory=list)
    tech_stack_raw: list[str] = Field(default_factory=list)
    founders_names: list[str] = Field(default_factory=list)
    funding_rounds: list[str] = Field(default_factory=list)
    raw_text: str | None = None
    has_ai_signals: bool = False
    ai_signal_score: float = 0.0
    extraction_level: str = "none"  # 'json_ld' | 'main_text' | 'spa' | 'none'
    collected_at: datetime = Field(default_factory=datetime.utcnow)


def _coerce_str_list(val: Any) -> list[str]:
    """Converte string ou lista de strings/dicts em list[str]."""
    if not val:
        return []
    if isinstance(val, str):
        return [val] if val.strip() else []
    if isinstance(val, list):
        out = []
        for item in val:
            if isinstance(item, str) and item.strip():
                out.append(item.strip())
            elif isinstance(item, dict):
                name = item.get("name") or item.get("title") or item.get("@id")
                if name and isinstance(name, str):
                    out.append(name.strip())
        return out
    return []


def _extract_use_cases_from_text(text: str) -> list[str]:
    """Extrai frases de caso de uso via regex sobre texto livre."""
    cases: list[str] = []
    for pattern in _USE_CASE_PATTERNS:
        for m in pattern.finditer(text):
            phrase = m.group(1).strip().rstrip(".,;")
            if phrase and len(phrase) > 10:
                cases.append(phrase)
    return cases[:10]  # limita para evitar ruido


def _parse_json_ld_items(items: list[dict]) -> dict:
    """Mapeamento defensivo com hierarquia explicita de fallback.

    Nunca inventa dados: cada campo so e preenchido se o valor existir
    explicitamente no JSON-LD. Avanca para Nivel 2 se necessario.
    """
    result: dict[str, Any] = {
        "core_business": None,
        "use_cases": [],
        "tech_stack_raw": [],
        "founders_names": [],
        "funding_rounds": [],
    }
    for item in items:
        if not isinstance(item, dict):
            continue
        # core_business: description → abstract → about.description
        if not result["core_business"]:
            desc = (
                item.get("description")
                or item.get("abstract")
                or (item.get("about") or {}).get("description")
            )
            if isinstance(desc, str) and desc.strip():
                result["core_business"] = desc.strip()

        # use_cases: applicationCategory (se lista/str)
        app_cat = item.get("applicationCategory")
        if app_cat:
            result["use_cases"].extend(_coerce_str_list(app_cat))
        # Complementa com regex sobre description se nao houver applicationCategory
        if not result["use_cases"] and result["core_business"]:
            result["use_cases"].extend(_extract_use_cases_from_text(result["core_business"]))

        # tech_stack_raw: programmingLanguage | softwareRequirements
        for key in ("programmingLanguage", "softwareRequirements", "runtimePlatform"):
            val = item.get(key)
            if val:
                result["tech_stack_raw"].extend(_coerce_str_list(val))

        # founders_names: author[].name | founder[].name
        for key in ("author", "founder"):
            persons = item.get(key)
            if isinstance(persons, list):
                for p in persons:
                    if isinstance(p, dict) and isinstance(p.get("name"), str):
                        result["founders_names"].append(p["name"].strip())
            elif isinstance(persons, dict) and isinstance(persons.get("name"), str):
                result["founders_names"].append(persons["name"].strip())
            elif isinstance(persons, str) and persons.strip():
                result["founders_names"].append(persons.strip())

        # funding_rounds: funding | offers[].price
        funding = item.get("funding")
        if funding:
            result["funding_rounds"].append(str(funding))
        offers = item.get("offers")
        if offers:
            for offer in ([offers] if isinstance(offers, dict) else offers):
                if not isinstance(offer, dict):
                    continue
                price = offer.get("price")
                currency = offer.get("priceCurrency", "")
                if price is not None:
                    result["funding_rounds"].append(f"{currency} {price}".strip())

    # Deduplicacao mantendo ordem
    for key in ("use_cases", "tech_stack_raw", "founders_names", "funding_rounds"):
        seen: set[str] = set()
        deduped = []
        for v in result[key]:
            if v not in seen:
                seen.add(v)
                deduped.append(v)
        result[key] = deduped
    return result


def _parse_opengraph(og_items: list[dict]) -> str | None:
    """Extrai og:description como fallback de core_business."""
    props: dict[str, str] = {}
    for item in og_items:
        if isinstance(item, dict):
            prop = item.get("property") or item.get("name")
            content = item.get("content")
            if prop and content:
                props[prop] = str(content)
    return (
        props.get("og:description")
        or props.get("twitter:description")
        or props.get("description")
    )


async def _fetch_html(url: str) -> str | None:
    """Baixa o HTML com cliente rotativo de UA e jitter de politeness."""
    import asyncio
    import random
    from ...config import get_settings

    cfg = get_settings()
    # Jitter antes de cada requisicao: mesma logica do PoliteFetcher da Fase 1.
    # Sem isso, N workers disparam sem pausa e o IP pode ser bloqueado.
    await asyncio.sleep(random.uniform(cfg.polite_delay_min, cfg.polite_delay_max))

    client = make_deep_client()
    try:
        async with client:
            client.headers.update({"User-Agent": random.choice(_UA_POOL)})
            resp = await client.get(url)
            resp.raise_for_status()
            return resp.text
    except Exception as exc:
        status = ""
        msg = str(exc)
        if any(c in msg for c in ("403", "429", "401")):
            status = f" HTTP {msg[:3]}"
        elif "timeout" in msg.lower():
            status = " timeout"
        logger.warning("Falha ao buscar HTML%s em %s: %s", status, url, exc)
        return None


async def _extract_impl(url: str) -> ExtractedStartupData:
    data = ExtractedStartupData(url=url, source_url=url)
    html = await _fetch_html(url)

    # --- Nivel 1: JSON-LD / OpenGraph ---
    if html:
        try:
            import extruct  # lazy

            metadata = extruct.extract(
                html,
                base_url=url,
                syntaxes=["json-ld", "opengraph"],
                uniform=False,
            )
            json_ld_result = _parse_json_ld_items(metadata.get("json-ld") or [])
            data.core_business = json_ld_result["core_business"]
            data.use_cases = json_ld_result["use_cases"]
            data.tech_stack_raw = json_ld_result["tech_stack_raw"]
            data.founders_names = json_ld_result["founders_names"]
            data.funding_rounds = json_ld_result["funding_rounds"]
            if data.core_business:
                data.extraction_level = "json_ld"
            # Fallback OpenGraph se JSON-LD nao trouxe core_business
            if not data.core_business:
                og_desc = _parse_opengraph(metadata.get("opengraph") or [])
                if og_desc:
                    data.core_business = og_desc.strip()
                    data.extraction_level = "json_ld"
        except ImportError:
            logger.warning("extruct ausente: pulando Nivel 1 para %s.", url)
        except Exception as exc:
            logger.warning("extruct falhou em %s: %s", url, exc)

    # --- Nivel 2: Texto principal (trafilatura) ---
    if html and not data.core_business:
        try:
            import trafilatura  # lazy

            text = trafilatura.extract(
                html,
                include_comments=False,
                no_fallback=False,
                favor_recall=True,
            )
            if text and text.strip():
                data.raw_text = text.strip()
                if not data.core_business:
                    data.core_business = text.strip()[:800]
                if not data.use_cases:
                    data.use_cases = _extract_use_cases_from_text(text)
                data.extraction_level = "main_text"
        except ImportError:
            logger.warning("trafilatura ausente: pulando Nivel 2 para %s.", url)
        except Exception as exc:
            logger.warning("trafilatura falhou em %s: %s", url, exc)

    # --- Nivel 3: SPA fallback (Crawl4AI) ---
    if not data.raw_text and not data.core_business:
        try:
            from ...enrichment.spa_fallback import fetch_clean
            from ...http_client import PoliteFetcher

            client_raw = make_deep_client()
            try:
                async with client_raw:
                    fetcher = PoliteFetcher(client_raw)
                    text = await fetch_clean(url, fetcher)
                    if text and text.strip():
                        data.raw_text = text.strip()
                        data.core_business = text.strip()[:800]
                        data.extraction_level = "spa"
            finally:
                pass  # client fechado pelo context manager acima
        except (ImportError, AttributeError) as exc:
            logger.warning("crawl4ai indisponivel para %s: raw_text=None (%s)", url, exc)
        except Exception as exc:
            logger.warning("SPA fallback falhou em %s: %s", url, exc)

    return data


try:
    from langchain_core.tools import tool as _lc_tool

    @_lc_tool
    async def extract_startup_data(url: str) -> dict:
        """Extrai conteudo rico de uma startup em 3 niveis (JSON-LD, texto, SPA).

        Retorna um dicionario JSON-serializavel correspondendo a ExtractedStartupData.
        O orquestrador reconstroi o modelo com ExtractedStartupData(**result).
        """
        data = await _extract_impl(url)
        return data.model_dump(mode="json")

except ImportError:
    logger.warning(
        "langchain-core ausente: extract_startup_data nao sera decorada com @tool."
    )

    async def extract_startup_data(url: str) -> dict:  # type: ignore[misc]
        """Versao sem @tool (langchain-core nao instalado)."""
        data = await _extract_impl(url)
        return data.model_dump(mode="json")
