from __future__ import annotations

import json
import os
import re
import unicodedata
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import UTC, datetime
from typing import Any
from urllib.parse import urlsplit

from scraper.enrichment_pipeline import config
from scraper.enrichment_pipeline.nodes.web_scrape import (
    DDGS,
    extract_text_from_url,
)

MODEL = os.getenv("TECH_INTELLIGENCE_MODEL", "openai/gpt-oss-120b")
MAX_RESULTS_PER_QUERY = max(
    1, int(os.getenv("TECH_INTELLIGENCE_RESULTS_PER_QUERY", "3"))
)
MAX_PAGES = max(1, int(os.getenv("TECH_INTELLIGENCE_MAX_PAGES", "12")))

SYSTEM_PROMPT = """
Você é Especialista em Inteligência de Mercado e CTO. Analise SOMENTE as
evidências numeradas recebidas. Não use conhecimento não documentado.

Separe tecnologia confirmada de inferência provável. Uma vaga pedindo uma
tecnologia é evidência Média de uso, não confirmação arquitetural. Repositório
oficial ou engenharia oficial pode gerar evidência Alta. Snippet isolado,
agregador ou notícia indireta normalmente é Baixa.

Retorne exclusivamente um objeto json válido com este formato:
{
  "perfil_geral": {"resumo": "...", "evidencias": ["S1"]},
  "infraestrutura_backend": [
    {"tecnologia": "...", "uso_provavel": "...", "certeza": "Alta|Média|Baixa",
     "evidencias": ["S1"]}
  ],
  "frontend_mobile": [],
  "ia_operacional_interna": [],
  "ia_produto_core": [],
  "nivel_certeza": {"classificacao": "Alta|Média|Baixa",
                    "justificativa": "..."},
  "dados_insuficientes": []
}

Regras:
- Todo fato ou inferência precisa citar ao menos um ID de evidência fornecido.
- Não confunda IA usada internamente com IA que compõe o produto vendido.
- Não transforme ausência de evidência em conclusão de que a empresa não usa.
- Escreva em português e mantenha os itens curtos e auditáveis.
""".strip()


def build_queries(company_name: str, domain: str | None = None) -> list[str]:
    quoted = f'"{company_name}"'
    domain_hint = f" {domain}" if domain else ""
    return [
        f"{quoted} vagas engenheiro desenvolvedor dados IA",
        f"{quoted} Gupy tecnologia",
        f"{quoted} LinkedIn jobs software engineer",
        f"{quoted} GitHub",
        f"{quoted} StackShare",
        f"{quoted} arquitetura engenharia tecnologia",
        f"{quoted} AWS GCP Azure cloud",
        f"{quoted} Python Node React Flutter Swift",
        f"{quoted} OpenAI LLM inteligência artificial",
        f"{quoted}{domain_hint} Medium Brazil Journal Startups.com.br Exame",
    ]


def _search_query(query: str) -> list[dict[str, str]]:
    if DDGS is None:
        raise RuntimeError("ddgs nao esta instalado")
    with DDGS(timeout=config.HTTP_TIMEOUT_SECONDS) as ddgs:
        results = ddgs.text(query, max_results=MAX_RESULTS_PER_QUERY)
        return [
            {
                "url": str(row.get("href") or row.get("url") or "").strip(),
                "title": str(row.get("title") or "").strip(),
                "snippet": str(
                    row.get("body") or row.get("snippet") or ""
                ).strip(),
                "query": query,
            }
            for row in results
            if str(row.get("href") or row.get("url") or "").startswith("http")
        ]


def search_sources(queries: list[str]) -> tuple[list[dict[str, str]], list[str]]:
    rows: list[dict[str, str]] = []
    errors: list[str] = []
    with ThreadPoolExecutor(max_workers=min(6, len(queries))) as executor:
        futures = {executor.submit(_search_query, query): query for query in queries}
        for future in as_completed(futures):
            try:
                rows.extend(future.result())
            except Exception as error:
                errors.append(f"{futures[future]}: {error}")

    deduped: list[dict[str, str]] = []
    seen: set[str] = set()
    for row in rows:
        url = row["url"].split("#", 1)[0]
        if url in seen:
            continue
        seen.add(url)
        row["url"] = url
        deduped.append(row)
    return deduped[:MAX_PAGES], errors


def _fetch_source(row: dict[str, str]) -> dict[str, str]:
    try:
        text = extract_text_from_url(row["url"])
    except Exception:
        text = ""
    content = re.sub(r"\s+", " ", text).strip()[:6000]
    return {**row, "content": content or row.get("snippet", "")}


def fetch_sources(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    with ThreadPoolExecutor(max_workers=min(6, len(rows) or 1)) as executor:
        return list(executor.map(_fetch_source, rows))


def source_matches_company(
    source: dict[str, str], company_name: str, company_domain: str | None
) -> bool:
    host = (urlsplit(source.get("url", "")).hostname or "").removeprefix("www.")
    if company_domain and (
        host == company_domain or host.endswith(f".{company_domain}")
    ):
        return True
    normalized_name = re.sub(
        r"[^a-z0-9]+",
        " ",
        unicodedata.normalize("NFKD", company_name.casefold())
        .encode("ascii", "ignore")
        .decode("ascii"),
    ).strip()
    haystack = unicodedata.normalize(
        "NFKD",
        " ".join(
            (
                source.get("title", ""),
                source.get("snippet", ""),
                source.get("content", "")[:2500],
                source.get("url", ""),
            )
        ).casefold(),
    ).encode("ascii", "ignore").decode("ascii")
    if normalized_name and normalized_name in re.sub(
        r"[^a-z0-9]+", " ", haystack
    ):
        return True
    meaningful_tokens = [
        token
        for token in normalized_name.split()
        if len(token) >= 5
        and token not in {"tecnologia", "technology", "brasil", "sistemas"}
    ]
    return bool(meaningful_tokens) and all(
        token in haystack for token in meaningful_tokens
    )


def _json_object(raw: str) -> dict[str, Any]:
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", cleaned)
    parsed = json.loads(cleaned)
    if not isinstance(parsed, dict):
        raise ValueError("OpenRouter response is not a JSON object")
    return parsed


def _invoke_openrouter(prompt: str) -> dict[str, Any]:
    from langchain_openai import ChatOpenAI

    llm = ChatOpenAI(
        model=MODEL,
        api_key=config.openrouter_api_key(),
        base_url=config.OPENROUTER_BASE_URL,
        default_headers={
            "HTTP-Referer": config.OPENROUTER_REFERER,
            "X-Title": config.OPENROUTER_TITLE,
        },
        temperature=0,
        max_tokens=2200,
        model_kwargs={"response_format": {"type": "json_object"}},
    )
    response = llm.invoke(
        [
            ("system", SYSTEM_PROMPT),
            ("user", prompt),
        ]
    )
    return _json_object(str(getattr(response, "content", response)))


def _evidence_payload(
    company: dict[str, Any], sources: list[dict[str, str]]
) -> tuple[str, list[dict[str, str]]]:
    evidence: list[dict[str, str]] = []
    blocks: list[str] = []
    for index, source in enumerate(sources, 1):
        item = {
            "id": f"S{index}",
            "url": source["url"],
            "titulo": source.get("title", ""),
            "dominio": (urlsplit(source["url"]).hostname or "").removeprefix(
                "www."
            ),
            "consulta": source.get("query", ""),
            "trecho": source.get("content", "")[:1200],
        }
        evidence.append(item)
        blocks.append(
            f"[{item['id']}] {item['titulo']}\nURL: {item['url']}\n"
            f"TRECHO: {item['trecho']}"
        )
    context = {
        key: company.get(key)
        for key in (
            "company_name",
            "validated_url",
            "website",
            "company_description",
            "description",
            "github_org",
            "gupy_url",
        )
        if company.get(key)
    }
    prompt = (
        f"EMPRESA DO CATÁLOGO:\n{json.dumps(context, ensure_ascii=False)}\n\n"
        "EVIDÊNCIAS DA PESQUISA:\n" + "\n\n".join(blocks)
    )
    return prompt, evidence


def _validated_report(
    raw: dict[str, Any], evidence: list[dict[str, str]]
) -> dict[str, Any]:
    valid_ids = {item["id"] for item in evidence}

    def ids(value: Any) -> list[str]:
        return [
            item
            for item in (value if isinstance(value, list) else [])
            if isinstance(item, str) and item in valid_ids
        ]

    profile = raw.get("perfil_geral")
    if not isinstance(profile, dict):
        profile = {}
    profile_ids = ids(profile.get("evidencias"))
    validated: dict[str, Any] = {
        "perfil_geral": {
            "resumo": str(profile.get("resumo") or "")
            if profile_ids
            else "Dados insuficientes.",
            "evidencias": profile_ids,
        }
    }
    for field in (
        "infraestrutura_backend",
        "frontend_mobile",
        "ia_operacional_interna",
        "ia_produto_core",
    ):
        items = []
        for value in raw.get(field) or []:
            if not isinstance(value, dict):
                continue
            evidence_ids = ids(value.get("evidencias"))
            technology = str(value.get("tecnologia") or "").strip()
            if not technology or not evidence_ids:
                continue
            certainty = str(value.get("certeza") or "Baixa").title()
            if certainty not in {"Alta", "Média", "Baixa"}:
                certainty = "Baixa"
            items.append(
                {
                    "tecnologia": technology[:120],
                    "uso_provavel": str(
                        value.get("uso_provavel") or ""
                    ).strip()[:500],
                    "certeza": certainty,
                    "evidencias": evidence_ids,
                }
            )
        validated[field] = items

    level = raw.get("nivel_certeza")
    if not isinstance(level, dict):
        level = {}
    classification = str(level.get("classificacao") or "Baixa").title()
    if classification not in {"Alta", "Média", "Baixa"}:
        classification = "Baixa"
    validated["nivel_certeza"] = {
        "classificacao": classification,
        "justificativa": str(level.get("justificativa") or "")[:500],
    }
    validated["dados_insuficientes"] = [
        str(item)[:300]
        for item in (raw.get("dados_insuficientes") or [])
        if str(item).strip()
    ][:10]
    validated["fontes"] = evidence
    return validated


class TechnologyIntelligenceAgent:
    def analyze(self, startup: dict[str, Any], progress=lambda _: None) -> dict[str, Any]:
        company_name = str(startup.get("company_name") or "").strip()
        if not company_name:
            raise ValueError("Startup has no company_name")
        url = str(startup.get("validated_url") or startup.get("website") or "")
        parsed_url = urlsplit(url if "://" in url else f"//{url}")
        domain = (parsed_url.hostname or "").removeprefix("www.") or None
        queries = build_queries(company_name, domain)
        progress(10)
        rows, search_errors = search_sources(queries)
        progress(45)
        sources = fetch_sources(rows)
        useful = [
            source
            for source in sources
            if source.get("content")
            and source_matches_company(source, company_name, domain)
        ]
        if not useful:
            raise RuntimeError("Nenhuma evidência pública foi encontrada")
        prompt, evidence = _evidence_payload(startup, useful)
        progress(70)
        report = _validated_report(_invoke_openrouter(prompt), evidence)
        report.update(
            {
                "schema_version": "technology-intelligence/v1",
                "company_name": company_name,
                "modelo": MODEL,
                "consultas": queries,
                "erros_de_busca": search_errors,
                "pesquisado_em": datetime.now(UTC).isoformat(),
            }
        )
        progress(95)
        return report
