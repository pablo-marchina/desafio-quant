from app.agents.impact_estimator_agent import ImpactEstimatorAgent
from app.core.schemas import KnowledgeMetadata, RetrievedChunk


class BenchmarkStore:
    def hybrid_search(self, query, top_k, profile):
        technology = "Triton" if "Triton" in query else "NIM"
        content = (
            "Triton benchmark reports throughput 2x higher for the evaluated workload."
            if technology == "Triton"
            else "NIM provides deployment capabilities without a numeric benchmark."
        )
        return [
            RetrievedChunk(
                chunk_id=f"{technology}-benchmark",
                content=content,
                metadata=KnowledgeMetadata(
                    tecnologia=technology,
                    tipo="documentacao",
                    dores_relacionadas=["latencia"],
                    perfil_aplicavel=["AI-enabled"],
                    titulo_secao="Benchmark",
                    url_fonte=f"https://docs.nvidia.com/{technology.lower()}/benchmark",
                ),
                retrieval_score=0.9,
            )
        ]


def _payload(technology="Triton"):
    return {
        "classificacao_ia": {
            "startup": "Startup Teste",
            "classificacao": "AI-enabled",
            "nivel_maturidade": 3,
            "confianca_classificacao": 0.8,
            "justificativa": "Evidencias qualificadas.",
            "tecnologias_utilizadas": {},
            "necessidades_limitacoes": ["Reduzir latencia"],
        },
        "recomendacao_refinada": {
            "startup": "Startup Teste",
            "recomendacao_refinada": {
                "tecnologias_priorizadas": [
                    {
                        "tecnologia": technology,
                        "ordem": 1,
                        "fase": "curto_prazo",
                        "problema_resolvido": "Reduzir latencia.",
                        "beneficio": "Beneficio depende de validacao.",
                        "dependencias": ["containerizacao"],
                        "riscos": "Validar em prova de conceito.",
                        "complexidade": "media",
                        "fontes_evidencia": [f"https://docs.nvidia.com/{technology.lower()}"],
                    }
                ],
                "roadmap": {
                    "curto_prazo": {"tecnologias": [technology], "acoes": ["Executar POC."]},
                    "medio_prazo": {"tecnologias": [], "acoes": []},
                    "longo_prazo": {"tecnologias": [], "acoes": []},
                },
                "fit_score": 0.86,
                "alertas": [],
                "perguntas_startup": [],
            },
        },
    }


def test_impact_estimator_uses_only_sourced_quantitative_benchmark():
    result = ImpactEstimatorAgent(store=BenchmarkStore()).estimate(_payload())
    estimate = result.estimativas_impacto[0]

    assert "2x" in estimate.impacto_tecnico.vazao
    assert estimate.confianca == "alta"
    assert "https://docs.nvidia.com/triton/benchmark" in estimate.fontes_evidencia
    assert result.indice_impacto_agregado > 0
    assert "requisicoes por segundo" in result.kpis_sugeridos


def test_impact_estimator_marks_missing_benchmark_as_uncertain():
    result = ImpactEstimatorAgent(store=BenchmarkStore()).estimate(_payload("NIM"))
    estimate = result.estimativas_impacto[0]

    assert estimate.impacto_tecnico.latencia.startswith("A mensurar")
    assert estimate.confianca == "media"
    assert any("nenhum benchmark quantitativo" in item for item in result.incertezas)


def test_impact_estimator_does_not_invent_roi_without_current_cost():
    result = ImpactEstimatorAgent().estimate(_payload())
    estimate = result.estimativas_impacto[0]

    assert "USD" not in estimate.impacto_tecnico.custo
    assert "A mensurar" in estimate.impacto_tecnico.custo
