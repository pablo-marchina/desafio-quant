from app.agents.inception_fit_agent import InceptionFitAgent


def _payload():
    return {
        "startup_profile": {
            "startup_name": "Startup Teste",
            "dados_adicionais": {},
        },
        "classificacao_ia": {
            "startup": "Startup Teste",
            "classificacao": "AI-enabled",
            "nivel_maturidade": 3,
            "confianca_classificacao": 0.82,
            "justificativa": "Evidencias tecnicas publicas.",
            "tecnologias_utilizadas": {},
            "necessidades_limitacoes": [],
            "evidencias_suporte": [],
        },
    }


def test_inception_fit_keeps_unknown_when_evidence_is_missing():
    result = InceptionFitAgent().assess(_payload())

    assert result["eligibility_status"] == "unknown"
    assert result["startup_stage"] == "unknown"
    assert result["benefit_matches"] == []
    assert all(item["status"] == "unknown" for item in result["needs"])
    assert len(result["open_questions"]) == 3


def test_inception_fit_uses_only_explicit_eligibility_and_stage_signals():
    payload = _payload()
    payload["startup_profile"]["dados_adicionais"] = {
        "funding_round": "seed",
        "inception": {"eligibility_confirmed": True},
    }
    payload["classificacao_ia"]["necessidades_limitacoes"] = [
        "Reduzir custo de infraestrutura GPU e latencia de inferencia."
    ]
    payload["classificacao_ia"]["evidencias_suporte"] = [
        "https://startup.example/tecnologia"
    ]

    result = InceptionFitAgent().assess(payload)

    assert result["eligibility_status"] == "eligible"
    assert result["startup_stage"] == "early"
    identified = {item["need"] for item in result["needs"] if item["status"] == "identified"}
    assert {"credits", "technical_support", "infrastructure"}.issubset(identified)
    assert all(match["source_urls"][0].startswith("https://www.nvidia.com") for match in result["benefit_matches"])


def test_non_ai_classification_does_not_imply_ineligibility():
    payload = _payload()
    payload["classificacao_ia"].update(
        {"classificacao": "Non-AI", "nivel_maturidade": 0}
    )

    result = InceptionFitAgent().assess(payload)

    assert result["eligibility_status"] == "unknown"
