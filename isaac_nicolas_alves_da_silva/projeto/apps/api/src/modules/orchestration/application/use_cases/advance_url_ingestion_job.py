"""Caso de uso que avanca a maquina de estados de um url ingestion job.

Chamado a cada entrega da fila ``url_ingestion`` (worker). So avanca UM
passo por chamada: submete o proximo job downstream quando o atual
terminou, ou levanta ``UrlIngestionStillProcessingError`` para o
Dramatiq reentregar a mensagem mais tarde enquanto espera. Mesmo padrao
de retry-via-excecao ja usado por ``ExecuteEmbeddingJob`` para chunks
pendentes.

A etapa ``ANALYZING`` e diferente das anteriores: nao submete um job
assincrono de outro modulo para ficar consultando depois — startup,
evidencia, extract, classify, recommendations e briefing sao chamadas
sincronas (mesmo padrao que ``ExecuteAnalysisJob`` ja usa para
recommendations->briefing), entao a cadeia inteira roda numa unica
entrega. Falha aqui e terminal (``job.fail()``, sem relancar) — nao e o
padrao "ainda processando" usado para scraping/ingestion/embedding, que
sao jobs assincronos de outro modulo. As escritas intermediarias
(``link_startup``/``mark_evidence_attached``) existem para proteger
contra reentrega-por-crash do Dramatiq: se o processo morrer entre criar
a startup e salvar o job, a proxima entrega nao deve criar uma segunda
startup nem duplicar a evidencia.
"""

import re
from urllib.parse import urljoin, urlparse, urlunparse
from uuid import UUID

from apps.api.src.modules.orchestration.application.ports import (
    BriefingPort,
    DocumentContentView,
    EmbeddingsPort,
    EnrichmentSearchExecutorPort,
    EnrichmentSearchPlannerPort,
    IngestionPort,
    RecommendationsPort,
    ScrapingPort,
    StartupExtractionAttempt,
    StartupProfileSnapshot,
    StartupsPort,
    UrlIngestionTaskDispatcher,
)
from apps.api.src.modules.orchestration.application.unit_of_work import (
    AnalysisUnitOfWorkFactory,
)
from apps.api.src.modules.orchestration.domain.entities import UrlIngestionJob
from apps.api.src.modules.orchestration.domain.enums import UrlIngestionJobStatus
from apps.api.src.modules.orchestration.domain.exceptions import (
    UrlIngestionJobNotFoundError,
    UrlIngestionStillProcessingError,
)
from apps.api.src.shared.logging import bind_context, get_logger

STARTUP_EVIDENCE_SOURCE_TYPE = "startup_evidence"
MAX_EVIDENCE_TEXT_CHARS = 8000
MAX_ENRICHMENT_ROUNDS = 1

_TERMINAL_JOB_STATUSES = {
    UrlIngestionJobStatus.COMPLETED,
    UrlIngestionJobStatus.FAILED,
}
MAX_ENRICHMENT_URLS_PER_ROUND = 4
MAX_ENRICHMENT_SEARCH_QUERIES = 3
MAX_ENRICHMENT_SEARCH_RESULTS_PER_QUERY = 5

# Paths that commonly reveal tech stack, team, and traction.
# Ordenado por PROBABILIDADE DE EXISTIR primeiro (about/sobre/blog/carreiras
# existem em quase todo site; /product e /solution costumam ser 404 — foi a
# causa real da "parede de 404" observada na rodada das 12 startups). Como o
# slot same-domain agora e' reduzido quando a busca esta disponivel, a 1a
# entrada precisa ser a de maior chance de existir.
ENRICHMENT_PATHS = (
    "sobre",
    "about",
    "blog",
    "carreiras",
    "careers",
    "vagas",
    "trabalhe-conosco",
    "jobs",
    "technology",
    "engineering",
    "solucoes",
    "solutions",
    "product",
    "products",
    "platform",
    "team",
    "customers",
    "case-studies",
)
TRUSTED_ENRICHMENT_HOSTS = {
    "crunchbase.com",
    "www.crunchbase.com",
    "linkedin.com",
    "www.linkedin.com",
    "wellfound.com",
    "www.wellfound.com",
    # Bases de dados de startups / investimentos
    "angel.co",
    "pitchbook.com",
    "tracxn.com",
    "f6s.com",
    # Public job boards often expose stack and deployment hints.
    "gupy.io",
    "boards.greenhouse.io",
    "jobs.lever.co",
    "github.com",
    "www.github.com",
}
AI_EVIDENCE_TERMS = (
    " ai ",
    " ai-",
    " ai.",
    "artificial intelligence",
    "inteligencia artificial",
    "inteligência artificial",
    "machine learning",
    "deep learning",
    "generative ai",
    "gen ai",
    "llm",
    "large language model",
    "computer vision",
    "natural language",
    "nlp",
    "neural network",
    "model training",
    "model inference",
    "foundation model",
    "agentic",
    "automation with ai",
    "pytorch",
    "tensorflow",
    "cuda",
    "triton",
    "vllm",
    "requirements.txt",
    "package.json",
)
BLOCKED_ENRICHMENT_HOSTS = {
    # Redes sociais — conteudo fragmentado, sem informacao estruturada de empresa
    "facebook.com",
    "instagram.com",
    "linktr.ee",
    "tiktok.com",
    "threads.net",
    "twitter.com",
    "x.com",
    # Agregadores de conteudo — nao autoritativos sobre a empresa
    "reddit.com",
    "quora.com",
    "medium.com",
    "substack.com",
    "grokipedia.com",
    "wikipedia.org",
    # Video / streaming
    "youtube.com",
    "youtu.be",
    "vimeo.com",
    # Avaliacoes — util para cultura, nao para perfil tecnico de empresa
    "glassdoor.com",
    "indeed.com",
    "vagas.com.br",
    "catho.com.br",
    # SEO farms / diretórios de baixa qualidade
    "yellowpages.com",
    "yelp.com",
}
# Imprensa independente e ecossistema de inovacao BR — fonte PRIMARIA de
# enriquecimento. Noticia tem prosa real sobre produto, escala, funding e
# direcao de time (validado manualmente: foi o que fez Driva/NeuralMind
# funcionarem, enquanto home institucional + LinkedIn nao funcionaram).
# Pontuada ACIMA dos diretorios (f6s/wellfound), que retornam conteudo fino.
NEWS_ENRICHMENT_HOSTS = {
    # Imprensa de tecnologia / negocios / startups
    "exame.com",
    "braziljournal.com",
    "neofeed.com.br",
    "startups.com.br",
    "itforum.com.br",
    "baguete.com.br",
    "mobiletime.com.br",
    "diariodocomercio.com.br",
    "abcdacomunicacao.com.br",
    "economiasa.com.br",
    "tiinside.com.br",
    "convergenciadigital.com.br",
    "panoramamercantil.com.br",
    "revistapegn.globo.com",
    "valor.globo.com",
    "meioemensagem.com.br",
    "revistaempreende.com.br",
    "revistaempresarios.net",
    "channel360.com.br",
    "revistasegurancaeletronica.com.br",
    # Ecossistema de inovacao / hubs / aceleradoras
    "sanpedrovalley.org.br",
    "bhtec.org.br",
    "distrito.me",
    "startse.com",
    "brasilinovador.com.br",
    "aiotbrasil.com.br",
}

logger = get_logger(__name__)


# Generic page-type words that appear as fragments in HTML titles.
_GENERIC_PAGE_FRAGMENT_RE = re.compile(
    r"^(?:home|about(?:\s+us)?|quem\s+somos|inicio|"
    r"bem[- ]vindo(?:s)?|nossa\s+empresa|company|welcome|"
    r"official\s+site|website|contact(?:o)?|"
    r"products?|solutions?|servi[cç]os?|platform)$",
    re.IGNORECASE,
)

# Known multi-segment TLDs (order matters: longest first).
_MULTI_TLDS = ("com.br", "co.uk", "org.br", "net.br", "gov.br", "co.in")


def _domain_to_brand(hostname: str) -> str:
    """Extract a readable brand name from a hostname.

    'plat.econodata.com.br' -> 'Econodata'
    'www.aprix.ai'          -> 'Aprix'
    'app.datlo.io'          -> 'Datlo'
    """
    h = hostname.lower().removeprefix("www.")
    # Strip known multi-segment TLDs first
    for tld in _MULTI_TLDS:
        if h.endswith(f".{tld}"):
            h = h[: -(len(tld) + 1)]
            break
    # Remove any remaining TLD (.ai, .io, .com, etc.)
    if "." in h:
        h = h.rsplit(".", 1)[0]
    # Strip any leading subdomain (app., plat., api., staging., etc.)
    if "." in h:
        h = h.rsplit(".", 1)[-1]
    return h.capitalize() if h else hostname


def _clean_page_title(title: str) -> str:
    """Remove generic page-type fragments from an HTML title.

    'About us - Aprix Pricing'              -> 'Aprix Pricing'
    'Home | Econodata'                       -> 'Econodata'
    'NeuralMind – AI solutions'              -> 'NeuralMind'
    'Quem Somos - Morada.ai • Morada.ai'    -> 'Morada.ai'
    """
    for _ in range(3):  # up to 3 passes for compound titles
        prev = title
        for sep in (" - ", " | ", " – ", " — ", " • ", " / ", " \\ "):
            if sep in title:
                parts = [p.strip() for p in title.split(sep)]
                meaningful = [
                    p for p in parts if p and not _GENERIC_PAGE_FRAGMENT_RE.match(p)
                ]
                if meaningful:
                    title = min(meaningful, key=len)
                break  # only one separator per pass; restart from top
        if title == prev:
            break
    return title.strip()


def _derive_startup_name(*, title: str | None, url: str) -> str:
    hostname = urlparse(url).netloc
    brand_from_domain = _domain_to_brand(hostname) if hostname else url

    if title:
        cleaned = _clean_page_title(title)
        # Fall back to domain-derived name when the cleaned title is the hostname.
        if cleaned.lower() in (hostname.lower(), hostname.lower().removeprefix("www.")):
            return brand_from_domain
        # Fall back when cleaned title starts with the domain brand followed by a
        # descriptor word — e.g. "Aprix Pricing" from domain "aprix.ai" -> "Aprix".
        if (
            brand_from_domain
            and cleaned.lower().startswith(brand_from_domain.lower() + " ")
        ):
            return brand_from_domain
        return cleaned

    return brand_from_domain


def _normalize_url(url: str) -> str:
    parsed = urlparse(url.strip())
    scheme = parsed.scheme or "https"
    netloc = parsed.netloc.lower()
    path = parsed.path.rstrip("/") or "/"
    return urlunparse((scheme, netloc, path, "", "", ""))


def _same_domain_candidate_urls(source_url: str) -> list[str]:
    parsed = urlparse(source_url)
    if not parsed.netloc:
        return []

    base = urlunparse((parsed.scheme or "https", parsed.netloc, "/", "", "", ""))
    return [_normalize_url(urljoin(base, path)) for path in ENRICHMENT_PATHS]


# ---------------------------------------------------------------------------
# P0d — Extração de links reais do HTML da home
# ---------------------------------------------------------------------------

_HREF_RE = re.compile(r'href=["\']([^"\']+)["\']', re.IGNORECASE)

# Paths que levam a conteúdo substantivo sobre o produto/empresa
_ENRICHMENT_KEYWORD_RE = re.compile(
    r"(about|sobre|produto|product|platform|plataform|solution|solucao|"
    r"blog|tech|engineering|engenharia|team|equipe|carreira|career|vaga|"
    r"job|customer|cliente|case|feature|pricing|preco|api|docs|"
    r"documentation|how|why|partner|parceiro|resource|recurso)",
    re.IGNORECASE,
)

# Extensões de arquivo que não são páginas
_SKIP_EXT_RE = re.compile(
    r"\.(png|jpg|jpeg|gif|svg|ico|pdf|zip|mp4|mp3|css|js|woff2?|ttf|eot|map)$",
    re.IGNORECASE,
)

# Segmentos de path que não valem para enriquecimento
_SKIP_SEGMENT_RE = re.compile(
    r"^(login|signin|sign-in|signup|sign-up|register|logout|auth|"
    r"dashboard|app|admin|cdn|static|assets|images|img|fonts|"
    r"privacy|privacidade|terms|termos|cookies|sitemap|rss)$",
    re.IGNORECASE,
)


def _extract_internal_links(html: str, base_url: str) -> list[str]:
    """Extrai links internos relevantes do HTML da home (P0d).

    Retorna URLs normalizadas do mesmo domínio, ordenadas por relevância
    (páginas de produto/sobre/blog/tech primeiro), sem media/auth/assets.
    """
    parsed_base = urlparse(base_url)
    base_host = parsed_base.netloc.lower().removeprefix("www.")

    seen: set[str] = set()
    scored: list[tuple[int, str]] = []

    for match in _HREF_RE.finditer(html):
        href = match.group(1).strip()

        # Descarta URIs especiais
        if href.startswith(("data:", "mailto:", "tel:", "javascript:", "#")):
            continue

        try:
            absolute = urljoin(base_url, href)
            parsed = urlparse(absolute)
        except Exception:
            continue

        # Apenas mesmo domínio
        link_host = parsed.netloc.lower().removeprefix("www.")
        if link_host != base_host:
            continue

        path = parsed.path
        if not path or path == "/":
            continue

        # Descarta arquivos de mídia/estilo
        if _SKIP_EXT_RE.search(path):
            continue

        # Normaliza sem query/fragment
        normalized = _normalize_url(
            urlunparse((parsed.scheme, parsed.netloc, path, "", "", ""))
        )
        if normalized in seen:
            continue
        seen.add(normalized)

        # Descarta paths com segmentos irrelevantes
        segments = [s for s in path.strip("/").split("/") if s]
        if any(_SKIP_SEGMENT_RE.match(s) for s in segments):
            continue

        # Pontua por relevância do path
        score = 10 if _ENRICHMENT_KEYWORD_RE.search(path) else 0
        scored.append((score, normalized))

    # Relevantes primeiro; dentro do mesmo score, paths mais curtos (mais gerais)
    scored.sort(key=lambda x: (-x[0], len(x[1])))
    return [url for _, url in scored]


def _hostname(url: str) -> str:
    return urlparse(url).netloc.lower().removeprefix("www.")


def _is_news_host(host: str) -> bool:
    """Imprensa independente / hub de inovacao / fonte institucional publica.

    Inclui a allowlist curada (``NEWS_ENRICHMENT_HOSTS``) e dominios
    governamentais/academicos (.gov.br, .edu.br, universidades), que publicam
    releases substantivos sobre startups (ex.: parana.pr.gov.br, unicamp.br).
    """
    if host in NEWS_ENRICHMENT_HOSTS:
        return True
    if any(host == h or host.endswith(f".{h}") for h in NEWS_ENRICHMENT_HOSTS):
        return True
    return (
        host.endswith(".gov.br")
        or host.endswith(".edu.br")
        or host.endswith(".ac.uk")
        or host.endswith(".unicamp.br")
        or host.endswith(".usp.br")
    )


def _startup_terms(name: str) -> list[str]:
    return [
        term
        for term in (
            name.lower()
            .replace(".", " ")
            .replace("-", " ")
            .replace("_", " ")
            .split()
        )
        if len(term) >= 4
    ]


def _has_ai_evidence_signal(text: str) -> bool:
    normalized = f" {text.lower()} "
    return any(term in normalized for term in AI_EVIDENCE_TERMS)


def _score_external_candidate(
    *,
    url: str,
    startup_name: str,
    source_url: str,
    title: str | None = None,
    snippet: str | None = None,
) -> int:
    host = _hostname(url)
    if host in BLOCKED_ENRICHMENT_HOSTS:
        return -1

    source_host = _hostname(source_url)
    if host == source_host or host.endswith(f".{source_host}"):
        base_score = 50
        searchable_text = " ".join([url, title or "", snippet or ""])
        return base_score + (20 if _has_ai_evidence_signal(searchable_text) else 0)

    # Noticia independente / fonte institucional: fonte PRIMARIA. Pontuada
    # acima dos diretorios (90) para vencer o slot limitado de enriquecimento.
    # Exige o nome da startup no texto, para nao puxar indices/home de portal.
    if _is_news_host(host):
        searchable_text = " ".join([url, title or "", snippet or ""])
        terms = _startup_terms(startup_name)
        if terms and any(term in searchable_text.lower() for term in terms):
            return 95 + (20 if _has_ai_evidence_signal(searchable_text) else 0)
        return -1

    is_trusted = (
        host in TRUSTED_ENRICHMENT_HOSTS
        or host.endswith(".gupy.io")
        or host.endswith(".greenhouse.io")
        or host.endswith(".lever.co")
        or host.endswith("github.com")
        or host.endswith(".linkedin.com")
    )
    if is_trusted:
        # LinkedIn (qualquer subdominio regional, ex: br.linkedin.com):
        # paginas de empresa e vagas sao uteis; perfis individuais (/in/) nao.
        if host.endswith("linkedin.com") and not any(
            segment in url.lower() for segment in ("/company/", "/jobs/")
        ):
            return -1
        searchable_text = " ".join([url, title or "", snippet or ""])
        if host.endswith("github.com"):
            terms = _startup_terms(startup_name)
            searchable_text_lower = searchable_text.lower()
            if not terms or not any(term in searchable_text_lower for term in terms):
                return -1
        return 90 + (20 if _has_ai_evidence_signal(searchable_text) else 0)

    terms = _startup_terms(startup_name)
    searchable_text = " ".join([url, title or "", snippet or ""])
    searchable_text_lower = searchable_text.lower()
    if terms and any(term in searchable_text_lower for term in terms):
        return 60 + (20 if _has_ai_evidence_signal(searchable_text) else 0)

    return -1


def _is_weak_source_failure(reason: str | None) -> bool:
    if not reason:
        return False

    normalized = reason.lower()
    return "rejeitado" in normalized or "mais fontes" in normalized


def _deterministic_enrichment_queries(
    *, startup_name: str, missing_signals: list[str]
) -> list[str]:
    """Queries de enriquecimento, NOTICIA-FIRST (ordem importa).

    A primeira query preenche os primeiros slots; por isso a busca de
    noticia/lancamento/investimento vem antes (foi a fonte que funcionou no
    teste manual: Driva via abcdacomunicacao, NeuralMind via bhtec). GitHub
    e funding vem em seguida; o portugues vem primeiro porque o alvo sao
    startups brasileiras.
    """
    missing_text = " ".join(missing_signals)
    return [
        f'"{startup_name}" startup IA notícia lançamento investimento rodada',
        f'"{startup_name}" Brasil inteligência artificial produto clientes',
        f'"{startup_name}" GitHub Python PyTorch machine learning modelo',
        f'"{startup_name}" startup fundadores funding clientes {missing_text}',
        f'"{startup_name}" Brazil generative AI LLM startup',
    ]


def _unique_non_empty(items: list[str]) -> list[str]:
    seen: set[str] = set()
    unique: list[str] = []
    for item in items:
        normalized = item.strip()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        unique.append(normalized)
    return unique


def _key_missing_fields(profile: StartupProfileSnapshot) -> list[str]:
    """Campos-chave que movem a recomendacao e que ainda estao desconhecidos.

    Funcao pura extraida para ser testavel sem instanciar o use case.
    """
    return [
        label
        for label, value in (
            ("ai_workload_type", profile.ai_workload_type),
            ("deployment_stage", profile.deployment_stage),
            ("gpu_need", profile.gpu_need),
        )
        if value == "unknown"
    ]


def _recommendation_blocking_missing_fields(
    profile: StartupProfileSnapshot,
) -> list[str]:
    """Campos minimos para recomendar sem cair em palpite fraco."""
    return [
        label
        for label, value in (
            ("ai_workload_type", profile.ai_workload_type),
            ("deployment_stage", profile.deployment_stage),
        )
        if value in {None, "", "unknown", "none", "null"}
    ]


class AdvanceUrlIngestionJob:

    def __init__(
        self,
        uow_factory: AnalysisUnitOfWorkFactory,
        scraping_port: ScrapingPort,
        ingestion_port: IngestionPort,
        embeddings_port: EmbeddingsPort,
        startups_port: StartupsPort,
        recommendations_port: RecommendationsPort,
        briefing_port: BriefingPort,
        task_dispatcher: UrlIngestionTaskDispatcher,
        search_planner_port: EnrichmentSearchPlannerPort | None = None,
        search_executor_port: EnrichmentSearchExecutorPort | None = None,
    ) -> None:
        self._uow_factory = uow_factory
        self._scraping_port = scraping_port
        self._ingestion_port = ingestion_port
        self._embeddings_port = embeddings_port
        self._startups_port = startups_port
        self._recommendations_port = recommendations_port
        self._briefing_port = briefing_port
        self._task_dispatcher = task_dispatcher
        self._search_planner_port = search_planner_port
        self._search_executor_port = search_executor_port

    async def execute(self, *, job_id: UUID) -> None:
        job = await self._get(job_id)

        with bind_context(job_id=str(job_id)):
            logger.info(
                "advancing url ingestion job", extra={"status": job.status.value}
            )

            if job.status is UrlIngestionJobStatus.PENDING:
                scraping_job_id = await self._scraping_port.submit(
                    job.url, source_type=job.source_type
                )
                job.start_scraping(scraping_job_id)
                await self._save(job)
                raise UrlIngestionStillProcessingError("Scraping submetido.")

            if job.status is UrlIngestionJobStatus.SCRAPING:
                assert job.scraping_job_id is not None
                status = await self._scraping_port.get_status(job.scraping_job_id)
                if status.is_failed:
                    reason = status.error_message or "Scraping falhou."
                    logger.warning(
                        "scraping failed, failing url ingestion job",
                        extra={"reason": reason},
                    )
                    await self._try_schedule_enrichment_after_scraping_failure(
                        job,
                        reason=reason,
                    )
                    job.fail(reason)
                    await self._save(job)
                    return
                if not status.is_done:
                    raise UrlIngestionStillProcessingError("Scraping em andamento.")

                if status.result_id is None:
                    reason = (
                        status.error_message
                        or "Scraping concluiu sem scraping_result_id."
                    )
                    logger.warning(
                        "scraping finished without result, failing url ingestion job",
                        extra={"reason": reason},
                    )
                    await self._try_schedule_enrichment_after_scraping_failure(
                        job,
                        reason=reason,
                    )
                    job.fail(reason)
                    await self._save(job)
                    return
                ingestion_job_id = await self._ingestion_port.submit(
                    status.result_id,
                    source_type=job.source_type,
                )
                job.start_ingesting(
                    scraping_result_id=status.result_id,
                    ingestion_job_id=ingestion_job_id,
                )
                await self._save(job)
                raise UrlIngestionStillProcessingError("Ingestion submetido.")

            if job.status is UrlIngestionJobStatus.INGESTING:
                assert job.ingestion_job_id is not None
                status = await self._ingestion_port.get_status(job.ingestion_job_id)
                if status.is_failed:
                    logger.warning(
                        "ingestion failed, failing url ingestion job",
                        extra={"reason": status.error_message},
                    )
                    job.fail(status.error_message or "Ingestion falhou.")
                    await self._save(job)
                    return
                if not status.is_done:
                    raise UrlIngestionStillProcessingError("Ingestion em andamento.")

                if status.result_id is None:
                    reason = (
                        status.error_message
                        or "Ingestion concluiu sem document_id."
                    )
                    logger.warning(
                        "ingestion finished without result, failing url ingestion job",
                        extra={"reason": reason},
                    )
                    job.fail(reason)
                    await self._save(job)
                    return
                embedding_job_id = await self._embeddings_port.submit(
                    status.result_id
                )
                job.start_embedding(
                    document_id=status.result_id,
                    embedding_job_id=embedding_job_id,
                )
                await self._save(job)
                raise UrlIngestionStillProcessingError("Embedding submetido.")

            if job.status is UrlIngestionJobStatus.EMBEDDING:
                assert job.embedding_job_id is not None
                status = await self._embeddings_port.get_status(job.embedding_job_id)
                if status.is_failed:
                    logger.warning(
                        "embedding failed, failing url ingestion job",
                        extra={"reason": status.error_message},
                    )
                    job.fail(status.error_message or "Embedding falhou.")
                    await self._save(job)
                    return
                if not status.is_done:
                    raise UrlIngestionStillProcessingError("Embedding em andamento.")

                await self._cleanup_superseded_vectors(job)

                if job.source_type != STARTUP_EVIDENCE_SOURCE_TYPE:
                    job.complete()
                    await self._save(job)
                    return

                job.start_analyzing()
                await self._save(job)
                raise UrlIngestionStillProcessingError(
                    "Embedding concluido, iniciando analise."
                )

            if job.status is UrlIngestionJobStatus.ANALYZING:
                assert job.scraping_result_id is not None
                try:
                    await self._run_analysis(job)
                except UrlIngestionStillProcessingError:
                    # Pai aguardando filhos de enriquecimento: re-enfileira,
                    # NAO falha. Mesmo padrao das fases scraping/ingestion.
                    raise
                except Exception as error:
                    logger.warning(
                        "analysis failed, failing url ingestion job",
                        extra={"reason": str(error)},
                    )
                    job.fail(str(error))
                    await self._save(job)
                    return

                job.complete()
                await self._save(job)
                await self._dispatch_parent_after_enrichment_child(job)
                logger.info(
                    "url ingestion job completed",
                    extra={
                        "startup_id": str(job.startup_id),
                        "recommendation_count": job.recommendation_count,
                        "briefing_id": str(job.briefing_id),
                    },
                )
                return

            # COMPLETED/FAILED: estado terminal, nada a fazer.
            return

    async def _try_schedule_enrichment_after_scraping_failure(
        self,
        job: UrlIngestionJob,
        *,
        reason: str,
    ) -> None:
        if job.source_type != STARTUP_EVIDENCE_SOURCE_TYPE:
            return
        if job.enrichment_round >= MAX_ENRICHMENT_ROUNDS:
            return
        if not _is_weak_source_failure(reason):
            return

        try:
            if job.startup_id is None:
                startup_id = await self._startups_port.create_startup(
                    name=_derive_startup_name(title=None, url=job.url),
                    website_url=job.url,
                )
                job.link_startup(startup_id)
                await self._save(job)

            enrichment_job_ids = await self._schedule_enrichment_if_needed(
                job,
                content=None,
            )
            if enrichment_job_ids:
                logger.info(
                    "scheduled enrichment after weak source scraping failure",
                    extra={"count": len(enrichment_job_ids)},
                )
        except Exception as error:
            logger.warning(
                "failed to schedule enrichment after scraping failure",
                extra={"reason": str(error)},
            )

    async def _run_analysis(self, job: UrlIngestionJob) -> None:
        assert job.scraping_result_id is not None
        content = await self._ingestion_port.get_document_content(
            job.scraping_result_id
        )

        if job.startup_id is None:
            name = _derive_startup_name(
                title=content.title if content else None, url=job.url
            )
            startup_id = await self._startups_port.create_startup(
                name=name, website_url=job.url
            )
            job.link_startup(startup_id)
            await self._save(job)
            logger.info(
                "startup created from url ingestion job",
                extra={"startup_id": str(startup_id)},
            )

        assert job.startup_id is not None

        with bind_context(startup_id=str(job.startup_id)):
            if not job.evidence_attached:
                notes = (
                    content.clean_text[:MAX_EVIDENCE_TEXT_CHARS] if content else None
                )
                title = content.title if content else None
                await self._startups_port.attach_evidence(
                    startup_id=job.startup_id,
                    scraping_result_id=job.scraping_result_id,
                    source_url=job.url,
                    title=title,
                    notes=notes,
                )
                job.mark_evidence_attached()
                await self._save(job)
                logger.info("evidence attached to startup")

            # --- Coordenacao do enriquecimento: o pai (round 0) e o DONO UNICO
            # da recomendacao/briefing. Filhos so coletam evidencia. Isso elimina
            # a corrida do "ultimo irmao" (duas fontes terminando juntas adiavam
            # ambas, orfanando a recomendacao).
            if job.enrichment_round > 0:
                # Filho de enriquecimento: evidencia ja anexada acima; nao recomenda.
                logger.info("enrichment child collected evidence; parent will finalize")
                return

            children = await self._list_enrichment_children(job)

            if not children:
                # Primeira passada do pai: extrai, classifica, agenda enriquecimento.
                logger.info("running extraction (best-effort)")
                extraction_attempt = await self._startups_port.try_extract(
                    job.startup_id
                )
                logger.info("running classification (best-effort)")
                await self._startups_port.try_classify(job.startup_id)

                enrichment_job_ids = await self._schedule_enrichment_if_needed(
                    job, content=content
                )
                if enrichment_job_ids:
                    logger.info(
                        "analysis deferred until enrichment sources complete",
                        extra={"count": len(enrichment_job_ids)},
                    )
                    raise UrlIngestionStillProcessingError(
                        "Aguardando fontes de enriquecimento."
                    )
                # Sem enriquecimento necessario -> segue direto para recomendacao.
            else:
                # Passadas seguintes do pai: espera TODOS os filhos terminarem.
                await self._complete_collected_enrichment_children(children)
                if any(c.status not in _TERMINAL_JOB_STATUSES for c in children):
                    raise UrlIngestionStillProcessingError(
                        "Aguardando filhos de enriquecimento."
                    )
                # Filhos terminaram: re-extrai/classifica com a evidencia nova.
                logger.info("running extraction after enrichment (best-effort)")
                extraction_attempt = await self._startups_port.try_extract(
                    job.startup_id
                )
                logger.info("running classification after enrichment (best-effort)")
                await self._startups_port.try_classify(job.startup_id)

            # Dono unico roda recomendacao + briefing UMA vez. Se o worker cair
            # depois de recommendations e antes do briefing, o retry reaproveita
            # o count ja persistido.
            if job.recommendations_done:
                recommendation_count = job.recommendation_count or 0
                logger.info(
                    "recommendations already generated; skipping regeneration",
                    extra={"recommendation_count": recommendation_count},
                )
            else:
                await self._ensure_profile_ready_for_recommendations(
                    job,
                    extraction_attempt=extraction_attempt,
                )
                recommendation_count = await self._recommendations_port.generate(
                    job.startup_id
                )
                job.record_recommendations(recommendation_count)
                await self._save(job)
                logger.info(
                    "recommendations generated",
                    extra={"recommendation_count": recommendation_count},
                )

            briefing_id = await self._briefing_port.generate(job.startup_id)
            logger.info("briefing generated", extra={"briefing_id": str(briefing_id)})
            job.record_analysis_result(
                recommendation_count=recommendation_count, briefing_id=briefing_id
            )

    async def _ensure_profile_ready_for_recommendations(
        self,
        job: UrlIngestionJob,
        *,
        extraction_attempt: StartupExtractionAttempt,
    ) -> None:
        assert job.startup_id is not None

        profile = await self._startups_port.get_profile(job.startup_id)
        missing = _recommendation_blocking_missing_fields(profile)
        if not missing:
            return

        reason = (
            extraction_attempt.error_message
            or "extracao completou sem preencher os campos minimos"
        )
        status = (
            "timeout"
            if extraction_attempt.timed_out
            else "indisponivel"
            if extraction_attempt.unavailable
            else "falhou"
            if not extraction_attempt.succeeded
            else "incompleta"
        )
        raise RuntimeError(
            "Perfil estruturado de IA incompleto apos consolidar as evidencias "
            f"ja anexadas; campos criticos ausentes: {', '.join(missing)}. "
            f"Status da extracao: {status}. Motivo: {reason}. "
            "Recomendacoes nao foram geradas para evitar briefing fraco."
        )

    async def _list_enrichment_children(
        self, job: UrlIngestionJob
    ) -> list[UrlIngestionJob]:
        """Jobs de enriquecimento filhos deste job (mesma startup, parent=este)."""
        if job.startup_id is None:
            return []
        async with self._uow_factory() as uow:
            jobs = await uow.url_ingestion_job_repository.list_by_startup_id(
                job.startup_id
            )
        return [j for j in jobs if j.parent_job_id == job.id]

    async def _complete_collected_enrichment_children(
        self, children: list[UrlIngestionJob]
    ) -> None:
        """Fecha filhos que ja anexaram evidencia, mas ficaram em ANALYZING.

        Se o worker cair entre ``mark_evidence_attached`` e ``complete()``, o pai
        ficava esperando um filho que ja tinha cumprido sua unica funcao.
        """

        for child in children:
            if (
                child.status is UrlIngestionJobStatus.ANALYZING
                and child.enrichment_round > 0
                and child.evidence_attached
            ):
                child.complete()
                await self._save(child)

    async def _schedule_enrichment_if_needed(
        self,
        job: UrlIngestionJob,
        *,
        content: DocumentContentView | None,
    ) -> list[UUID]:
        if job.startup_id is None:
            return []
        if job.enrichment_round >= MAX_ENRICHMENT_ROUNDS:
            return []

        profile = await self._startups_port.get_profile(job.startup_id)

        # Parada por CAMPOS-CHAVE: enriquece enquanto algum campo que move a
        # recomendacao estiver desconhecido (workload, estagio, GPU). O teto
        # MAX_ENRICHMENT_ROUNDS garante terminacao mesmo quando o dado nunca
        # aparece em fonte publica.
        key_missing = _key_missing_fields(profile)

        # Para quando os campos-chave ja estao preenchidos (perfil "bom o
        # suficiente"), mesmo que founders/clientes faltem — esses sao pouco
        # recuperaveis publicamente e nao mudam a recomendacao.
        if not key_missing:
            return []

        # founders/funding/customers nao disparam enriquecimento sozinhos:
        # entram apenas como dica adicional de busca quando ja vamos enriquecer
        # por um campo-chave.
        basic_missing = [
            label
            for label, is_missing in (
                ("founders", not profile.founders),
                ("funding_stage", profile.funding_stage is None),
                ("customers", not profile.customers),
            )
            if is_missing
        ]
        missing_signals = [*key_missing, *basic_missing]

        async with self._uow_factory() as uow:
            existing_jobs = await uow.url_ingestion_job_repository.list_by_startup_id(
                job.startup_id
            )

        known_urls = {
            _normalize_url(url)
            for url in [
                job.url,
                *(profile.evidence_urls),
                *(item.url for item in existing_jobs),
            ]
            if url
        }
        # P0d — tenta extrair links reais do HTML já raspado antes de chutar paths.
        # Best-effort: qualquer falha (sem result_id, DB indisponível, HTML None)
        # cai silenciosamente no fallback de paths fixos.
        extracted_html_links: list[str] = []
        if job.scraping_result_id is not None:
            try:
                html = await self._scraping_port.get_html(job.scraping_result_id)
                if html:
                    extracted_html_links = _extract_internal_links(html, job.url)
            except Exception as _html_err:
                logger.debug(
                    "could not extract internal links from html",
                    extra={"reason": str(_html_err)},
                )

        # Quando a busca esta disponivel, os paths same-domain sao apenas um
        # palpite (e em geral 404 — a "parede de 404" das 12 startups). Por
        # isso reservamos s o' 1 slot para o palpite same-domain de maior chance
        # (about/sobre, ja' reordenados) e deixamos os 3 restantes para a busca
        # noticia-first. Sem busca, mantem o fallback same-domain completo.
        search_available = (
            self._search_planner_port is not None
            and self._search_executor_port is not None
        )
        same_domain_limit = 1 if search_available else MAX_ENRICHMENT_URLS_PER_ROUND
        candidates = self._same_domain_enrichment_urls(
            profile_website_url=profile.website_url,
            job_url=job.url,
            known_urls=known_urls,
            candidates=[],
            extracted_links=extracted_html_links,
        )[:same_domain_limit]

        external_candidates = await self._find_external_enrichment_urls(
            job=job,
            profile=profile,
            missing_signals=missing_signals,
            known_urls=known_urls,
            content=content,
        )
        candidates.extend(
            url
            for url in external_candidates
            if url not in known_urls and url not in candidates
        )
        candidates = candidates[:MAX_ENRICHMENT_URLS_PER_ROUND]
        if not candidates:
            return []

        created_jobs = [
            UrlIngestionJob(
                url=url,
                source_type=STARTUP_EVIDENCE_SOURCE_TYPE,
                startup_id=job.startup_id,
                parent_job_id=job.id,
                enrichment_round=job.enrichment_round + 1,
            )
            for url in candidates
        ]
        async with self._uow_factory() as uow:
            for enrichment_job in created_jobs:
                await uow.url_ingestion_job_repository.save(enrichment_job)
            await uow.commit()

        dispatched_job_ids: list[UUID] = []
        for enrichment_job in created_jobs:
            try:
                await self._task_dispatcher.dispatch(job_id=enrichment_job.id)
                dispatched_job_ids.append(enrichment_job.id)
            except Exception as error:
                logger.warning(
                    "failed to dispatch enrichment url ingestion job",
                    extra={
                        "enrichment_job_id": str(enrichment_job.id),
                        "reason": str(error),
                    },
                )

        logger.info(
            "startup profile incomplete; scheduled enrichment sources",
            extra={
                "missing_signals": missing_signals,
                "urls": [enrichment_job.url for enrichment_job in created_jobs],
            },
        )
        return dispatched_job_ids

    async def _dispatch_parent_after_enrichment_child(
        self, job: UrlIngestionJob
    ) -> None:
        if job.parent_job_id is None:
            return

        try:
            await self._task_dispatcher.dispatch(job_id=job.parent_job_id)
            logger.info(
                "parent url ingestion job requeued after enrichment child completed",
                extra={"parent_job_id": str(job.parent_job_id)},
            )
        except Exception as error:
            logger.warning(
                "failed to requeue parent url ingestion job after enrichment child",
                extra={
                    "parent_job_id": str(job.parent_job_id),
                    "child_job_id": str(job.id),
                    "reason": str(error),
                },
            )

    async def _find_external_enrichment_urls(
        self,
        *,
        job: UrlIngestionJob,
        profile: StartupProfileSnapshot,
        missing_signals: list[str],
        known_urls: set[str],
        content: DocumentContentView | None,
    ) -> list[str]:
        if self._search_planner_port is None or self._search_executor_port is None:
            return []

        known_terms = [
            term
            for term in [
                profile.name,
                *(profile.founders),
                *(profile.customers),
                profile.funding_stage,
            ]
            if term
        ]
        try:
            queries = await self._search_planner_port.plan_queries(
                startup_name=profile.name,
                source_url=job.url,
                source_title=content.title if content else None,
                raw_text=content.clean_text if content else "",
                missing_signals=missing_signals,
                known_terms=known_terms,
                excluded_urls=sorted(known_urls),
                max_queries=MAX_ENRICHMENT_SEARCH_QUERIES,
            )
        except Exception as error:
            logger.warning(
                "failed to plan enrichment searches",
                extra={"reason": str(error)},
            )
            queries = []

        queries = _unique_non_empty(
            [
                *_deterministic_enrichment_queries(
                    startup_name=profile.name,
                    missing_signals=missing_signals,
                ),
                *queries,
            ]
        )

        candidates: list[str] = []
        for query in queries:
            if len(candidates) >= MAX_ENRICHMENT_URLS_PER_ROUND:
                break
            try:
                results = await self._search_executor_port.search(
                    query,
                    excluded_urls=sorted(known_urls | set(candidates)),
                    max_results=MAX_ENRICHMENT_SEARCH_RESULTS_PER_QUERY,
                )
            except Exception as error:
                logger.warning(
                    "failed to execute enrichment search",
                    extra={"query": query, "reason": str(error)},
                )
                continue

            scored_results = sorted(
                (
                    (
                        _score_external_candidate(
                            url=_normalize_url(result.url),
                            startup_name=profile.name,
                            source_url=job.url,
                            title=result.title,
                            snippet=result.snippet,
                        ),
                        _normalize_url(result.url),
                    )
                    for result in results
                ),
                reverse=True,
            )
            for score, normalized_url in scored_results:
                if score < 0:
                    continue
                if (
                    normalized_url not in known_urls
                    and normalized_url not in candidates
                ):
                    candidates.append(normalized_url)
                if len(candidates) >= MAX_ENRICHMENT_URLS_PER_ROUND:
                    break

        return candidates

    def _same_domain_enrichment_urls(
        self,
        *,
        profile_website_url: str | None,
        job_url: str,
        known_urls: set[str],
        candidates: list[str],
        extracted_links: list[str] | None = None,
    ) -> list[str]:
        # P0d: quando temos links reais do HTML, usamos eles em vez de adivinhar.
        # Fallback para ENRICHMENT_PATHS quando o HTML não estava disponível.
        source_urls = (
            extracted_links
            if extracted_links
            else _same_domain_candidate_urls(profile_website_url or job_url)
        )
        return [
            url
            for url in source_urls
            if url not in known_urls and url not in candidates
        ]

    async def _cleanup_superseded_vectors(self, job: UrlIngestionJob) -> None:
        """Remove vetores Qdrant de scrapes anteriores da mesma URL.

        Re-scrape apos o cache de ``SCRAPING_RESULT_CACHE_TTL`` (scraping)
        expirar cria um ``Document`` novo para a mesma URL; sem esta
        limpeza, o ``Document`` antigo (e seus vetores no Qdrant) fica
        orfao para sempre. Best-effort: falha aqui nao impede o job atual
        de concluir, so deixa o vetor orfao pra uma limpeza futura.
        """

        async with self._uow_factory() as uow:
            previous_jobs = await uow.url_ingestion_job_repository.list_completed_by_url(
                job.url
            )

        superseded_document_ids = {
            previous.document_id
            for previous in previous_jobs
            if previous.id != job.id
            and previous.document_id is not None
            and previous.document_id != job.document_id
        }
        for document_id in superseded_document_ids:
            try:
                await self._embeddings_port.delete_vectors_for_document(document_id)
                logger.info(
                    "deleted superseded vectors from previous scrape",
                    extra={"document_id": str(document_id)},
                )
            except Exception as error:
                logger.warning(
                    "failed to delete superseded vectors",
                    extra={"document_id": str(document_id), "reason": str(error)},
                )

    async def _get(self, job_id: UUID) -> UrlIngestionJob:
        async with self._uow_factory() as uow:
            job = await uow.url_ingestion_job_repository.get_by_id(job_id)
            if job is None:
                raise UrlIngestionJobNotFoundError(
                    f"UrlIngestionJob {job_id} nao encontrado."
                )
            return job

    async def _save(self, job: UrlIngestionJob) -> None:
        async with self._uow_factory() as uow:
            await uow.url_ingestion_job_repository.save(job)
            await uow.commit()
