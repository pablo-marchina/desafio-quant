from agents.nvidia import startup_context_agent as agent


def test_preloaded_context_skips_detection_and_enrichment(monkeypatch):
    monkeypatch.setattr(
        agent,
        "detect_startup_request",
        lambda _: (_ for _ in ()).throw(
            AssertionError("preloaded startup must not be detected again")
        ),
    )
    result = agent.startup_context_agent(
        {
            "question": "Recomende para Axenya",
            "startup_context_preloaded": True,
            "empresa": "Axenya",
            "servico_startup_analisado": "Plataforma de saúde preditiva",
            "stack_atual": ["Python"],
            "output_mode": "recommendation",
        }
    )
    assert result["startup_lookup_status"] == "encontrada"
    assert "Plataforma de saúde preditiva" in result["rag_question"]


def test_no_startup_keeps_requested_mode(monkeypatch):
    monkeypatch.setattr(
        agent,
        "detect_startup_request",
        lambda _: {
            "startup_mencionada": False,
            "startup_nome": None,
            "acao": "rag",
        },
    )
    result = agent.startup_context_agent(
        {"question": "O que é NIM?", "output_mode": "briefing"}
    )
    assert result["startup_lookup_status"] == "nao_aplicavel"
    assert result["output_mode"] == "briefing"


def test_only_selected_startup_is_enriched(monkeypatch):
    candidate = {
        "id": "startup-123",
        "company_name": "Acme AI",
        "description": "Automação de relatórios industriais via SaaS",
    }
    enriched = {
        "candidate_id": "startup-123",
        "company_name": "Acme AI",
        "company_description": "Automação de relatórios industriais via SaaS",
        "validated_url": "https://acme.example",
        "tech_stack": ["Python"],
    }
    calls = []
    monkeypatch.setattr(
        agent,
        "detect_startup_request",
        lambda _: {
            "startup_mencionada": True,
            "startup_nome": "Acme AI",
            "acao": "competitive",
        },
    )
    monkeypatch.setattr(
        agent, "find_startup_candidate", lambda _: ("encontrada", candidate)
    )
    monkeypatch.setattr(
        agent.enrichment_main,
        "run",
        lambda **kwargs: calls.append(kwargs) or {"total": 1},
    )
    monkeypatch.setattr(agent, "load_enriched_startup", lambda _: enriched)

    result = agent.startup_context_agent(
        {"question": "Compare a Acme AI com big techs"}
    )

    assert calls == [
        {"company_id": "startup-123", "mode": "full", "no_cache": True}
    ]
    assert result["startup_lookup_status"] == "encontrada"
    assert result["empresa"] == "Acme AI"
    assert result["servico_startup_analisado"] == enriched["company_description"]
    assert result["output_mode"] == "competitive"


def test_missing_startup_does_not_run_enrichment(monkeypatch):
    monkeypatch.setattr(
        agent,
        "detect_startup_request",
        lambda _: {
            "startup_mencionada": True,
            "startup_nome": "Inexistente",
            "acao": "recommendation",
        },
    )
    monkeypatch.setattr(
        agent, "find_startup_candidate", lambda _: ("nao_encontrada", None)
    )
    monkeypatch.setattr(
        agent.enrichment_main,
        "run",
        lambda **_: (_ for _ in ()).throw(AssertionError("não deve enriquecer")),
    )

    result = agent.startup_context_agent(
        {"question": "Recomende NVIDIA para a Inexistente"}
    )
    assert result["startup_lookup_status"] == "nao_encontrada"
    assert "não foi encontrada" in result["final_answer"]
