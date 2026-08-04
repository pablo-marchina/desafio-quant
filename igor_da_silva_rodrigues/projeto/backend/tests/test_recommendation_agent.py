from app.agents.recommendation_agent import RecommendationAgent


def _payload(technology="Triton", category="Fintech"):
    return {
        "classificacao_ia": {
            "startup": "Startup Teste",
            "classificacao": "AI-enabled",
            "nivel_maturidade": 3,
            "confianca_classificacao": 0.84,
            "justificativa": "Evidencias qualificadas.",
            "tecnologias_utilizadas": {
                "frameworks": ["PyTorch"],
                "modelos_apis": [],
                "infraestrutura": [],
                "ferramentas_mlops": [],
            },
            "necessidades_limitacoes": ["Reduzir latencia de inferencia"],
            "evidencias_suporte": ["https://startup.example/tech"],
        },
        "recomendacao_rag": {
            "startup": "Startup Teste",
            "recomendacoes": [
                {
                    "tecnologia": technology,
                    "fit_score": 0.86,
                    "justificativa": "Aderencia documentada.",
                    "dores_atendidas": ["latencia"],
                    "citacoes": [f"https://docs.nvidia.com/{technology.lower()} evidencia"],
                }
            ],
            "chunks_utilizados": [
                {
                    "chunk_id": "chunk-1",
                    "content": f"{technology} oferece recursos para serving e otimizacao de inferencia.",
                    "metadata": {
                        "tecnologia": technology,
                        "tipo": "documentacao",
                        "dores_relacionadas": ["latencia"],
                        "perfil_aplicavel": ["AI-enabled"],
                        "titulo_secao": "Overview",
                        "url_fonte": f"https://docs.nvidia.com/{technology.lower()}",
                    },
                    "retrieval_score": 0.9,
                }
            ],
        },
        "startup_profile": {"categoria": category, "descricao_curta": "Plataforma financeira"},
    }


def test_recommendation_agent_prioritizes_and_preserves_grounding():
    result = RecommendationAgent().refine(_payload())
    refined = result.recomendacao_refinada

    assert refined.fit_score > 0.8
    assert refined.tecnologias_priorizadas[0].tecnologia == "Triton"
    assert refined.tecnologias_priorizadas[0].fase == "curto_prazo"
    assert refined.tecnologias_priorizadas[0].fontes_evidencia == [
        "https://docs.nvidia.com/triton"
    ]
    assert refined.roadmap["curto_prazo"].tecnologias == ["Triton"]
    assert refined.perguntas_startup


def test_recommendation_agent_flags_vertical_mismatch_without_removing_technology():
    result = RecommendationAgent().refine(_payload("Isaac", category="Fintech"))

    assert result.recomendacao_refinada.tecnologias_priorizadas[0].tecnologia == "Isaac"
    assert any("aderencia depende" in alert for alert in result.recomendacao_refinada.alertas)


def test_recommendation_agent_handles_empty_rag_recommendation():
    payload = _payload()
    payload["recomendacao_rag"]["recomendacoes"] = []
    payload["recomendacao_rag"]["chunks_utilizados"] = []
    payload["recomendacao_rag"]["aviso"] = "Sem recomendacao fundamentada."

    result = RecommendationAgent().refine(payload)

    assert result.recomendacao_refinada.fit_score == 0
    assert result.recomendacao_refinada.tecnologias_priorizadas == []
    assert result.recomendacao_refinada.alertas == ["Sem recomendacao fundamentada."]


def test_recommendation_agent_removes_markdown_links_from_benefit():
    payload = _payload()
    payload["recomendacao_rag"]["chunks_utilizados"][0]["content"] = (
        "Triton oferece [metricas oficiais](https://docs.nvidia.com/triton/metrics) "
        "para avaliar o serving de modelos."
    )

    result = RecommendationAgent().refine(payload)
    benefit = result.recomendacao_refinada.tecnologias_priorizadas[0].beneficio

    assert "metricas oficiais" in benefit
    assert "](http" not in benefit
