"""Testes do adapter Startups -> Agents para extracao."""

import pytest

from apps.api.src.modules.agents.application.dto import (
    ExtractionInput,
    ExtractionResult,
)
from apps.api.src.modules.agents.application.public.extractor import ExtractionService
from apps.api.src.modules.agents.domain.enums import ExtractedFundingStage
from apps.api.src.modules.startups.domain.enums import AiWorkloadType
from apps.api.src.modules.startups.infrastructure.agent_adapters.agents_extractor import (
    AgentsExtractor,
)


class FakeExtractionService(ExtractionService):
    def __init__(self, result: ExtractionResult) -> None:
        self.result = result
        self.received_input: ExtractionInput | None = None

    async def extract(self, extraction_input: ExtractionInput) -> ExtractionResult:
        self.received_input = extraction_input
        return self.result


@pytest.mark.anyio
async def test_agents_extractor_splits_main_and_ai_profile_audit() -> None:
    service = FakeExtractionService(
        ExtractionResult(
            founders=["Ana Silva"],
            funding_stage=ExtractedFundingStage.SEED,
            funding_amount_usd=None,
            customers=[],
            country="BR",
            ai_workload_type="analytics",
            field_confidence={
                "founders": 0.9,
                "country": 0.7,
                "ai_workload_type": 0.8,
            },
            field_evidence_ids={
                "founders": ["ev-main"],
                "country": ["ev-country"],
                "ai_workload_type": ["ev-ai"],
            },
        )
    )
    adapter = AgentsExtractor(service)

    outcome = await adapter.extract(
        name="Aprix",
        sector=None,
        description=None,
        evidence_texts=["[evidence_id=ev-ai] Analytics workload."],
    )

    assert outcome.country == "BR"
    assert outcome.field_confidence == {"founders": 0.9, "country": 0.7}
    assert outcome.field_evidence_ids == {
        "founders": ["ev-main"],
        "country": ["ev-country"],
    }
    assert outcome.ai_profile is not None
    assert outcome.ai_profile.ai_workload_type is AiWorkloadType.ANALYTICS
    assert outcome.ai_profile.field_confidence == {"ai_workload_type": 0.8}
    assert outcome.ai_profile.field_evidence_ids == {"ai_workload_type": ["ev-ai"]}
