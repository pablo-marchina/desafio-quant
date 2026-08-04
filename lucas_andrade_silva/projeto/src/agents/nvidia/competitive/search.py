from __future__ import annotations

import logging
from urllib.parse import urlsplit

try:
    from ddgs import DDGS
    from ddgs.exceptions import DDGSException
except ModuleNotFoundError:  # pragma: no cover
    DDGS = None
    DDGSException = RuntimeError

from scraper.enrichment_pipeline import config
from scraper.enrichment_pipeline.nodes.web_scrape import (
    extract_text_from_url,
    _rate_limit,
)

logger = logging.getLogger(__name__)

OFFICIAL_DOMAINS = {
    "Anthropic": ("anthropic.com",),
    "OpenAI": ("openai.com",),
    "Google": ("google.com", "cloud.google.com", "ai.google.dev"),
    "xAI": ("x.ai",),
    "DeepSeek": ("deepseek.com",),
    "Microsoft": ("microsoft.com", "azure.com"),
    "Meta": ("meta.com", "ai.meta.com"),
    "Amazon": ("aws.amazon.com",),
    "NVIDIA": ("nvidia.com",),
    "Apple": ("apple.com",),
    "IBM": ("ibm.com",),
    "Oracle": ("oracle.com",),
    "Salesforce": ("salesforce.com",),
    "Adobe": ("adobe.com",),
    "Intel": ("intel.com",),
    "AMD": ("amd.com",),
    "Qualcomm": ("qualcomm.com",),
    "Tesla": ("tesla.com",),
    "Palantir Technologies": ("palantir.com",),
    "Snowflake": ("snowflake.com",),
    "Databricks": ("databricks.com",),
    "Mistral AI": ("mistral.ai",),
    "Cohere": ("cohere.com",),
    "DeepMind": ("deepmind.google",),
    "Tencent": ("tencent.com", "cloud.tencent.com"),
    "Alibaba": ("alibaba.com", "alibabacloud.com"),
    "ByteDance": ("bytedance.com",),
    "Huawei": ("huawei.com",),
    "Baidu": ("baidu.com",),
    "Samsung Electronics": ("samsung.com",),
    "Naver": ("naver.com",),
    "TOTVS": ("totvs.com",),
    "CI&T": ("ciandt.com",),
    "Stefanini": ("stefanini.com",),
    "TIVIT": ("tivit.com",),
    "Positivo Tecnologia": ("positivo.com.br",),
    "Locaweb": ("locaweb.com.br",),
    "Take Blip": ("blip.ai",),
    "Sinqia": ("sinqia.com.br",),
    "Zup Innovation": ("zup.com.br",),
    "Stone": ("stone.com.br",),
    "PagBank": ("pagbank.com.br",),
    "Nubank": ("nubank.com.br",),
    "iFood": ("ifood.com.br",),
    "VTEX": ("vtex.com",),
    "Hugging Face": ("huggingface.co",),
    "Scale AI": ("scale.com",),
    "Runway": ("runwayml.com",),
    "Perplexity AI": ("perplexity.ai",),
    "SAP": ("sap.com",),
    "Cisco": ("cisco.com",),
    "Accenture": ("accenture.com",),
    "ServiceNow": ("servicenow.com",),
    "Workday": ("workday.com",),
    "Atlassian": ("atlassian.com",),
    "HubSpot": ("hubspot.com",),
    "Zoom": ("zoom.com",),
    "Twilio": ("twilio.com",),
    "Cloudflare": ("cloudflare.com",),
    "MongoDB": ("mongodb.com",),
    "Elastic": ("elastic.co",),
    "Red Hat": ("redhat.com",),
    "Broadcom": ("broadcom.com",),
    "Dell Technologies": ("dell.com",),
    "Hewlett Packard Enterprise": ("hpe.com",),
    "HP": ("hp.com",),
    "Stripe": ("stripe.com",),
    "PayPal": ("paypal.com",),
    "Block": ("block.xyz", "squareup.com"),
    "Visa": ("visa.com",),
    "Mastercard": ("mastercard.com",),
    "Cielo": ("cielo.com.br",),
    "Rede": ("userede.com.br",),
    "Getnet": ("getnet.com.br",),
    "PicPay": ("picpay.com",),
    "Mercado Pago": ("mercadopago.com.br",),
    "Itaú Unibanco": ("itau.com.br",),
    "Bradesco": ("bradesco.com.br",),
    "Santander": ("santander.com.br",),
    "BTG Pactual": ("btgpactual.com",),
    "XP Inc.": ("xpinc.com", "xp.com.br"),
    "JPMorgan Chase": ("jpmorganchase.com", "jpmorgan.com"),
    "Goldman Sachs": ("goldmansachs.com",),
    "B3": ("b3.com.br",),
    "Serasa Experian": ("serasaexperian.com.br",),
    "Experian": ("experian.com",),
    "Equifax": ("equifax.com",),
    "Bloomberg": ("bloomberg.com",),
    "Thomson Reuters": ("thomsonreuters.com",),
    "Shopify": ("shopify.com",),
    "Mercado Livre": ("mercadolivre.com.br", "mercadolibre.com"),
    "Magazine Luiza": ("magazineluiza.com.br", "luizalabs.com"),
    "Rappi": ("rappi.com",),
    "Uber": ("uber.com",),
    "99": ("99app.com",),
    "Localiza": ("localiza.com",),
    "DHL": ("dhl.com",),
    "FedEx": ("fedex.com",),
    "UPS": ("ups.com",),
    "Siemens": ("siemens.com",),
    "Bosch": ("bosch.com",),
    "GE": ("ge.com",),
    "Schneider Electric": ("se.com",),
    "Honeywell": ("honeywell.com",),
    "Embraer": ("embraer.com",),
    "WEG": ("weg.net",),
    "Petrobras": ("petrobras.com.br",),
    "Vale": ("vale.com",),
    "Gerdau": ("gerdau.com",),
    "Raízen": ("raizen.com.br",),
    "Suzano": ("suzano.com.br",),
    "Ambev": ("ambev.com.br",),
    "Natura": ("natura.com.br",),
    "Johnson & Johnson": ("jnj.com",),
    "Pfizer": ("pfizer.com",),
    "Roche": ("roche.com",),
    "Novartis": ("novartis.com",),
    "Philips": ("philips.com",),
    "UnitedHealth Group": ("unitedhealthgroup.com", "uhg.com"),
    "Hospital Israelita Albert Einstein": ("einstein.br",),
    "Dasa": ("dasa.com.br",),
    "Rede D'Or": ("rededorsaoluiz.com.br",),
    "RD Saúde": ("rdsaude.com.br",),
}

DEFAULT_SEARCH_COMPANIES = (
    "OpenAI",
    "Google",
    "Microsoft",
    "Amazon",
    "Meta",
    "NVIDIA",
    "IBM",
    "Oracle",
    "Salesforce",
    "SAP",
    "Cisco",
    "ServiceNow",
    "Stripe",
    "Nubank",
    "Stone",
    "Mercado Livre",
    "Siemens",
    "Philips",
    "Accenture",
    "TOTVS",
)


def normalized_host(url: str) -> str:
    return (urlsplit(url).hostname or "").casefold().removeprefix("www.")


def company_for_official_url(url: str) -> str | None:
    host = normalized_host(url)
    for company, domains in OFFICIAL_DOMAINS.items():
        if any(host == domain or host.endswith(f".{domain}") for domain in domains):
            return company
    return None


def _search_text(query: str, max_results: int) -> list[dict[str, object]]:
    if DDGS is None:
        return []
    try:
        with DDGS(timeout=config.HTTP_TIMEOUT_SECONDS) as ddgs:
            return list(ddgs.text(query, max_results=max_results))
    except DDGSException as exc:
        logger.warning("Busca DDGS indisponivel; seguindo sem resultados: %s", exc)
        return []


def search_official_candidates(
    query: str | list[str],
    tested: set[str],
    companies: list[str] | None = None,
) -> list[dict[str, str]]:
    if DDGS is None:
        raise RuntimeError("ddgs não está instalado")
    selected_companies = [
        company
        for company in (companies or DEFAULT_SEARCH_COMPANIES)
        if company in OFFICIAL_DOMAINS
    ]
    domain_filter = " OR ".join(
        f"site:{domain}"
        for company in selected_companies
        for domain in OFFICIAL_DOMAINS[company]
    )
    if not domain_filter:
        return []
    queries = [query] if isinstance(query, str) else query
    for search_query in queries:
        if not str(search_query).strip():
            continue
        _rate_limit()
        rows: list[dict[str, str]] = []
        for result in _search_text(
            f"{search_query} ({domain_filter})",
            max_results=30,
        ):
            url = str(result.get("href") or result.get("url") or "").strip()
            company = company_for_official_url(url)
            if not company or url in tested:
                continue
            rows.append(
                {
                    "url": url,
                    "company": company,
                    "title": str(result.get("title") or ""),
                    "snippet": str(
                        result.get("body") or result.get("snippet") or ""
                    ),
                }
            )
        if rows:
            return rows
    return []


def scrape_official_candidate(candidate: dict[str, str]) -> dict[str, object]:
    url = candidate["url"]
    if not company_for_official_url(url):
        raise ValueError("URL fora dos domínios oficiais permitidos")
    text = extract_text_from_url(url)
    return {
        "candidato_url": url,
        "candidato_empresa": candidate["company"],
        "candidato_conteudo": {
            "titulo_produto": candidate["title"],
            "descricao_oficial": text[:6000] or candidate["snippet"],
            "trecho_relevante": (text[:1500] or candidate["snippet"]),
        },
    }


def search_pricing_page(
    query: str, allowed_domains: tuple[str, ...]
) -> dict[str, str] | None:
    """Busca e coleta no máximo uma página de preço do domínio oficial."""
    if DDGS is None or not allowed_domains:
        return None
    site_query = " OR ".join(f"site:{domain}" for domain in allowed_domains)
    _rate_limit()
    results = _search_text(f"{query} pricing ({site_query})", max_results=10)
    for result in results:
        url = str(result.get("href") or result.get("url") or "").strip()
        host = normalized_host(url)
        if not any(
            host == domain or host.endswith(f".{domain}")
            for domain in allowed_domains
        ):
            continue
        try:
            text = extract_text_from_url(url)
        except Exception:
            continue
        if text:
            return {"url": url, "conteudo": text[:5000]}
    return None
