"""Tests for src.extraction.extractor."""

from datetime import datetime

from pydantic import HttpUrl

from src.extraction.extractor import extract_profile
from src.extraction.schemas import ConfidenceLevel, Evidence, SourceType


def _full_text() -> str:
    return (
        "Aurora Ops AI\n\n"
        "Aurora Ops AI provides AI-assisted operational workflows "
        "for industrial teams. Our platform uses machine learning and "
        "natural language processing to automate complex tasks.\n\n"
        "Founded by João Silva and Maria Santos, the company has raised "
        "$10M in Series A funding.\n\n"
        "Our clients include large industrial enterprises and logistics "
        "companies.\n\n"
        "Our tech stack includes Python, PyTorch, and Kubernetes."
    )


def _minimal_text() -> str:
    return "StartupX\n\nWe are a small company building software tools."


def _empty_text() -> str:
    return ""


def _text_with_no_ai() -> str:
    return "CleanTech Solutions\n\n" "We sell physical water filters for residential use. " "Founded by Carlos Souza."


def _text_with_title_tag() -> str:
    return (
        "<title>DataFlow AI | Intelligent Data Pipelines</title>\n\n"
        "DataFlow AI builds smart data pipelines for e-commerce."
    )


# ---------------------------------------------------------------------------
# Full profile
# ---------------------------------------------------------------------------


def test_extract_full_profile() -> None:
    profile = extract_profile(_full_text(), "https://auroraops.ai")

    assert profile.startup_name == "Aurora Ops AI"
    assert profile.website == HttpUrl("https://auroraops.ai")
    assert profile.country == "Brazil"
    assert profile.description != "Not verified"
    assert profile.product_summary != "Not verified"
    assert len(profile.ai_signals) > 0
    assert len(profile.founders) > 0
    assert len(profile.customers) > 0
    assert len(profile.funding_signals) > 0
    assert len(profile.tech_stack_signals) > 0
    assert profile.confidence_score > 0.5
    assert len(profile.sources) > 0


def test_extract_full_ai_signals() -> None:
    profile = extract_profile(_full_text(), "https://auroraops.ai")
    signals_text = " ".join(profile.ai_signals).lower()
    assert "machine learning" in signals_text
    assert "natural language processing" in signals_text


def test_extract_full_founders() -> None:
    profile = extract_profile(_full_text(), "https://auroraops.ai")
    founder_names = " ".join(profile.founders)
    assert "João Silva" in founder_names or "Joao Silva" in founder_names


def test_extract_full_funding() -> None:
    profile = extract_profile(_full_text(), "https://auroraops.ai")
    funding_text = " ".join(profile.funding_signals)
    assert "$10M" in funding_text or "10M" in funding_text
    assert "A" in funding_text


def test_extract_full_customers() -> None:
    profile = extract_profile(_full_text(), "https://auroraops.ai")
    cust_text = " ".join(profile.customers).lower()
    assert "industrial" in cust_text or "logistics" in cust_text


def test_extract_full_tech_stack() -> None:
    profile = extract_profile(_full_text(), "https://auroraops.ai")
    tech_text = " ".join(profile.tech_stack_signals).lower()
    assert "python" in tech_text
    assert "pytorch" in tech_text
    assert "kubernetes" in tech_text


def test_extract_full_confidence() -> None:
    profile = extract_profile(_full_text(), "https://auroraops.ai")
    assert 0.7 <= profile.confidence_score <= 1.0


def test_extract_full_sources_have_evidence() -> None:
    profile = extract_profile(_full_text(), "https://auroraops.ai")
    assert len(profile.sources) >= 1
    for src in profile.sources:
        assert isinstance(src, Evidence)
        assert src.source_url == HttpUrl("https://auroraops.ai")
        assert src.confidence in (ConfidenceLevel.MEDIUM, ConfidenceLevel.HIGH)
        assert isinstance(src.collected_at, datetime)


# ---------------------------------------------------------------------------
# Partial profile (minimal text)
# ---------------------------------------------------------------------------


def test_extract_partial_profile() -> None:
    profile = extract_profile(_minimal_text(), "https://startupx.com")

    assert profile.startup_name == "StartupX"
    assert profile.description != "Not verified"
    assert profile.ai_signals == []
    assert profile.founders == []
    assert profile.customers == []
    assert profile.funding_signals == []
    assert profile.tech_stack_signals == []
    assert profile.confidence_score < 0.5


# ---------------------------------------------------------------------------
# Empty text
# ---------------------------------------------------------------------------


def test_extract_empty_text() -> None:
    profile = extract_profile(_empty_text(), "https://empty.com")

    assert profile.startup_name == "Not verified"
    assert profile.description == "Not verified"
    assert profile.product_summary == "Not verified"
    assert profile.ai_signals == []
    assert profile.founders == []
    assert profile.customers == []
    assert profile.funding_signals == []
    assert profile.tech_stack_signals == []
    assert profile.confidence_score == 0.1


# ---------------------------------------------------------------------------
# No AI signals
# ---------------------------------------------------------------------------


def test_extract_no_ai_signals() -> None:
    profile = extract_profile(_text_with_no_ai(), "https://cleantech.com")

    assert profile.ai_signals == []
    assert profile.description != "Not verified"
    assert profile.founders != []


# ---------------------------------------------------------------------------
# Title tag extraction
# ---------------------------------------------------------------------------


def test_extract_title_tag() -> None:
    profile = extract_profile(_text_with_title_tag(), "https://dataflow.ai")

    assert profile.startup_name == "DataFlow AI"
    assert profile.description != "Not verified"


# ---------------------------------------------------------------------------
# Startup name hint overrides text
# ---------------------------------------------------------------------------


def test_extract_name_hint_override() -> None:
    profile = extract_profile(
        _full_text(),
        "https://auroraops.ai",
        startup_name_hint="Custom Name",
    )
    assert profile.startup_name == "Custom Name"


# ---------------------------------------------------------------------------
# Source classification via URL
# ---------------------------------------------------------------------------


def test_extract_source_type_from_url() -> None:
    profile = extract_profile(
        "Some blog text about a startup.",
        "https://blog.example.com/startup",
    )
    assert len(profile.sources) > 0
    assert profile.sources[0].source_type == SourceType.BLOG


def test_extract_source_type_news() -> None:
    profile = extract_profile(
        "Some news about a startup.",
        "https://neofeed.com.br/startup",
    )
    assert len(profile.sources) > 0
    assert profile.sources[0].source_type == SourceType.NEWS


# ---------------------------------------------------------------------------
# Confidence edge cases
# ---------------------------------------------------------------------------


def test_extract_confidence_no_filled_fields() -> None:
    profile = extract_profile("", "https://nowhere.com")
    assert profile.confidence_score == 0.1


def test_extract_confidence_mostly_filled() -> None:
    text = (
        "HealthAI\n\n"
        "We build AI for hospitals using machine learning and deep learning.\n\n"
        "Founded by Ana Costa.\n\n"
        "Raised $5M seed funding.\n\n"
        "Our stack: Python, PyTorch."
    )
    profile = extract_profile(text, "https://healthai.com")
    assert profile.confidence_score >= 0.5
