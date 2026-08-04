from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from urllib.parse import quote_plus, urlparse
from xml.etree import ElementTree

import httpx

from app.llm.client import LlmUnavailableError, generate_openai_json, is_llm_enabled
from app.settings import get_settings

_DISCOVERY_CACHE: dict[tuple[str, str, int, bool, tuple[str, ...]], "MarketDiscoveryResult"] = {}


@dataclass(frozen=True)
class LiveSearchLink:
    label: str
    url: str


@dataclass(frozen=True)
class NewsArticle:
    title: str
    url: str
    published_at: datetime | None
    source: str
    query: str


@dataclass(frozen=True)
class MarketCandidate:
    name: str
    sector: str
    website: str
    why_relevant: str
    ai_native_signals: tuple[str, ...]
    nvidia_opportunity: tuple[str, ...]
    wrapper_risk: float
    nvidia_fit: float
    urgency: float
    rank_score: float
    evidence_count: int
    source_urls: tuple[str, ...]
    analysis_text: str


@dataclass(frozen=True)
class MarketDiscoveryResult:
    query: str
    country: str
    summary: str
    trend_signals: tuple[str, ...]
    suggested_queries: tuple[str, ...]
    source_targets: tuple[str, ...]
    live_search_links: tuple[LiveSearchLink, ...]
    candidates: tuple[MarketCandidate, ...]
    evaluation_checklist: tuple[str, ...]
    next_actions: tuple[str, ...]
    crawl_status: str
    crawled_source_count: int


def build_market_discovery(
    query: str,
    country: str,
    max_results: int,
    client: httpx.Client | None = None,
) -> MarketDiscoveryResult:
    normalized_query = " ".join(query.split())
    normalized_country = country.strip() or "Brasil"
    portuguese_country = _country_label(normalized_country)
    settings = get_settings()
    llm_enabled = is_llm_enabled(settings)

    sector = _detect_sector(normalized_query)
    suggested_queries = _suggested_queries(normalized_query, portuguese_country, sector)
    articles = crawl_market_articles(suggested_queries[:4], client=client)
    cache_key = (
        normalized_query.casefold(),
        portuguese_country.casefold(),
        max_results,
        llm_enabled,
        _article_signature(articles),
    )
    if client is None and cache_key in _DISCOVERY_CACHE:
        return _DISCOVERY_CACHE[cache_key]

    candidates = _rank_candidates_with_llm_or_fallback(
        articles,
        sector,
        max_results,
        normalized_query,
    )
    crawl_status = "succeeded" if articles else "no_results"

    result = MarketDiscoveryResult(
        query=normalized_query,
        country=portuguese_country,
        summary=(
            f"Busca automática em fontes recentes encontrou {len(candidates)} candidatas "
            f"rankeadas para {sector.lower()} no {portuguese_country}."
        ),
        trend_signals=_trend_signals(sector),
        suggested_queries=suggested_queries,
        source_targets=_source_targets(sector),
        live_search_links=_live_search_links(suggested_queries[:5]),
        candidates=candidates,
        evaluation_checklist=_evaluation_checklist(),
        next_actions=(
            "Abrir as fontes das candidatas mais bem rankeadas e validar evidência recente.",
            "Carregar uma candidata no fluxo de análise para gerar relatório completo.",
            "Priorizar empresas com evidência de produto em produção e dor de inferência.",
        ),
        crawl_status=crawl_status,
        crawled_source_count=len(articles),
    )
    if client is None:
        _DISCOVERY_CACHE[cache_key] = result
    return result


def crawl_market_articles(
    queries: tuple[str, ...],
    client: httpx.Client | None = None,
    per_query_limit: int = 8,
) -> tuple[NewsArticle, ...]:
    owns_client = client is None
    http_client = client or httpx.Client(timeout=8.0, follow_redirects=True)
    articles: list[NewsArticle] = []

    try:
        for query in queries:
            url = _google_news_rss_url(query)
            try:
                response = http_client.get(url)
                response.raise_for_status()
            except httpx.HTTPError:
                continue
            articles.extend(_parse_google_news_rss(response.text, query)[:per_query_limit])
    finally:
        if owns_client:
            http_client.close()

    return tuple(_sort_articles(_dedupe_articles(articles)))


def _rank_candidates_with_llm_or_fallback(
    articles: tuple[NewsArticle, ...],
    sector: str,
    max_results: int,
    query: str,
) -> tuple[MarketCandidate, ...]:
    settings = get_settings()
    if is_llm_enabled(settings) and articles:
        try:
            candidates = _rank_candidates_with_llm(articles, sector, max_results, query)
            if candidates:
                return candidates
        except (LlmUnavailableError, KeyError, TypeError, ValueError):
            pass
    return _rank_candidates(articles, sector, max_results)


def _rank_candidates_with_llm(
    articles: tuple[NewsArticle, ...],
    sector: str,
    max_results: int,
    query: str,
) -> tuple[MarketCandidate, ...]:
    settings = get_settings()
    article_payload = [
        {
            "title": article.title,
            "url": article.url,
            "source": article.source,
            "published_at": article.published_at.isoformat() if article.published_at else None,
        }
        for article in articles[:24]
    ]
    response = generate_openai_json(
        settings=settings,
        system_prompt=(
            "Você é um analista de mercado da NVIDIA. A partir de notícias recentes, "
            "identifique empresas reais, descarte termos genéricos, veículos de mídia, "
            "laboratórios grandes e páginas que não sejam startups. Faça uma análise "
            "criteriosa de fit NVIDIA, risco de wrapper, evidência multi-fonte e "
            "maturidade IA-native. Responda somente JSON válido."
        ),
        user_prompt=(
            "Retorne JSON no formato: "
            '{"candidates": ['
            '{"name": string, "sector": string, "website": string, "why_relevant": string, '
            '"ai_native_signals": string[], "nvidia_opportunity": string[], '
            '"wrapper_risk": number, "nvidia_fit": number, "urgency": number, '
            '"rank_score": number, "source_urls": string[], "analysis_text": string}'
            "]}. "
            "Todos os scores devem estar entre 0 e 1. "
            "Use rank_score alto apenas quando houver pelo menos dois indícios públicos "
            "ou um indício muito forte de produto IA-native. Penalize candidatas com "
            "uma única fonte fraca, menções genéricas, matéria opinativa ou ausência "
            "de produto. Em analysis_text, escreva uma síntese profunda em português "
            "com: tese de oportunidade, evidências usadas, risco técnico, hipótese de "
            "fit NVIDIA e próximas perguntas de validação. "
            "Não inclua palavras genéricas como IA, Inteligência, Brasil, Rio "
            "ou nomes de veículos. "
            f"Busca: {query}. Setor preferencial: {sector}. Máximo: {max_results}. "
            f"Notícias: {article_payload}"
        ),
    )
    candidates = [
        _candidate_from_llm(item)
        for item in _list_value(response.get("candidates"))
        if isinstance(item, dict)
    ]
    valid_candidates = [candidate for candidate in candidates if candidate is not None]
    ranked = sorted(valid_candidates, key=lambda candidate: candidate.rank_score, reverse=True)
    return tuple(ranked[:max_results])


def _candidate_from_llm(raw_candidate: dict[str, object]) -> MarketCandidate | None:
    name = _string_value(raw_candidate.get("name"))
    if not name or _looks_like_publisher(name):
        return None
    source_urls = tuple(_string_list(raw_candidate.get("source_urls")))
    rank_score = _float_between_zero_and_one(raw_candidate.get("rank_score"))
    adjusted_rank_score = _adjust_rank_score_for_evidence(rank_score, source_urls)
    return MarketCandidate(
        name=name,
        sector=_string_value(raw_candidate.get("sector")) or "IA aplicada",
        website=(
            _string_value(raw_candidate.get("website"))
            or (source_urls[0] if source_urls else "")
        ),
        why_relevant=(
            _string_value(raw_candidate.get("why_relevant"))
            or "Candidata identificada por LLM."
        ),
        ai_native_signals=tuple(_string_list(raw_candidate.get("ai_native_signals"))),
        nvidia_opportunity=tuple(_string_list(raw_candidate.get("nvidia_opportunity"))),
        wrapper_risk=_float_between_zero_and_one(raw_candidate.get("wrapper_risk")),
        nvidia_fit=_float_between_zero_and_one(raw_candidate.get("nvidia_fit")),
        urgency=_float_between_zero_and_one(raw_candidate.get("urgency")),
        rank_score=adjusted_rank_score,
        evidence_count=max(len(source_urls), 1),
        source_urls=source_urls,
        analysis_text=_string_value(raw_candidate.get("analysis_text")) or "",
    )


def _parse_google_news_rss(xml_text: str, query: str) -> tuple[NewsArticle, ...]:
    try:
        root = ElementTree.fromstring(xml_text)
    except ElementTree.ParseError:
        return ()

    articles: list[NewsArticle] = []
    for item in root.findall(".//item"):
        title = (item.findtext("title") or "").strip()
        link = (item.findtext("link") or "").strip()
        pub_date = (item.findtext("pubDate") or "").strip()
        source = (item.findtext("source") or _domain_name(link)).strip()
        if not title or not link:
            continue
        articles.append(
            NewsArticle(
                title=title,
                url=link,
                published_at=_parse_pub_date(pub_date),
                source=source,
                query=query,
            )
        )
    return tuple(articles)


def _rank_candidates(
    articles: tuple[NewsArticle, ...],
    sector: str,
    max_results: int,
) -> tuple[MarketCandidate, ...]:
    grouped: dict[str, list[NewsArticle]] = {}
    for article in articles:
        candidate_name = _extract_candidate_name(article.title)
        if not candidate_name or _looks_like_publisher(candidate_name):
            continue
        grouped.setdefault(candidate_name, []).append(article)

    candidates = [
        _build_candidate(name, evidence_articles, sector)
        for name, evidence_articles in grouped.items()
    ]
    ranked = sorted(
        candidates,
        key=lambda candidate: (candidate.rank_score, candidate.evidence_count),
        reverse=True,
    )
    return tuple(ranked[:max_results])


def _build_candidate(
    name: str,
    articles: list[NewsArticle],
    requested_sector: str,
) -> MarketCandidate:
    evidence_text = " ".join(article.title for article in articles)
    sector = (
        _detect_sector(evidence_text)
        if requested_sector == "IA aplicada"
        else requested_sector
    )
    ai_score = _keyword_score(evidence_text, _AI_NATIVE_KEYWORDS)
    nvidia_score = _keyword_score(evidence_text, _NVIDIA_FIT_KEYWORDS)
    wrapper_score = _keyword_score(evidence_text, _WRAPPER_RISK_KEYWORDS)
    recency_score = max((_recency_score(article.published_at) for article in articles), default=0.2)
    evidence_score = min(len(articles) / 3, 1.0)
    rank_score = _clamp(
        0.34 * ai_score + 0.24 * nvidia_score + 0.18 * recency_score + 0.24 * evidence_score
    )
    urgency = _clamp(0.45 * nvidia_score + 0.35 * recency_score + 0.2 * wrapper_score)

    return MarketCandidate(
        name=name,
        sector=sector,
        website=articles[0].url,
        why_relevant=_why_relevant(name, sector, articles),
        ai_native_signals=_signals_from_text(evidence_text),
        nvidia_opportunity=_nvidia_opportunities(evidence_text),
        wrapper_risk=_clamp(0.35 + 0.45 * wrapper_score),
        nvidia_fit=_clamp(0.35 + 0.55 * nvidia_score),
        urgency=urgency,
        rank_score=rank_score,
        evidence_count=len(articles),
        source_urls=tuple(article.url for article in articles[:4]),
        analysis_text=_analysis_text(name, sector, evidence_text, articles),
    )


def _extract_candidate_name(title: str) -> str | None:
    cleaned = title.split(" - ")[0].strip()
    lowered = cleaned.lower()
    triggers = (
        "startup ",
        "empresa ",
        "healthtech ",
        "fintech ",
        "edtech ",
        "legaltech ",
        "agtech ",
    )
    for trigger in triggers:
        index = lowered.find(trigger)
        if index >= 0:
            after_trigger = cleaned[index + len(trigger) :]
            return _clean_candidate_name(after_trigger)

    for verb in (
        " recebe ",
        " capta ",
        " levanta ",
        " raises ",
        " lança ",
        " usa ",
        " firma ",
        " é ",
    ):
        if verb in lowered:
            before_verb = cleaned[: lowered.find(verb)].strip()
            return _clean_candidate_name(before_verb)

    if ":" in cleaned:
        return _clean_candidate_name(cleaned.split(":", 1)[0])
    return None


def _clean_candidate_name(value: str) -> str | None:
    stop_words = {
        "a",
        "as",
        "o",
        "os",
        "de",
        "da",
        "das",
        "do",
        "dos",
        "que",
        "com",
        "para",
        "brasileira",
        "brasileiro",
    }
    words = [
        word.strip(" ,.;:()[]{}\"'")
        for word in value.split()
        if word.strip(" ,.;:()[]{}\"'")
    ]
    selected: list[str] = []
    for word in words:
        normalized = word.lower()
        if normalized in stop_words:
            continue
        if word[:1].isupper() or word.isupper() or any(character.isdigit() for character in word):
            selected.append(word)
        elif selected:
            break
        if len(selected) == 3:
            break
    if not selected:
        return None
    candidate = " ".join(selected)
    if len(selected) == 1:
        lowered_candidate = candidate.lower()
        if not (lowered_candidate.endswith("ai") or candidate.endswith("IA")):
            return None
    if len(selected) == 1 and "ai" not in candidate.lower() and "ia" not in candidate.lower():
        return None
    return candidate


def _looks_like_publisher(name: str) -> bool:
    lowered = name.lower()
    blocked = {
        "bloomberg",
        "brasil",
        "elite ia",
        "exame",
        "forbes",
        "google",
        "ia",
        "inteligência",
        "incêndio",
        "linkedin",
        "rio",
        "startupi",
        "startups",
        "valor",
        "vonage",
    }
    generic_prefixes = ("como ", "por que ", "o que ", "a nova ", "novo ")
    return lowered in blocked or lowered.startswith(generic_prefixes) or len(name) < 2


def _why_relevant(name: str, sector: str, articles: list[NewsArticle]) -> str:
    source_names = sorted({article.source for article in articles if article.source})
    source_text = ", ".join(source_names[:3]) or "fontes recentes"
    return (
        f"{name} apareceu em {len(articles)} fonte(s) recentes sobre {sector.lower()}, "
        f"incluindo {source_text}, com sinais públicos relacionados a IA."
    )


def _signals_from_text(text: str) -> tuple[str, ...]:
    lowered = text.lower()
    signals = []
    if any(keyword in lowered for keyword in ("agente", "agent", "copiloto", "copilot")):
        signals.append("Produto descrito com agentes ou copilotos de IA.")
    if any(keyword in lowered for keyword in ("generativa", "generative", "llm", "modelo")):
        signals.append("Menção explícita a IA generativa, LLMs ou modelos fundacionais.")
    if any(keyword in lowered for keyword in ("automação", "automatiza", "workflow", "operação")):
        signals.append("IA aplicada a workflow operacional, não só camada de chat.")
    if any(keyword in lowered for keyword in ("rodada", "capta", "recebe", "raises", "funding")):
        signals.append("Sinal recente de tração, investimento ou expansão.")
    return tuple(signals or ("Evidência pública recente de uso de IA no posicionamento.",))


def _nvidia_opportunities(text: str) -> tuple[str, ...]:
    lowered = text.lower()
    opportunities = []
    if any(keyword in lowered for keyword in ("saúde", "jurídico", "finance", "banco")):
        opportunities.append("Implantação privada, governança e guardrails para dados sensíveis.")
    if any(keyword in lowered for keyword in ("llm", "generativa", "agente", "copiloto")):
        opportunities.append("Otimização de inferência com TensorRT-LLM e Triton.")
    if any(keyword in lowered for keyword in ("documento", "dados", "workflow", "crm")):
        opportunities.append("RAG e avaliação com NeMo para respostas rastreáveis.")
    return tuple(opportunities or ("Validar fit NVIDIA em inferência, RAG, dados e governança.",))


def _analysis_text(
    name: str,
    sector: str,
    evidence_text: str,
    articles: list[NewsArticle],
) -> str:
    sources = "; ".join(article.title for article in articles[:3])
    return (
        f"{name} foi identificado automaticamente em busca recente sobre IA no setor "
        f"{sector}. Evidências encontradas: {sources}. O texto sugere uma candidata "
        "para análise NVIDIA quando houver produto de IA em produção, uso de agentes, "
        "LLMs, automação de workflow, dados proprietários ou dor de inferência. "
        f"Resumo de sinais: {evidence_text[:800]}"
    )


def _keyword_score(text: str, keywords: tuple[str, ...]) -> float:
    lowered = text.lower()
    matches = sum(1 for keyword in keywords if keyword in lowered)
    return _clamp(matches / 4)


def _recency_score(published_at: datetime | None) -> float:
    if published_at is None:
        return 0.25
    age_days = max((datetime.now(UTC) - published_at.astimezone(UTC)).days, 0)
    if age_days <= 14:
        return 1.0
    if age_days <= 60:
        return 0.8
    if age_days <= 180:
        return 0.55
    return 0.3


def _parse_pub_date(value: str) -> datetime | None:
    if not value:
        return None
    try:
        parsed = parsedate_to_datetime(value)
    except (TypeError, ValueError):
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed


def _dedupe_articles(articles: list[NewsArticle]) -> list[NewsArticle]:
    deduped: dict[str, NewsArticle] = {}
    for article in articles:
        key = article.url or article.title.lower()
        deduped[key] = article
    return list(deduped.values())


def _sort_articles(articles: list[NewsArticle]) -> list[NewsArticle]:
    return sorted(
        articles,
        key=lambda article: (
            article.published_at or datetime.min.replace(tzinfo=UTC),
            article.source.casefold(),
            article.title.casefold(),
            article.url,
        ),
        reverse=True,
    )


def _article_signature(articles: tuple[NewsArticle, ...]) -> tuple[str, ...]:
    return tuple(article.url or article.title.casefold() for article in articles[:32])


def _adjust_rank_score_for_evidence(rank_score: float, source_urls: tuple[str, ...]) -> float:
    unique_source_count = len(set(source_urls))
    if unique_source_count >= 3:
        return _clamp(rank_score)
    if unique_source_count == 2:
        return _clamp(rank_score * 0.9)
    return _clamp(rank_score * 0.72)


def _google_news_rss_url(query: str) -> str:
    return (
        "https://news.google.com/rss/search?"
        f"q={quote_plus(query)}&hl=pt-BR&gl=BR&ceid=BR:pt-419"
    )


def _domain_name(url: str) -> str:
    return urlparse(url).netloc.replace("www.", "")


def _clamp(value: float) -> float:
    return round(max(0.0, min(1.0, value)), 2)


def _string_value(value: object) -> str | None:
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
    if not isinstance(value, (int, float)):
        return 0.5
    return max(0.0, min(float(value), 1.0))


_AI_NATIVE_KEYWORDS = (
    "ia",
    "inteligência artificial",
    "artificial intelligence",
    "generativa",
    "generative",
    "llm",
    "agente",
    "agent",
    "copiloto",
    "copilot",
    "automação",
    "machine learning",
)

_NVIDIA_FIT_KEYWORDS = (
    "inferência",
    "inference",
    "latência",
    "latency",
    "gpu",
    "llm",
    "generativa",
    "dados",
    "data",
    "privacidade",
    "on-prem",
    "documentos",
    "voz",
    "vídeo",
)

_WRAPPER_RISK_KEYWORDS = (
    "openai",
    "chatgpt",
    "api",
    "llm",
    "generativa",
    "copiloto",
    "agente",
)


def _detect_sector(query: str) -> str:
    lowered = query.lower()
    sector_keywords = {
        "saúde": ("saúde", "health", "healthcare", "medicina", "hospital", "clínica"),
        "finanças": ("finanças", "finance", "fintech", "banco", "crédito", "risco"),
        "jurídico": ("jurídico", "legal", "advogado", "contrato", "compliance"),
        "educação": ("educação", "education", "edtech", "ensino", "aprendizado"),
        "indústria": ("indústria", "industrial", "manufatura", "fábrica", "iot"),
        "varejo": ("varejo", "retail", "ecommerce", "e-commerce", "commerce"),
        "agro": ("agro", "agricultura", "agritech", "campo", "fazenda"),
    }
    for sector, keywords in sector_keywords.items():
        if any(keyword in lowered for keyword in keywords):
            return sector

    return "IA aplicada"


def _country_label(country: str) -> str:
    lowered = country.lower()
    if lowered in {"brazil", "brasil", "br"}:
        return "Brasil"
    return country


def _suggested_queries(query: str, country: str, sector: str) -> tuple[str, ...]:
    return (
        f'{query} startup IA {country} 2026',
        f'"{sector}" "IA generativa" startup {country}',
        f'"{sector}" agentes de IA empresa {country}',
        f'"{sector}" LLM copiloto startup {country}',
        f'"{sector}" NVIDIA IA startup {country}',
        f'"{sector}" captação investimento IA {country}',
        f'"{sector}" vagas machine learning startup {country}',
    )


def _source_targets(sector: str) -> tuple[str, ...]:
    base_sources = [
        "Google Notícias e comunicados recentes da empresa",
        "LinkedIn de fundadores, empresa e vagas técnicas",
        "Crunchbase, Distrito, Sling Hub ou bases similares",
        "GitHub, documentação técnica, blog de engenharia e páginas de produto",
        "Eventos, acelerações, editais, NVIDIA Inception e programas de startups",
    ]
    sector_sources = {
        "saúde": "Hospitais, healthtech reports, ANVISA, HIMSS e cases clínicos públicos",
        "finanças": "Banco Central, CVM, FEBRABAN, Open Finance e comunicados de fintechs",
        "jurídico": "OAB, legaltech reports, páginas de produto e cases de compliance",
        "educação": "MEC, edtech reports, escolas, universidades e plataformas de ensino",
        "indústria": "ABDI, SENAI, indústria 4.0, manufatura avançada e automação",
        "varejo": "E-commerce Brasil, ABComm, marketplaces e cases de atendimento/precificação",
        "agro": "Embrapa, AgTech Garage, cooperativas, sensoriamento e agricultura de precisão",
    }
    fallback_source = "Relatórios setoriais, notícias e diretórios de startups"
    return tuple([sector_sources.get(sector, fallback_source)] + base_sources)


def _trend_signals(sector: str) -> tuple[str, ...]:
    return (
        f"Uso de agentes de IA em fluxos críticos de {sector.lower()}.",
        "Pressão de custo, latência ou escala em inferência.",
        "Dependência explícita de APIs de modelos fundacionais.",
        "Necessidade de privacidade, implantação dedicada ou ambiente on-prem.",
        "Evidência de avaliação, guardrails, RAG, fine-tuning ou dados proprietários.",
        "Contratações recentes para ML, infraestrutura, dados ou produto de IA.",
    )


def _evaluation_checklist() -> tuple[str, ...]:
    return (
        "A empresa tem produto de IA em produção, não apenas discurso de marketing?",
        "Há dados proprietários, workflow específico ou integração profunda com o domínio?",
        "Existe dor clara que NVIDIA resolve: inferência, GPU, latência, "
        "privacidade, RAG ou guardrails?",
        "A startup parece vulnerável a grandes laboratórios de IA ou tem defensibilidade própria?",
        "Há sinal recente de tração: clientes, investimento, vagas, lançamento ou parceria?",
    )


def _live_search_links(queries: tuple[str, ...]) -> tuple[LiveSearchLink, ...]:
    links: list[LiveSearchLink] = []
    for query in queries:
        encoded_query = quote_plus(query)
        links.append(
            LiveSearchLink(
                label=f"Google: {query}",
                url=f"https://www.google.com/search?q={encoded_query}",
            )
        )
        links.append(
            LiveSearchLink(
                label=f"Notícias: {query}",
                url=f"https://www.google.com/search?tbm=nws&q={encoded_query}",
            )
        )
        links.append(
            LiveSearchLink(
                label=f"LinkedIn: {query}",
                url=(
                    "https://www.linkedin.com/search/results/companies/"
                    f"?keywords={encoded_query}"
                ),
            )
        )
    return tuple(links)
