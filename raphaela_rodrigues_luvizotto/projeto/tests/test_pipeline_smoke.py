from __future__ import annotations

from src.agents import build_startup_pipeline


def test_pipeline_smoke_runs_with_validator_and_retry_metadata():
    graph = build_startup_pipeline()
    state = graph.invoke(
        {
            "query": "Acme AI",
            "target_startup": "Acme AI",
            "raw_documents": [
                {
                    "url": "https://acme.ai",
                    "titulo": "Acme AI | Voice agents for healthcare operations",
                    "fonte_tipo": "site_oficial",
                    "texto": (
                        "Acme AI is a Brazilian startup building voice agents and LLM workflows "
                        "for hospitals and clinics. The Acme AI platform automates patient intake."
                    ),
                    "coletado_em": "2026-06-29T00:00:00+00:00",
                    "metodo_coleta": "test_fixture",
                    "status_http": 200,
                },
                {
                    "url": "https://www.cubo.itau.com.br/startups/acme-ai",
                    "titulo": "Acme AI na vitrine Cubo",
                    "fonte_tipo": "directory_profile",
                    "texto": (
                        "Acme AI develops generative AI copilots for healthcare and customer service. "
                        "Its business model is B2B SaaS."
                    ),
                    "coletado_em": "2026-06-29T00:00:00+00:00",
                    "metodo_coleta": "test_fixture",
                    "status_http": 200,
                },
                {
                    "url": "https://www.linkedin.com/company/acme-ai",
                    "titulo": "Acme AI | LinkedIn",
                    "fonte_tipo": "linkedin",
                    "texto": "Acme AI helps clinics with AI automation.",
                    "coletado_em": "2026-06-29T00:00:00+00:00",
                    "metodo_coleta": "test_fixture",
                    "status_http": 200,
                },
            ],
        }
    )

    assert state["structured_startup"] is not None
    assert state["validation_report"]["status"] in {"ok", "warning", "needs_review"}
    assert state["validation_report"]["weak_evidence_ids"] == [
        "acme_ai::https_www_linkedin_com_company_acme_ai"
    ]
    assert "canonical_url" not in state["validation_report"]["unsupported_fields"]
    assert "segment" not in state["validation_report"]["unsupported_fields"]
    assert "short_description" not in state["validation_report"]["unsupported_fields"]
    assert "validator" in state["quality_flags"]
    assert "extractor" in state["quality_flags"]
    assert state["final_briefing"]
    assert isinstance(state.get("logs"), list)
