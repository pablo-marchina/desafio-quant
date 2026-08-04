"""Caso de uso para classificar a maturidade de IA de uma startup."""

import asyncio
from uuid import UUID

from apps.api.src.modules.startups.application.dto import (
    ClassifyStartupInput,
    StartupView,
)
from apps.api.src.modules.startups.application.evidence_text_cleaner import (
    compact_evidence_text,
)
from apps.api.src.modules.startups.application.ports import StartupClassifierPort
from apps.api.src.modules.startups.application.public.classification_trigger import (
    ClassificationTrigger,
)
from apps.api.src.modules.startups.application.unit_of_work import (
    StartupsUnitOfWorkFactory,
)
from apps.api.src.modules.startups.application.use_cases.create_startup import (
    to_startup_view,
)
from apps.api.src.modules.startups.domain.exceptions import (
    StartupClassificationUnavailableError,
    StartupNotFoundError,
)
from apps.api.src.shared.logging import get_logger


logger = get_logger(__name__)
TRY_CLASSIFY_TIMEOUT_SECONDS = 45


class ClassifyStartup(ClassificationTrigger):
    """Classifica uma startup chamando o Startup Classifier Agent."""

    def __init__(
        self,
        uow_factory: StartupsUnitOfWorkFactory,
        classifier: StartupClassifierPort | None,
    ) -> None:
        self._uow_factory = uow_factory
        self._classifier = classifier

    async def try_classify(self, startup_id: UUID) -> None:
        try:
            await asyncio.wait_for(
                self.execute(ClassifyStartupInput(startup_id=startup_id)),
                timeout=TRY_CLASSIFY_TIMEOUT_SECONDS,
            )
        except StartupClassificationUnavailableError:
            return
        except (asyncio.TimeoutError, TimeoutError):
            logger.warning(
                "startup classification timed out",
                extra={
                    "startup_id": str(startup_id),
                    "reason": f"timeout after {TRY_CLASSIFY_TIMEOUT_SECONDS}s",
                },
            )
            return
        except Exception as error:
            logger.warning(
                "startup classification skipped after best-effort failure",
                extra={
                    "startup_id": str(startup_id),
                    "reason": str(error) or repr(error),
                },
            )
            return

    async def execute(self, classify_input: ClassifyStartupInput) -> StartupView:
        if self._classifier is None:
            raise StartupClassificationUnavailableError(
                "Servico de classificacao nao configurado (verifique GEMINI_API_KEY)."
            )

        async with self._uow_factory() as uow:
            startup = await uow.startup_repository.get_by_id(
                classify_input.startup_id
            )
            if startup is None:
                raise StartupNotFoundError(
                    f"Startup {classify_input.startup_id} nao encontrada."
                )
            evidences = await uow.evidence_repository.list_by_startup_id(
                classify_input.startup_id
            )

            evidence_texts = [
                compact_evidence_text(
                    "\n".join([evidence.title or "", evidence.notes or ""])
                )
                for evidence in evidences
            ]
            outcome = await self._classifier.classify(
                name=startup.name,
                sector=startup.sector,
                description=startup.description,
                country=startup.country,
                website_url=startup.website_url,
                evidence_texts=[text for text in evidence_texts if text],
            )

            startup.classify(outcome.level, outcome.reason)
            await uow.startup_repository.save(startup)
            await uow.commit()

        return to_startup_view(startup)
