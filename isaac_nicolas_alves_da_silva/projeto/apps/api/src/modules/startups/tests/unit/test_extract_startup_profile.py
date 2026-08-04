"""Testes do caso de uso ExtractStartupProfile."""

from uuid import uuid4

import pytest

from apps.api.src.modules.startups.application.dto import ExtractStartupProfileInput
from apps.api.src.modules.startups.application.ports import (
    ExtractionOutcome,
    ExtractionPort,
)
from apps.api.src.modules.startups.application.use_cases.extract_startup_profile import (
    ExtractStartupProfile,
)
from apps.api.src.modules.startups.domain.entities import Startup, StartupAIProfile, StartupEvidence
from apps.api.src.modules.startups.domain.enums import (
    AiDeploymentStage,
    AiGpuNeed,
    AiWorkloadType,
    FundingStage,
)
from apps.api.src.modules.startups.domain.exceptions import (
    StartupExtractionUnavailableError,
    StartupNotFoundError,
)
from apps.api.src.modules.startups.tests.unit.test_startup_use_cases import (
    FakeEvidenceRepository,
    FakeStartupRepository,
    FakeUoW,
)


def _make_uow() -> FakeUoW:
    return FakeUoW(FakeStartupRepository(), FakeEvidenceRepository())


class FakeExtractionPort(ExtractionPort):
    def __init__(self, outcome: ExtractionOutcome) -> None:
        self.outcome = outcome
        self.received_evidence_texts: list[str] | None = None

    async def extract(
        self,
        *,
        name: str,
        sector: str | None,
        description: str | None,
        evidence_texts: list[str],
    ) -> ExtractionOutcome:
        self.received_evidence_texts = evidence_texts
        return self.outcome


@pytest.mark.anyio
async def test_extract_startup_profile_persists_outcome() -> None:
    uow = _make_uow()
    startup = Startup(name="Acme AI", sector="LLM customer service")
    await uow.startup_repository.save(startup)
    evidence = StartupEvidence(
        startup_id=startup.id,
        scraping_result_id=uuid4(),
        source_url="https://example.com/news",
        title="Acme launches LLM chatbot",
        notes="Fundada por Ana Silva, Series A de USD 2M, cliente Empresa X.",
    )
    await uow.evidence_repository.save(evidence)

    outcome = ExtractionOutcome(
        founders=["Ana Silva"],
        funding_stage=FundingStage.SERIES_A,
        funding_amount_usd=2_000_000.0,
        customers=["Empresa X"],
    )
    extractor = FakeExtractionPort(outcome)

    use_case = ExtractStartupProfile(lambda: uow, extractor)
    view = await use_case.execute(
        ExtractStartupProfileInput(startup_id=startup.id)
    )

    assert view.founders == ["Ana Silva"]
    assert view.funding_stage is FundingStage.SERIES_A
    assert view.funding_amount_usd == 2_000_000.0
    assert view.customers == ["Empresa X"]
    assert extractor.received_evidence_texts is not None
    assert extractor.received_evidence_texts[0].startswith(
        f"[evidence_id={evidence.id}] "
    )
    assert (
        "Acme launches LLM chatbot Fundada por Ana Silva, Series A de "
        "USD 2M, cliente Empresa X."
    ) in extractor.received_evidence_texts[0]


@pytest.mark.anyio
async def test_extract_startup_profile_persists_sector_and_description() -> None:
    uow = _make_uow()
    startup = Startup(name="Dadosfera")
    await uow.startup_repository.save(startup)

    outcome = ExtractionOutcome(
        sector="Data Analytics",
        description="Data platform with an AI agent that answers questions in natural language.",
    )
    extractor = FakeExtractionPort(outcome)

    use_case = ExtractStartupProfile(lambda: uow, extractor)
    view = await use_case.execute(
        ExtractStartupProfileInput(startup_id=startup.id)
    )

    assert view.sector == "Data Analytics"
    assert view.description == (
        "Data platform with an AI agent that answers questions in natural language."
    )


@pytest.mark.anyio
async def test_extract_startup_profile_persists_country_and_audit() -> None:
    uow = _make_uow()
    startup = Startup(name="Parana AI")
    await uow.startup_repository.save(startup)
    evidence = StartupEvidence(
        startup_id=startup.id,
        scraping_result_id=uuid4(),
        source_url="https://parana.ai/news",
        title="Startup paranaense cresce com IA",
        notes="A empresa brasileira tem sede no Parana.",
    )
    await uow.evidence_repository.save(evidence)

    outcome = ExtractionOutcome(country="BR")
    extractor = FakeExtractionPort(outcome)

    use_case = ExtractStartupProfile(lambda: uow, extractor)
    view = await use_case.execute(
        ExtractStartupProfileInput(startup_id=startup.id)
    )

    assert view.country == "BR"
    saved = uow.startup_repository.items[startup.id]
    assert saved.field_evidence_ids["country"] == [str(evidence.id)]
    assert "country" in saved.field_confidence


@pytest.mark.anyio
async def test_extract_startup_profile_does_not_erase_sector_when_outcome_has_none() -> None:
    uow = _make_uow()
    startup = Startup(name="Acme AI", sector="LLM customer service", description="Existing description")
    await uow.startup_repository.save(startup)

    outcome = ExtractionOutcome(founders=["Ana Silva"])
    extractor = FakeExtractionPort(outcome)

    use_case = ExtractStartupProfile(lambda: uow, extractor)
    view = await use_case.execute(
        ExtractStartupProfileInput(startup_id=startup.id)
    )

    assert view.sector == "LLM customer service"
    assert view.description == "Existing description"


@pytest.mark.anyio
async def test_extract_startup_profile_does_not_erase_country_when_outcome_has_none() -> None:
    uow = _make_uow()
    startup = Startup(name="Acme BR", website_url="https://acme.com.br", country="BR")
    await uow.startup_repository.save(startup)

    outcome = ExtractionOutcome(founders=["Ana Silva"], country=None)
    extractor = FakeExtractionPort(outcome)

    use_case = ExtractStartupProfile(lambda: uow, extractor)
    view = await use_case.execute(
        ExtractStartupProfileInput(startup_id=startup.id)
    )

    assert view.country == "BR"


@pytest.mark.anyio
async def test_extract_startup_profile_raises_when_startup_missing() -> None:
    uow = _make_uow()
    extractor = FakeExtractionPort(ExtractionOutcome())

    use_case = ExtractStartupProfile(lambda: uow, extractor)

    with pytest.raises(StartupNotFoundError):
        await use_case.execute(ExtractStartupProfileInput(startup_id=uuid4()))


@pytest.mark.anyio
async def test_extract_startup_profile_raises_when_extractor_unavailable() -> None:
    uow = _make_uow()
    startup = Startup(name="Acme AI")
    await uow.startup_repository.save(startup)

    use_case = ExtractStartupProfile(lambda: uow, None)

    with pytest.raises(StartupExtractionUnavailableError):
        await use_case.execute(
            ExtractStartupProfileInput(startup_id=startup.id)
        )


@pytest.mark.anyio
async def test_try_extract_persists_outcome() -> None:
    uow = _make_uow()
    startup = Startup(name="Acme AI")
    await uow.startup_repository.save(startup)
    outcome = ExtractionOutcome(founders=["Ana Silva"])
    extractor = FakeExtractionPort(outcome)

    use_case = ExtractStartupProfile(lambda: uow, extractor)
    result = await use_case.try_extract(startup.id)

    assert result.succeeded is True
    assert uow.startup_repository.items[startup.id].founders == ("Ana Silva",)


@pytest.mark.anyio
async def test_extract_startup_profile_persists_ai_profile() -> None:
    """Quando o outcome tem ai_profile, ele e salvo na startup."""

    uow = _make_uow()
    startup = Startup(name="VoiceBot AI")
    await uow.startup_repository.save(startup)

    profile = StartupAIProfile(
        ai_workload_type=AiWorkloadType.SPEECH,
        deployment_stage=AiDeploymentStage.PRODUCTION,
        gpu_need=AiGpuNeed.HIGH,
        current_tools=("PyTorch", "Kubernetes"),
        business_goal="Reduzir custo de atendimento via voz.",
        field_confidence={"ai_workload_type": 0.95, "gpu_need": 0.8},
    )
    outcome = ExtractionOutcome(ai_profile=profile)
    extractor = FakeExtractionPort(outcome)

    use_case = ExtractStartupProfile(lambda: uow, extractor)
    await use_case.execute(ExtractStartupProfileInput(startup_id=startup.id))

    saved = uow.startup_repository.items[startup.id]
    assert saved.ai_profile is not None
    assert saved.ai_profile.ai_workload_type is AiWorkloadType.SPEECH
    assert saved.ai_profile.deployment_stage is AiDeploymentStage.PRODUCTION
    assert saved.ai_profile.gpu_need is AiGpuNeed.HIGH
    assert "PyTorch" in saved.ai_profile.current_tools
    assert saved.ai_profile.field_confidence["ai_workload_type"] == 0.95


@pytest.mark.anyio
async def test_extract_startup_profile_populates_ai_profile_evidence_ids() -> None:
    """Campos do perfil de IA tambem recebem auditoria de evidencias."""

    uow = _make_uow()
    startup = Startup(name="Aprix")
    await uow.startup_repository.save(startup)
    ev1 = StartupEvidence(
        startup_id=startup.id,
        scraping_result_id=uuid4(),
        source_url="https://aprix.ai/product",
        title="Aprix Product",
        notes="Analytics platform processing millions of prices per day.",
    )
    ev2 = StartupEvidence(
        startup_id=startup.id,
        scraping_result_id=uuid4(),
        source_url="https://aprix.ai/careers",
        title="Data Engineer",
        notes="The team uses tabular ML pipelines in production.",
    )
    await uow.evidence_repository.save(ev1)
    await uow.evidence_repository.save(ev2)

    profile = StartupAIProfile(
        ai_workload_type=AiWorkloadType.ANALYTICS,
        deployment_stage=AiDeploymentStage.PRODUCTION,
        gpu_need=AiGpuNeed.MEDIUM,
        field_confidence={"ai_workload_type": 0.9, "gpu_need": 0.7},
    )
    outcome = ExtractionOutcome(ai_profile=profile)
    extractor = FakeExtractionPort(outcome)

    use_case = ExtractStartupProfile(lambda: uow, extractor)
    await use_case.execute(ExtractStartupProfileInput(startup_id=startup.id))

    saved = uow.startup_repository.items[startup.id]
    assert saved.ai_profile is not None
    all_ids = {str(ev1.id), str(ev2.id)}
    assert set(saved.ai_profile.field_evidence_ids["ai_workload_type"]) == all_ids
    assert set(saved.ai_profile.field_evidence_ids["gpu_need"]) == all_ids
    assert "model_type" not in saved.ai_profile.field_evidence_ids


@pytest.mark.anyio
async def test_extract_startup_profile_preserves_agent_ai_profile_evidence_ids() -> None:
    """Quando o agente aponta uma evidencia especifica, o use case preserva."""

    uow = _make_uow()
    startup = Startup(name="Aprix")
    await uow.startup_repository.save(startup)
    ev1 = StartupEvidence(
        startup_id=startup.id,
        scraping_result_id=uuid4(),
        source_url="https://aprix.ai/product",
        title="Product",
        notes="Analytics platform.",
    )
    ev2 = StartupEvidence(
        startup_id=startup.id,
        scraping_result_id=uuid4(),
        source_url="https://aprix.ai/jobs",
        title="Data Engineer",
        notes="Tabular ML in production.",
    )
    await uow.evidence_repository.save(ev1)
    await uow.evidence_repository.save(ev2)

    profile = StartupAIProfile(
        ai_workload_type=AiWorkloadType.ANALYTICS,
        field_confidence={"ai_workload_type": 0.9},
        field_evidence_ids={"ai_workload_type": [str(ev2.id), "not-a-real-id"]},
    )
    outcome = ExtractionOutcome(ai_profile=profile)
    extractor = FakeExtractionPort(outcome)

    use_case = ExtractStartupProfile(lambda: uow, extractor)
    await use_case.execute(ExtractStartupProfileInput(startup_id=startup.id))

    saved = uow.startup_repository.items[startup.id]
    assert saved.ai_profile is not None
    assert saved.ai_profile.field_evidence_ids["ai_workload_type"] == [str(ev2.id)]


@pytest.mark.anyio
async def test_extract_startup_profile_no_ai_profile_leaves_existing_intact() -> None:
    """Quando o outcome nao tem ai_profile, o campo existente nao e apagado."""

    uow = _make_uow()
    startup = Startup(name="Acme AI")
    existing_profile = StartupAIProfile(ai_workload_type=AiWorkloadType.NLP)
    startup.update_ai_profile(existing_profile)
    await uow.startup_repository.save(startup)

    outcome = ExtractionOutcome(founders=["Ana Silva"])
    extractor = FakeExtractionPort(outcome)

    use_case = ExtractStartupProfile(lambda: uow, extractor)
    await use_case.execute(ExtractStartupProfileInput(startup_id=startup.id))

    saved = uow.startup_repository.items[startup.id]
    assert saved.ai_profile is not None
    assert saved.ai_profile.ai_workload_type is AiWorkloadType.NLP


@pytest.mark.anyio
async def test_try_extract_is_noop_when_extractor_unavailable() -> None:
    uow = _make_uow()
    startup = Startup(name="Acme AI")
    await uow.startup_repository.save(startup)

    use_case = ExtractStartupProfile(lambda: uow, None)

    result = await use_case.try_extract(startup.id)

    assert result.succeeded is False
    assert result.unavailable is True
    assert uow.startup_repository.items[startup.id].founders == ()


@pytest.mark.anyio
async def test_extract_startup_profile_persists_main_field_confidence() -> None:
    """Confianca por campo basico reportada pelo LLM e salva na startup."""

    uow = _make_uow()
    startup = Startup(name="Acme AI")
    await uow.startup_repository.save(startup)
    evidence = StartupEvidence(
        startup_id=startup.id,
        scraping_result_id=uuid4(),
        source_url="https://acme.ai",
        title="Acme AI",
        notes="Founded by Ana Silva.",
    )
    await uow.evidence_repository.save(evidence)

    outcome = ExtractionOutcome(
        founders=["Ana Silva"],
        sector="AI Infrastructure",
        field_confidence={"founders": 0.9, "sector": 0.75},
    )
    extractor = FakeExtractionPort(outcome)

    use_case = ExtractStartupProfile(lambda: uow, extractor)
    await use_case.execute(ExtractStartupProfileInput(startup_id=startup.id))

    saved = uow.startup_repository.items[startup.id]
    assert saved.field_confidence["founders"] == 0.9
    assert saved.field_confidence["sector"] == 0.75


@pytest.mark.anyio
async def test_extract_startup_profile_populates_field_evidence_ids_for_extracted_fields() -> None:
    """IDs das evidencias disponiveis sao gravados para cada campo extraido."""

    uow = _make_uow()
    startup = Startup(name="Acme AI")
    await uow.startup_repository.save(startup)
    ev1 = StartupEvidence(
        startup_id=startup.id,
        scraping_result_id=uuid4(),
        source_url="https://acme.ai",
        title="Acme AI",
        notes="Founded by Ana Silva.",
    )
    ev2 = StartupEvidence(
        startup_id=startup.id,
        scraping_result_id=uuid4(),
        source_url="https://acme.ai/customers",
        title="Customers",
        notes="Customer: Empresa X.",
    )
    await uow.evidence_repository.save(ev1)
    await uow.evidence_repository.save(ev2)

    outcome = ExtractionOutcome(
        founders=["Ana Silva"],
        customers=["Empresa X"],
    )
    extractor = FakeExtractionPort(outcome)

    use_case = ExtractStartupProfile(lambda: uow, extractor)
    await use_case.execute(ExtractStartupProfileInput(startup_id=startup.id))

    saved = uow.startup_repository.items[startup.id]
    all_ids = {str(ev1.id), str(ev2.id)}
    assert set(saved.field_evidence_ids["founders"]) == all_ids
    assert set(saved.field_evidence_ids["customers"]) == all_ids
    assert "sector" not in saved.field_evidence_ids


@pytest.mark.anyio
async def test_extract_startup_profile_preserves_agent_main_field_evidence_ids() -> None:
    """Auditoria de campos basicos respeita IDs especificos retornados."""

    uow = _make_uow()
    startup = Startup(name="Acme AI")
    await uow.startup_repository.save(startup)
    ev1 = StartupEvidence(
        startup_id=startup.id,
        scraping_result_id=uuid4(),
        source_url="https://acme.ai",
        title="Acme AI",
        notes="Founded by Ana Silva.",
    )
    ev2 = StartupEvidence(
        startup_id=startup.id,
        scraping_result_id=uuid4(),
        source_url="https://acme.ai/customers",
        title="Customers",
        notes="Customer: Empresa X.",
    )
    await uow.evidence_repository.save(ev1)
    await uow.evidence_repository.save(ev2)

    outcome = ExtractionOutcome(
        founders=["Ana Silva"],
        customers=["Empresa X"],
        field_evidence_ids={
            "founders": [str(ev1.id)],
            "customers": [str(ev2.id), "not-a-real-id"],
        },
    )
    extractor = FakeExtractionPort(outcome)

    use_case = ExtractStartupProfile(lambda: uow, extractor)
    await use_case.execute(ExtractStartupProfileInput(startup_id=startup.id))

    saved = uow.startup_repository.items[startup.id]
    assert saved.field_evidence_ids["founders"] == [str(ev1.id)]
    assert saved.field_evidence_ids["customers"] == [str(ev2.id)]


@pytest.mark.anyio
async def test_extract_startup_profile_computes_main_confidence_when_llm_returns_empty() -> None:
    """Quando o LLM retorna field_confidence vazio, o codigo computa deterministicamente."""

    uow = _make_uow()
    startup = Startup(name="Acme AI")
    await uow.startup_repository.save(startup)
    evidence = StartupEvidence(
        startup_id=startup.id,
        scraping_result_id=uuid4(),
        source_url="https://acme.ai",
        title="Acme AI",
        notes="Founded by Ana Silva.",
    )
    await uow.evidence_repository.save(evidence)

    # field_confidence vazio — simula comportamento real do LLM com with_structured_output
    outcome = ExtractionOutcome(
        founders=["Ana Silva"],
        sector="AI Infrastructure",
        field_confidence={},  # LLM nao preencheu
    )
    extractor = FakeExtractionPort(outcome)

    use_case = ExtractStartupProfile(lambda: uow, extractor)
    await use_case.execute(ExtractStartupProfileInput(startup_id=startup.id))

    saved = uow.startup_repository.items[startup.id]
    # O codigo deve ter computado confianca deterministicamente
    assert "founders" in saved.field_confidence
    assert "sector" in saved.field_confidence
    assert 0.0 < saved.field_confidence["founders"] <= 1.0
    assert 0.0 < saved.field_confidence["sector"] <= 1.0
    # Campos nao extraidos nao devem aparecer
    assert "customers" not in saved.field_confidence


@pytest.mark.anyio
async def test_extract_startup_profile_ai_profile_evidence_ids_when_confidence_empty() -> None:
    """Perfil de IA recebe evidence_ids mesmo quando field_confidence e vazio."""

    uow = _make_uow()
    startup = Startup(name="VoiceBot AI")
    await uow.startup_repository.save(startup)
    ev = StartupEvidence(
        startup_id=startup.id,
        scraping_result_id=uuid4(),
        source_url="https://voicebot.ai/product",
        title="Product",
        notes="Speech AI for customer service.",
    )
    await uow.evidence_repository.save(ev)

    profile = StartupAIProfile(
        ai_workload_type=AiWorkloadType.SPEECH,
        deployment_stage=AiDeploymentStage.PRODUCTION,
        gpu_need=AiGpuNeed.HIGH,
        field_confidence={},  # LLM nao preencheu
    )
    outcome = ExtractionOutcome(ai_profile=profile)
    extractor = FakeExtractionPort(outcome)

    use_case = ExtractStartupProfile(lambda: uow, extractor)
    await use_case.execute(ExtractStartupProfileInput(startup_id=startup.id))

    saved = uow.startup_repository.items[startup.id]
    assert saved.ai_profile is not None
    # evidence_ids deve ser populado para campos com valores nao-unknown
    assert "ai_workload_type" in saved.ai_profile.field_evidence_ids
    assert "deployment_stage" in saved.ai_profile.field_evidence_ids
    assert "gpu_need" in saved.ai_profile.field_evidence_ids
    # Campo unknown nao deve aparecer
    assert "model_type" not in saved.ai_profile.field_evidence_ids
    # field_confidence tambem deve ter sido computado deterministicamente
    assert "ai_workload_type" in saved.ai_profile.field_confidence
    assert saved.ai_profile.field_confidence["ai_workload_type"] > 0


@pytest.mark.anyio
async def test_extract_startup_profile_confidence_scales_with_evidence_count() -> None:
    """Confianca deterministica aumenta com mais evidencias."""

    uow_one = _make_uow()
    uow_three = _make_uow()
    startup_one = Startup(name="Startup One")
    startup_three = Startup(name="Startup Three")
    await uow_one.startup_repository.save(startup_one)
    await uow_three.startup_repository.save(startup_three)

    # 1 evidencia
    ev1 = StartupEvidence(
        startup_id=startup_one.id,
        scraping_result_id=uuid4(),
        source_url="https://one.ai",
        title="One",
        notes="Founders: Alice.",
    )
    await uow_one.evidence_repository.save(ev1)

    # 3 evidencias
    for i in range(3):
        ev = StartupEvidence(
            startup_id=startup_three.id,
            scraping_result_id=uuid4(),
            source_url=f"https://three.ai/page{i}",
            title=f"Page {i}",
            notes="Founders: Bob.",
        )
        await uow_three.evidence_repository.save(ev)

    outcome = ExtractionOutcome(founders=["Alice"], field_confidence={})
    use_case_one = ExtractStartupProfile(lambda: uow_one, FakeExtractionPort(outcome))
    await use_case_one.execute(ExtractStartupProfileInput(startup_id=startup_one.id))

    outcome3 = ExtractionOutcome(founders=["Bob"], field_confidence={})
    use_case_three = ExtractStartupProfile(lambda: uow_three, FakeExtractionPort(outcome3))
    await use_case_three.execute(ExtractStartupProfileInput(startup_id=startup_three.id))

    conf_one = uow_one.startup_repository.items[startup_one.id].field_confidence["founders"]
    conf_three = uow_three.startup_repository.items[startup_three.id].field_confidence["founders"]
    assert conf_three > conf_one
