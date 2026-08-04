from __future__ import annotations

from src.api.service import serialize_analysis_result
from src.models import Startup, StartupClassification


def test_serialize_analysis_result_falls_back_when_description_is_noisy_mojibake():
    payload = {
        "structured_startup": Startup(
            name="NeuralCare AI",
            segment="healthtech",
            short_description=(
                "NeuralCare AI re. Request Demo â Read the Docs â HIPAA Compliant "
                "â SOC 2 Type II â ISO 27001 â GDPR â FDA 21 CFR Part 11 "
                "â NHS IG Toolkit Top 10 Startups de Inteligência Artificial no Brasil em 2025 "
                "Skip to content Tecnologia Inteligência Artificial Startups July 24, 2025..."
            ),
            tags=["llm", "healthcare"],
            ai_native_score=0.82,
        ),
        "initial_classification": StartupClassification(
            label="ai_native_candidate",
            score=0.82,
            signals=["llm", "healthcare"],
        ),
        "validated_evidences": [],
        "recommendations": [],
        "validation_report": {"status": "ok", "unsupported_fields": []},
        "logs": [],
        "errors": [],
    }

    serialized = serialize_analysis_result(payload)

    assert serialized["description"] == "NeuralCare AI atua em healthtech com sinais de llm, healthcare."
    assert "Request Demo" not in serialized["description"]
