from agents.nvidia import gap_analysis_agent as agent


def test_generic_description_does_not_become_gap(monkeypatch):
    monkeypatch.setattr(
        agent,
        "call_json",
        lambda *_: {
            "gaps_identificados": [
                {
                    "gap": "falta de baixa latência",
                    "evidencia": "opera em mais de 1.000 plantas",
                    "fonte": "https://tractian.com",
                }
            ]
        },
    )
    result = agent.gap_analysis_agent(
        {
            "startup_mencionada": True,
            "question": "Qual serviço NVIDIA é recomendado para a Tractian?",
            "original_question": "Qual serviço NVIDIA é recomendado para a Tractian?",
            "empresa": "Tractian",
            "pontos_fortes": [
                {
                    "aspecto": "escala",
                    "evidencia": "opera em mais de 1.000 plantas",
                    "fonte": "https://tractian.com",
                }
            ],
        }
    )
    assert result["gaps_identificados"] == []
    assert result["dados_insuficientes"]


def test_explicit_user_need_can_become_documented_gap(monkeypatch):
    evidence = "A Tractian precisa reduzir latência"
    monkeypatch.setattr(
        agent,
        "call_json",
        lambda *_: {
            "gaps_identificados": [
                {
                    "gap": "latência elevada",
                    "evidencia": evidence,
                    "fonte": "Pergunta do usuário",
                }
            ]
        },
    )
    result = agent.gap_analysis_agent(
        {
            "startup_mencionada": True,
            "question": evidence,
            "original_question": evidence,
            "empresa": "Tractian",
            "pontos_fortes": [],
        }
    )
    assert result["gaps_identificados"] == [
        {
            "gap": "latência elevada",
            "evidencia": evidence,
            "fonte": "Pergunta do usuário",
        }
    ]


def test_api_documented_need_becomes_gap_without_llm(monkeypatch):
    monkeypatch.setattr(
        agent,
        "call_json",
        lambda *_: (_ for _ in ()).throw(
            AssertionError("LLM should not reinterpret explicit user input")
        ),
    )
    result = agent.gap_analysis_agent(
        {
            "startup_mencionada": True,
            "empresa": "Axenya",
            "user_documented_need": (
                "escalar a análise preditiva para 500 mil vidas"
            ),
        }
    )
    assert result["gaps_identificados"] == [
        {
            "gap": "escalar a análise preditiva para 500 mil vidas",
            "evidencia": (
                "Axenya precisa escalar a análise preditiva para 500 mil vidas."
            ),
            "fonte": "Necessidade informada pelo usuário",
        }
    ]
