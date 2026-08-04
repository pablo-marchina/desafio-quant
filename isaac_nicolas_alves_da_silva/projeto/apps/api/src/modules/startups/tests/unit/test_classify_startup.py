"""Testes do caso de uso ClassifyStartup."""

from uuid import uuid4

import pytest

from apps.api.src.modules.startups.application.dto import ClassifyStartupInput
from apps.api.src.modules.startups.application.ports import (
    ClassificationOutcome,
    StartupClassifierPort,
)
from apps.api.src.modules.startups.application.use_cases.classify_startup import (
    ClassifyStartup,
)
from apps.api.src.modules.startups.domain.entities import Startup, StartupEvidence
from apps.api.src.modules.startups.domain.enums import AiMaturityLevel
from apps.api.src.modules.startups.domain.exceptions import (
    StartupClassificationUnavailableError,
    StartupNotFoundError,
)
from apps.api.src.modules.startups.tests.unit.test_startup_use_cases import (
    FakeEvidenceRepository,
    FakeStartupRepository,
    FakeUoW,
)


def _make_uow() -> FakeUoW:
    return FakeUoW(FakeStartupRepository(), FakeEvidenceRepository())


class FakeClassifierPort(StartupClassifierPort):
    def __init__(self, outcome: ClassificationOutcome) -> None:
        self.outcome = outcome
        self.received_evidence_texts: list[str] | None = None

    async def classify(
        self,
        *,
        name: str,
        sector: str | None,
        description: str | None,
        country: str | None,
        website_url: str | None,
        evidence_texts: list[str],
    ) -> ClassificationOutcome:
        self.received_evidence_texts = evidence_texts
        return self.outcome


@pytest.mark.anyio
async def test_classify_startup_persists_outcome() -> None:
    uow = _make_uow()
    startup = Startup(name="Acme AI", sector="LLM customer service")
    await uow.startup_repository.save(startup)
    evidence = StartupEvidence(
        startup_id=startup.id,
        scraping_result_id=uuid4(),
        source_url="https://example.com/news",
        title="Acme launches LLM chatbot",
        notes="Modelo proprio treinado internamente.",
    )
    await uow.evidence_repository.save(evidence)

    outcome = ClassificationOutcome(
        level=AiMaturityLevel.AI_NATIVE,
        reason="Modelo proprio no core do produto.",
    )
    classifier = FakeClassifierPort(outcome)

    use_case = ClassifyStartup(lambda: uow, classifier)
    view = await use_case.execute(ClassifyStartupInput(startup_id=startup.id))

    assert view.ai_maturity_level is AiMaturityLevel.AI_NATIVE
    assert view.classification_reason == "Modelo proprio no core do produto."
    assert view.classified_at is not None
    assert classifier.received_evidence_texts == [
        "Acme launches LLM chatbot Modelo proprio treinado internamente."
    ]


@pytest.mark.anyio
async def test_classify_startup_compacts_evidence_texts() -> None:
    uow = _make_uow()
    startup = Startup(name="NeuralMind")
    await uow.startup_repository.save(startup)
    evidence = StartupEvidence(
        startup_id=startup.id,
        scraping_result_id=uuid4(),
        source_url="https://example.com/news",
        title="Menu\nNewsletter\nNeuralMind usa BERT",
        notes=(
            "Assine nossa newsletter\n"
            "NeuralMind treina modelos BERT em portugues\n"
            "NeuralMind treina modelos BERT em portugues"
        ),
    )
    await uow.evidence_repository.save(evidence)

    classifier = FakeClassifierPort(
        ClassificationOutcome(level=AiMaturityLevel.AI_NATIVE, reason="core")
    )

    use_case = ClassifyStartup(lambda: uow, classifier)
    await use_case.execute(ClassifyStartupInput(startup_id=startup.id))

    assert classifier.received_evidence_texts is not None
    sent = classifier.received_evidence_texts[0]
    assert "newsletter" not in sent.lower()
    assert "BERT" in sent
    assert sent.count("NeuralMind treina") == 1


@pytest.mark.anyio
async def test_classify_startup_raises_when_startup_missing() -> None:
    uow = _make_uow()
    classifier = FakeClassifierPort(
        ClassificationOutcome(level=AiMaturityLevel.NON_AI, reason="n/a")
    )

    use_case = ClassifyStartup(lambda: uow, classifier)

    with pytest.raises(StartupNotFoundError):
        await use_case.execute(ClassifyStartupInput(startup_id=uuid4()))


@pytest.mark.anyio
async def test_classify_startup_raises_when_classifier_unavailable() -> None:
    uow = _make_uow()
    startup = Startup(name="Acme AI")
    await uow.startup_repository.save(startup)

    use_case = ClassifyStartup(lambda: uow, None)

    with pytest.raises(StartupClassificationUnavailableError):
        await use_case.execute(ClassifyStartupInput(startup_id=startup.id))


@pytest.mark.anyio
async def test_try_classify_persists_outcome() -> None:
    uow = _make_uow()
    startup = Startup(name="Acme AI")
    await uow.startup_repository.save(startup)
    classifier = FakeClassifierPort(
        ClassificationOutcome(level=AiMaturityLevel.AI_NATIVE, reason="core")
    )

    use_case = ClassifyStartup(lambda: uow, classifier)
    await use_case.try_classify(startup.id)

    assert (
        uow.startup_repository.items[startup.id].ai_maturity_level
        is AiMaturityLevel.AI_NATIVE
    )


@pytest.mark.anyio
async def test_try_classify_is_noop_when_classifier_unavailable() -> None:
    uow = _make_uow()
    startup = Startup(name="Acme AI")
    await uow.startup_repository.save(startup)

    use_case = ClassifyStartup(lambda: uow, None)

    await use_case.try_classify(startup.id)

    assert uow.startup_repository.items[startup.id].ai_maturity_level is None
