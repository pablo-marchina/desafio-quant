"""Orquestração principal da coleta e validação de conteúdo."""

import asyncio
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from urllib.parse import urlparse
from uuid import UUID

from apps.api.src.shared.logging import get_logger

_logger = get_logger("scraping.pipeline")

from apps.api.src.modules.scraping.domain.entities import ScrapingAttempt, ScrapingResult
from apps.api.src.modules.scraping.domain.enums import (
    AgentInvestigationDecision,
    AttemptStatus,
    SemanticReviewDecision,
    ValidationDecision,
)
from apps.api.src.modules.scraping.domain.exceptions import (
    ContentRejectedError,
    GlobalScrapingLimitExceededError,
    MoreSourcesRequiredError,
    RecoverableScrapingError,
    ScrapingFailedError,
    SemanticValidationError,
)
from apps.api.src.modules.scraping.domain.policies import (
    CIRCUIT_BREAKER_WINDOW_HOURS,
    LLMReviewPolicy,
    ValidationDecisionPolicy,
    is_circuit_open,
)
from apps.api.src.modules.scraping.domain.repositories import ScrapingAttemptRepository

from .dto import InvestigationInput, ScrapingInput, SemanticValidationInput
from .ports import DeterministicValidator, SemanticInvestigator, SemanticValidator
from .quality_scoring_service import QualityScoringService
from .scraping_limits import PipelineLimits
from .semantic_confidence_service import SemanticConfidenceService
from .strategy_selector import ScrapingStrategySelector


class ScrapingPipeline:
    """Coordena componentes especializados sem implementar o trabalho deles.

    A pipeline não conhece BeautifulSoup e não calcula scores diretamente. Ela
    apenas organiza a ordem das operações e entrega cada tarefa ao componente
    responsável.
    """

    def __init__(
        self,
        strategy_selector: ScrapingStrategySelector,
        validator: DeterministicValidator,
        scoring_service: QualityScoringService,
        decision_policy: ValidationDecisionPolicy,
        attempt_repository: ScrapingAttemptRepository,
        limits: PipelineLimits | None = None,
        llm_review_policy: LLMReviewPolicy | None = None,
        semantic_validator: SemanticValidator | None = None,
        semantic_confidence_service: SemanticConfidenceService | None = None,
        semantic_investigator: SemanticInvestigator | None = None,
    ) -> None:
        """Recebe todas as dependências necessárias para executar o fluxo."""

        self.strategy_selector = strategy_selector
        self.validator = validator
        self.scoring_service = scoring_service
        self.decision_policy = decision_policy
        self.attempt_repository = attempt_repository
        self.limits = limits or PipelineLimits()
        self.llm_review_policy = llm_review_policy or LLMReviewPolicy()
        self.semantic_validator = semantic_validator
        self.semantic_confidence_service = (
            semantic_confidence_service or SemanticConfidenceService()
        )
        # Porta opcional da v8. Quando ``None``, o comportamento da v7 é
        # preservado: confiança baixa ou ``needs_agent_review`` simplesmente
        # mantêm a decisão REJECT, sem investigação adicional.
        self.semantic_investigator = semantic_investigator

    async def execute(
        self,
        job_id: UUID,
        url: str,
        *,
        source_type: str = "startup_evidence",
    ) -> ScrapingResult:
        """Executa estratégias até produzir um resultado aprovado.

        Conteúdos rejeitados não se transformam em ``ScrapingResult``. Quando
        nenhuma estratégia consegue produzir conteúdo aceito, a pipeline
        informa a falha ao caso de uso por meio de ``ScrapingFailedError``.
        """

        timeout = self.limits.timeout_for(source_type)
        try:
            async with asyncio.timeout(timeout):
                return await self._execute_with_limits(
                    job_id, url, source_type=source_type
                )
        except TimeoutError as error:
            raise GlobalScrapingLimitExceededError(
                f"O job excedeu o timeout total de {timeout}s."
            ) from error

    async def _execute_with_limits(
        self,
        job_id: UUID,
        url: str,
        *,
        source_type: str,
    ) -> ScrapingResult:
        """Executa a pipeline já protegida pelo timeout global."""

        selected_strategies = self.strategy_selector.select(url)

        # Mesmo que a factory configure estratégias demais, o job respeita o
        # teto global e nunca tenta além da quantidade permitida.
        strategies = selected_strategies[: self.limits.max_strategies]
        strategies_were_limited = len(selected_strategies) > len(strategies)

        strategies = await self._apply_circuit_breaker(url, strategies)

        # ``enumerate`` fornece a posição atual para descobrirmos se existe
        # outra estratégia disponível depois da tentativa atual.
        for index, scraper in enumerate(strategies):
            has_next_strategy = index < len(strategies) - 1

            # Cada tecnologia tentada gera um registro de auditoria separado.
            attempt = ScrapingAttempt(
                job_id=job_id,
                method=scraper.method,
            )
            await self.attempt_repository.save(attempt)

            try:
                output = await scraper.scrape(ScrapingInput(url=url))
                validation_without_score = await self.validator.validate(output)
                validation = self.scoring_service.calculate(
                    validation_without_score, source_type=source_type
                )

                decision = self.decision_policy.decide(
                    validation.to_summary(),
                    has_next_strategy=has_next_strategy,
                )
                attempt_warnings = set(validation.warnings)
                semantic_metadata: dict[str, str | float | bool] = {}

                # Campos de auditoria preenchidos somente quando a v8 (agente)
                # participa desta tentativa. Permanecem em seus valores
                # padrão (``None``/``False``) no caminho da v7.
                semantic_confidence_value: float | None = None
                agent_reviewed_value = False
                agent_reason_value: str | None = None

                # A revisao semantica julga "evidencia de IA de uma startup",
                # o que nao se aplica a fontes curadas (ex: nvidia_knowledge,
                # vindas do source registry). Para essas, a decisao
                # deterministica (tecnica + textual) e' a palavra final.
                if (
                    decision is ValidationDecision.REJECT
                    and source_type == "startup_evidence"
                    and self.semantic_validator is not None
                    and self.llm_review_policy.requires_review(
                        validation.to_summary()
                    )
                ):
                    try:
                        assessment = await self.semantic_validator.validate(
                            SemanticValidationInput(
                                url=output.final_url,
                                title=output.title,
                                raw_text=output.raw_text,
                                deterministic=validation,
                            )
                        )
                    except SemanticValidationError:
                        # LLM indisponível (503/timeout persistente após retries).
                        # Fallback determinístico: repondera qualidade sem evidência
                        # (mesmo critério de fontes curadas). Conteúdo tecnicamente
                        # sólido é aceito; genuinamente fraco continua rejeitado.
                        attempt_warnings.add("llm_unavailable")
                        fallback_score = round(
                            validation.technical_score * 0.50
                            + validation.text_score * 0.50,
                            4,
                        )
                        if fallback_score >= 0.45:
                            decision = ValidationDecision.ACCEPT
                            semantic_metadata = {"llm_unavailable": True}
                        assessment = None  # sinaliza que revisão foi pulada

                    if assessment is not None:
                        semantic = self.semantic_confidence_service.calculate(assessment)
                        attempt_warnings.add("semantic_reviewed")
                        attempt_warnings.add(
                            f"semantic_decision_{assessment.decision.value}"
                        )
                        semantic_metadata = {
                            "semantic_reviewed": True,
                            "semantic_decision": assessment.decision.value,
                            "semantic_confidence": semantic.semantic_confidence,
                            "semantic_reason": assessment.reason,
                            "semantic_contradiction_detected": (
                                assessment.contradiction_detected
                            ),
                        }

                        if (
                            assessment.decision is SemanticReviewDecision.ACCEPTED
                            and semantic.semantic_confidence >= 0.80
                        ):
                            decision = ValidationDecision.ACCEPT
                            semantic_confidence_value = semantic.semantic_confidence

                    # A revisao simples nao teve confianca suficiente, ou
                    # pediu explicitamente revisao de um agente. Investigamos
                    # mais a fundo antes de desistir do conteudo (v8).
                    if assessment is not None and self.semantic_investigator is not None and (
                        assessment.decision
                        is SemanticReviewDecision.NEEDS_AGENT_REVIEW
                        or semantic.semantic_confidence < 0.80
                    ):
                        investigation = await self.semantic_investigator.investigate(
                            InvestigationInput(
                                url=output.final_url,
                                title=output.title,
                                raw_text=output.raw_text,
                                deterministic=validation,
                                semantic=semantic,
                            )
                        )
                        attempt_warnings.add("agent_reviewed")
                        attempt_warnings.add(
                            f"agent_decision_{investigation.decision.value}"
                        )
                        semantic_metadata["agent_reviewed"] = True
                        semantic_metadata["agent_decision"] = (
                            investigation.decision.value
                        )
                        semantic_metadata["agent_reason"] = investigation.reason

                        semantic_confidence_value = semantic.semantic_confidence
                        agent_reviewed_value = True
                        agent_reason_value = investigation.reason

                        if (
                            investigation.decision
                            is AgentInvestigationDecision.ACCEPTED
                        ):
                            decision = ValidationDecision.ACCEPT
                        elif (
                            investigation.decision
                            is AgentInvestigationDecision.NEEDS_MORE_SOURCES
                        ):
                            # Este caso nao se encaixa em ACCEPT/FALLBACK/REJECT,
                            # entao a tentativa e finalizada aqui mesmo, sem
                            # passar por ``finish_validation``.
                            _logger.info(
                                "scraping_attempt_scored",
                                extra={
                                    "url": url,
                                    "method": scraper.method.value,
                                    "quality_score": validation.quality_score,
                                    "technical_score": validation.technical_score,
                                    "text_score": validation.text_score,
                                    "evidence_score": validation.evidence_score,
                                    "decision": "needs_more_sources",
                                    "source_type": source_type,
                                },
                            )
                            attempt.finish_needs_more_sources(investigation.reason)
                            await self.attempt_repository.save(attempt)
                            raise MoreSourcesRequiredError(investigation.reason)
                        # else: decision permanece REJECT; o motivo do agente
                        # ja foi guardado em agent_reason_value.

                _logger.info(
                    "scraping_attempt_scored",
                    extra={
                        "url": url,
                        "method": scraper.method.value,
                        "quality_score": validation.quality_score,
                        "technical_score": validation.technical_score,
                        "text_score": validation.text_score,
                        "evidence_score": validation.evidence_score,
                        "decision": decision.value,
                        "source_type": source_type,
                    },
                )
                attempt.finish_validation(
                    decision=decision,
                    technical_score=validation.technical_score,
                    text_score=validation.text_score,
                    evidence_score=validation.evidence_score,
                    quality_score=validation.quality_score,
                    problems=list(validation.problems),
                    warnings=list(attempt_warnings),
                    semantic_confidence=semantic_confidence_value,
                    agent_reviewed=agent_reviewed_value,
                    agent_reason=agent_reason_value,
                )
                await self.attempt_repository.save(attempt)

                # FALLBACK significa que esta execução terminou normalmente,
                # mas outra tecnologia deve tentar coletar a mesma URL.
                if decision is ValidationDecision.FALLBACK:
                    continue

                if decision is ValidationDecision.REJECT:
                    if agent_reviewed_value:
                        # O agente investigou e confirmou a rejeição: o
                        # motivo fica registrado em ``agent_reason`` na
                        # tentativa, e a exceção específica permite que
                        # camadas acima diferenciem este caso de uma simples
                        # falha de validação determinística.
                        raise ContentRejectedError(
                            agent_reason_value
                            or "O agente confirmou a rejeição do conteúdo."
                        )

                    raise ScrapingFailedError(
                        "O conteúdo coletado foi rejeitado pela validação."
                    )

                # Apenas uma decisão ACCEPT produz a saída oficial do módulo.
                return ScrapingResult(
                    job_id=job_id,
                    url=output.source_url,
                    final_url=output.final_url,
                    title=output.title,
                    raw_html=output.raw_html,
                    raw_text=output.raw_text,
                    method=output.method,
                    status_code=output.status_code,
                    technical_score=validation.technical_score,
                    text_score=validation.text_score,
                    evidence_score=validation.evidence_score,
                    quality_score=validation.quality_score,
                    content_hash=sha256(
                        output.raw_text.encode("utf-8")
                    ).hexdigest(),
                    metadata={**output.metadata, **semantic_metadata},
                )
            except Exception as error:
                if attempt.status is AttemptStatus.RUNNING:
                    attempt.fail(str(error))
                    await self.attempt_repository.save(attempt)

                # Rejeição é uma decisão de negócio, não uma falha técnica que
                # outra tecnologia de coleta conseguiria corrigir.
                if isinstance(error, ScrapingFailedError):
                    raise

                # Somente falhas técnicas conhecidas como recuperáveis podem
                # trocar de tecnologia. Bugs e erros fatais são propagados.
                if isinstance(error, RecoverableScrapingError) and has_next_strategy:
                    continue

                if isinstance(error, RecoverableScrapingError) and strategies_were_limited:
                    raise GlobalScrapingLimitExceededError(
                        "O job atingiu o máximo de "
                        f"{self.limits.max_strategies} estratégias."
                    ) from error

                if not isinstance(error, RecoverableScrapingError):
                    raise

                raise ScrapingFailedError(
                    f"A estratégia {scraper.method} falhou: {error}"
                ) from error

        if strategies_were_limited:
            raise GlobalScrapingLimitExceededError(
                "O job atingiu o máximo de "
                f"{self.limits.max_strategies} estratégias."
            )

        raise ScrapingFailedError("Nenhuma estratégia produziu conteúdo aprovado.")

    async def _apply_circuit_breaker(
        self, url: str, strategies: list
    ) -> list:
        """Filtra estratégias cujo circuito está aberto para este host.

        Consulta o histórico de tentativas para pular estratégias que falharam
        N vezes seguidas nas últimas T horas. Se TODOS os circuitos estiverem
        abertos (caso improvável), retorna a lista original para não bloquear
        completamente o job — o site pode ter voltado.
        """
        host = urlparse(url).netloc
        since = datetime.now(UTC) - timedelta(hours=CIRCUIT_BREAKER_WINDOW_HOURS)

        active: list = []
        for scraper in strategies:
            failures = await self.attempt_repository.count_recent_failures_by_host_and_method(
                host, scraper.method, since
            )
            if is_circuit_open(failures):
                _logger.info(
                    "scraping_circuit_breaker_tripped",
                    extra={
                        "host": host,
                        "method": scraper.method.value,
                        "failure_count": failures,
                    },
                )
            else:
                active.append(scraper)

        # Fallback de segurança: se todos os circuitos estiverem abertos,
        # usa a lista completa — evita bloquear o job 100%.
        return active if active else strategies
