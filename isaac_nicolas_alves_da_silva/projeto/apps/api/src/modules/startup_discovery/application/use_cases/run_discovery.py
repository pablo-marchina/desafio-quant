"""Caso de uso principal: descobre startups em hubs publicos.

Dois modos de extracao (configurado em HubSource.extraction_mode):

  "url"  — extracao direta de URLs (InovAtiva, Abstartups):
    1. Extrator retorna URLs de startups.
    2. Cada URL e submetida diretamente como url_ingestion_job.
    3. DiscoverySubmission salvo por URL.

  "name" — extracao por nome + enriquecimento (100 Open Startups):
    1. Extrator retorna nomes, categorias e ranking (sem URL).
    2. Candidatos sao salvos como StartupDiscoveryCandidate (status=DISCOVERED).
    3. CandidateEnrichmentService busca site oficial via Tavily.
    4. Candidatos com official_site_confidence >= AUTO_SUBMIT_CONFIDENCE
       sao submetidos automaticamente como url_ingestion_job
       (status=SUBMITTED, url_ingestion_job_id preenchido).
    5. Candidatos abaixo do limiar ficam como REJECTED/FAILED para revisao.

Best-effort por hub: falha de um hub nao cancela os outros.
O run so falha inteiro se TODOS os hubs falharem.
"""

import unicodedata
import re
from typing import Callable

from apps.api.src.modules.startup_discovery.application.dto import (
    CandidateView,
    DiscoveredCandidateItem,
    DiscoveryRunView,
    StartupCandidate,
    SubmittedUrlView,
)
from apps.api.src.modules.startup_discovery.application.ports import (
    HubLinkExtractor,
    HubNameExtractor,
)
from apps.api.src.modules.startup_discovery.domain.entities import (
    DiscoveryRun,
    DiscoverySubmission,
    StartupDiscoveryCandidate,
)
from apps.api.src.modules.startup_discovery.domain.enums import CandidateStatus
from apps.api.src.modules.startup_discovery.domain.hub_registry import HUB_SOURCES
from apps.api.src.shared.logging import get_logger

logger = get_logger(__name__)

AUTO_SUBMIT_CONFIDENCE: float = 0.75
CONSULTANCY_TERMS = (
    "consultoria",
    "consulting",
    "consultancy",
    "agencia",
    "agência",
    "agency",
    "servicos de dados",
    "serviços de dados",
    "data services",
    "prestador de servico",
    "prestador de serviço",
    "service provider",
    "software house",
    "outsourcing",
    "desenvolvimento sob demanda",
)
PRODUCT_TERMS = (
    "produto",
    "product",
    "plataforma",
    "platform",
    "saas",
    "app",
    "api",
    "agent",
    "agente",
)


def _normalize_name(name: str) -> str:
    name = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]", "", name.lower())


def _normalize_text(text: str) -> str:
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    return text.lower()


def _is_consultancy_candidate(*parts: str | None) -> bool:
    text = _normalize_text(" ".join(part for part in parts if part))
    if not text:
        return False
    has_consultancy_signal = any(term in text for term in CONSULTANCY_TERMS)
    has_product_signal = any(term in text for term in PRODUCT_TERMS)
    return has_consultancy_signal and not has_product_signal


class RunStartupDiscovery:

    def __init__(
        self,
        *,
        uow_factory: Callable,
        extractors: dict[str, HubLinkExtractor],
        name_extractors: dict[str, HubNameExtractor] | None = None,
        url_ingestion_submitter,
        candidate_enricher=None,
        max_per_run: int = 20,
    ) -> None:
        self._uow_factory = uow_factory
        self._extractors = extractors
        self._name_extractors: dict[str, HubNameExtractor] = name_extractors or {}
        self._submitter = url_ingestion_submitter
        self._enricher = candidate_enricher
        self._max_per_run = max_per_run

    async def execute(self) -> DiscoveryRunView:
        run = DiscoveryRun()
        await self._save_run(run)

        run.start()
        await self._save_run(run)

        submitted_urls: list[SubmittedUrlView] = []
        hubs_processed = 0
        had_success = False
        hub_failures: list[str] = []
        total_candidates_discovered = 0
        total_candidates_enriched = 0

        for hub in HUB_SOURCES:
            remaining = self._max_per_run - len(submitted_urls)
            if remaining <= 0:
                break

            if hub.extraction_mode == "name":
                name_extractor = self._name_extractors.get(hub.extractor_type)
                if name_extractor is None:
                    logger.warning(
                        "no name extractor for hub, skipping",
                        extra={"hub": hub.name, "extractor_type": hub.extractor_type},
                    )
                    continue

                try:
                    discovered = await name_extractor.extract(
                        hub.listing_url, limit=remaining
                    )
                    had_success = True
                except Exception as exc:
                    failure_reason = f"{type(exc).__name__}: {exc}"
                    hub_failures.append(f"{hub.name}: {failure_reason}")
                    logger.warning(
                        "name extractor failed, skipping hub",
                        extra={"hub": hub.name, "reason": failure_reason},
                    )
                    continue

                hubs_processed += 1
                total_candidates_discovered += len(discovered)
                logger.info(
                    "name hub extracted",
                    extra={"hub": hub.name, "candidates_found": len(discovered)},
                )

                candidates = [
                    StartupDiscoveryCandidate(
                        run_id=run.id,
                        name=item.name,
                        normalized_name=_normalize_name(item.name),
                        discovery_source=hub.name,
                        discovery_source_url=hub.listing_url,
                        category=item.category,
                        rank=item.rank,
                        description=item.description,
                    )
                    for item in discovered
                ]
                for candidate in candidates:
                    if _is_consultancy_candidate(
                        candidate.name,
                        candidate.category,
                        candidate.description,
                    ):
                        candidate.reject("consultancy_or_service_provider")
                for candidate in candidates:
                    await self._save_candidate(candidate)

                if self._enricher is not None:
                    enrichable_candidates = [
                        candidate
                        for candidate in candidates
                        if candidate.status is CandidateStatus.DISCOVERED
                    ]
                    enriched = await self._enricher.enrich_batch(enrichable_candidates)
                    for candidate in enriched:
                        if candidate.status == CandidateStatus.ENRICHED:
                            total_candidates_enriched += 1
                        await self._save_candidate(candidate)

                    for candidate in enriched:
                        if (
                            candidate.status == CandidateStatus.ENRICHED
                            and candidate.official_site_confidence is not None
                            and candidate.official_site_confidence >= AUTO_SUBMIT_CONFIDENCE
                            and candidate.official_website_url
                        ):
                            try:
                                job_id = await self._submitter.submit(
                                    candidate.official_website_url,
                                    name=candidate.name,
                                )
                                candidate.mark_submitted(job_id)
                                await self._save_candidate(candidate)
                                submitted_urls.append(
                                    SubmittedUrlView(
                                        hub_name=hub.name,
                                        url=candidate.official_website_url,
                                        job_id=job_id,
                                        name=candidate.name,
                                    )
                                )
                                logger.info(
                                    "candidate auto-submitted",
                                    extra={
                                        "startup_name": candidate.name,
                                        "url": candidate.official_website_url,
                                        "confidence": candidate.official_site_confidence,
                                        "job_id": str(job_id),
                                    },
                                )
                            except Exception as exc:
                                logger.warning(
                                    "failed to submit enriched candidate",
                                    extra={
                                        "startup_name": candidate.name,
                                        "url": candidate.official_website_url,
                                        "reason": str(exc),
                                    },
                                )

            else:
                extractor = self._extractors.get(hub.extractor_type)
                if extractor is None:
                    logger.warning(
                        "no extractor for hub, skipping",
                        extra={"hub": hub.name, "extractor_type": hub.extractor_type},
                    )
                    continue

                try:
                    extracted = await extractor.extract(hub.listing_url, limit=remaining)
                    url_candidates = [_to_candidate(item) for item in extracted]
                    had_success = True
                except Exception as exc:
                    failure_reason = f"{type(exc).__name__}: {exc}"
                    hub_failures.append(f"{hub.name}: {failure_reason}")
                    logger.warning(
                        "hub extractor failed, skipping hub",
                        extra={"hub": hub.name, "reason": failure_reason},
                    )
                    continue

                hubs_processed += 1
                logger.info(
                    "url hub extracted",
                    extra={"hub": hub.name, "candidates_found": len(url_candidates)},
                )

                for candidate in url_candidates:
                    if _is_consultancy_candidate(
                        candidate.website_url,
                        candidate.name,
                        candidate.short_description,
                        candidate.declared_sector,
                    ):
                        logger.info(
                            "startup discovery candidate skipped as consultancy",
                            extra={
                                "hub": hub.name,
                                "url": candidate.website_url,
                                "startup_name": candidate.name,
                            },
                        )
                        continue
                    try:
                        job_id = await self._submitter.submit(
                            candidate.website_url,
                            name=candidate.name,
                        )
                        submission = DiscoverySubmission(
                            run_id=run.id,
                            hub_name=hub.name,
                            website_url=candidate.website_url,
                            job_id=job_id,
                            name=candidate.name,
                            hub_profile_url=candidate.hub_profile_url,
                            short_description=candidate.short_description,
                            declared_sector=candidate.declared_sector,
                        )
                        await self._save_submission(submission)
                        submitted_urls.append(_submission_to_view(submission))
                        logger.info(
                            "url_ingestion_job submitted",
                            extra={
                                "hub": hub.name,
                                "url": candidate.website_url,
                                "name": candidate.name,
                                "job_id": str(job_id),
                            },
                        )
                    except Exception as exc:
                        logger.warning(
                            "failed to submit url_ingestion_job",
                            extra={"url": candidate.website_url, "reason": str(exc)},
                        )

        if not had_success and HUB_SOURCES:
            details = "; ".join(hub_failures) if hub_failures else "sem detalhes"
            run.fail(f"Todos os hubs falharam na extracao. Detalhes: {details}")
        else:
            run.complete(
                hubs_processed=hubs_processed,
                urls_found=len(submitted_urls),
                jobs_submitted=len(submitted_urls),
                candidates_discovered=total_candidates_discovered,
                candidates_enriched=total_candidates_enriched,
            )

        await self._save_run(run)
        return _to_view(run, submitted_urls)

    async def _save_run(self, run: DiscoveryRun) -> None:
        async with self._uow_factory() as uow:
            await uow.repository.save(run)
            await uow.commit()

    async def _save_submission(self, submission: DiscoverySubmission) -> None:
        async with self._uow_factory() as uow:
            await uow.repository.save_submission(submission)
            await uow.commit()

    async def _save_candidate(self, candidate: StartupDiscoveryCandidate) -> None:
        async with self._uow_factory() as uow:
            await uow.candidate_repository.save(candidate)
            await uow.commit()


def _to_candidate(item: StartupCandidate | str) -> StartupCandidate:
    if isinstance(item, StartupCandidate):
        return item
    return StartupCandidate(website_url=item)


def _submission_to_view(submission: DiscoverySubmission) -> SubmittedUrlView:
    return SubmittedUrlView(
        hub_name=submission.hub_name,
        url=submission.website_url,
        job_id=submission.job_id,
        name=submission.name,
        hub_profile_url=submission.hub_profile_url,
        short_description=submission.short_description,
        declared_sector=submission.declared_sector,
    )


def _to_view(run: DiscoveryRun, submitted: list[SubmittedUrlView]) -> DiscoveryRunView:
    return DiscoveryRunView(
        id=run.id,
        status=run.status,
        hubs_processed=run.hubs_processed,
        urls_found=run.urls_found,
        jobs_submitted=run.jobs_submitted,
        candidates_discovered=run.candidates_discovered,
        candidates_enriched=run.candidates_enriched,
        error_message=run.error_message,
        created_at=run.created_at,
        completed_at=run.completed_at,
        submitted_urls=submitted,
    )


def _to_candidate_view(candidate: StartupDiscoveryCandidate) -> CandidateView:
    return CandidateView(
        id=candidate.id,
        run_id=candidate.run_id,
        name=candidate.name,
        normalized_name=candidate.normalized_name,
        discovery_source=candidate.discovery_source,
        category=candidate.category,
        rank=candidate.rank,
        description=candidate.description,
        official_website_url=candidate.official_website_url,
        official_site_confidence=candidate.official_site_confidence,
        enrichment_sources=candidate.enrichment_sources,
        status=candidate.status,
        rejection_reason=candidate.rejection_reason,
        url_ingestion_job_id=candidate.url_ingestion_job_id,
        created_at=candidate.created_at,
        updated_at=candidate.updated_at,
    )
