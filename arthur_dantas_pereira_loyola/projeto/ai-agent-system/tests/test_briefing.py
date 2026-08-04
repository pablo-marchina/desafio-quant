from radar.agents.briefing import generate_briefing
from radar.graph.retry_policy import MAX_COLLECTION_ATTEMPTS
from radar.schemas import EvidenceValidationReport, PipelineError


def test_briefing_includes_collection_error_caveats() -> None:
    briefing = generate_briefing(
        {
            "query": "startup brasileira validada com IA",
            "errors": [
                PipelineError(
                    step="scraper.fetch",
                    message="fixture missing",
                    recoverable=True,
                    source_url="https://example.com/missing",
                    provider="PageContentAdapter",
                    error_type="ValueError",
                )
            ],
        }
    )

    assert "scraper.fetch" in "\n".join(briefing.caveats)
    assert "https://example.com/missing" in "\n".join(briefing.caveats)


def test_briefing_includes_retry_limit_caveat() -> None:
    briefing = generate_briefing(
        {
            "query": "startup brasileira de IA",
            "collection_attempts": MAX_COLLECTION_ATTEMPTS,
            "validation": EvidenceValidationReport(
                has_minimum_evidence=False,
                source_quality="weak",
                supporting_evidence_ids=[],
                conflicts=[],
                caveats=[],
                requires_human_review=True,
            ),
        }
    )

    all_caveats = "\n".join(briefing.caveats)
    assert f"apos {MAX_COLLECTION_ATTEMPTS} tentativas" in all_caveats


def test_briefing_has_rich_sections() -> None:
    briefing = generate_briefing(
        {
            "query": "gupy",
            "startup_name": "Gupy",
        }
    )

    assert briefing.title == "Briefing: Gupy"
    assert briefing.startup_name == "Gupy"
    assert briefing.executive_summary
    assert briefing.ai_maturity_diagnosis.title == "Diagnostico AI-native"
    assert briefing.evidence_summary.title == "Evidencias principais"
    assert briefing.technical_gaps.title == "Gaps tecnicos identificados"
    assert briefing.nvidia_recommendations_section.title == "Recomendacoes NVIDIA"
    assert briefing.suggested_approach.title == "Proximos passos sugeridos"


def test_briefing_uses_startup_name_when_available() -> None:
    briefing = generate_briefing(
        {
            "query": "tractian",
            "startup_name": "Tractian",
            "extracted_startups": [
                type("FakeProfile", (), {
                    "name": "Tractian Tecnologia",
                    "sector": "Industrial",
                    "product": "Manutencao Preditiva",
                    "cited_technologies": ["IoT", "Machine Learning"],
                    "funding": "Serie B",
                    "founders": [],
                })()
            ],
        }
    )

    assert briefing.startup_name == "Tractian Tecnologia"
    assert briefing.startup_sector == "Industrial"
