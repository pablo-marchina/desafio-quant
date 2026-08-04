from scraper.validation_pipeline.validator import (
    assign_priority, calculate_score, detect_noise, normalize_company_name, validate_candidate,
)


def test_normalize_and_noise():
    assert normalize_company_name("Ácme Tecnologia Ltda.") == "acme"
    assert detect_noise({"company_name": "CEO e fundador da empresa", "description": ""})
    assert detect_noise({"company_name": "Como captar investimento?", "description": ""})


def test_strong_source_ai_candidate_is_approved():
    row = validate_candidate({"id": "1", "company_name": "Nuvem AI", "source_name": "Cubo",
        "source_url": "https://cubo.itau/startups-portfolio",
        "description": "Startup brasileira com plataforma de inteligência artificial para automação.",
        "founding_year": "2025"})
    assert row["normalized_name"] == "nuvem ai"
    assert row["ai_classification"] == "AI_NATIVE"
    assert row["confidence_score"] == 100
    assert row["validation_status"] == "APPROVED"
    assert row["priority"] == "HIGH"


def test_news_is_weak_and_unknown_stays_review():
    row = validate_candidate({"company_name": "Acme", "source_name": "Brazil Journal",
        "source_url": "https://braziljournal.com/acme", "description": "A startup recebeu uma rodada de investimento."})
    assert row["validation_status"] == "REVIEW"
    assert row["is_brazilian"] is None
    assert row["ai_classification"] == "NON_AI"
    assert assign_priority(None) == "REVIEW"
