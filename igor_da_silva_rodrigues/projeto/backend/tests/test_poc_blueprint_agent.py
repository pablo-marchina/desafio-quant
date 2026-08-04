from app.agents.poc_blueprint_agent import POCBlueprintAgent


def test_poc_blueprint_is_grounded_and_measurable():
    refinement = {
        "refinement_json": {
            "recomendacao_refinada": {
                "tecnologias_priorizadas": [
                    {
                        "tecnologia": "Triton",
                        "fase": "curto_prazo",
                        "problema_resolvido": "Reduzir gargalos de inferencia.",
                        "dependencias": ["modelos versionados"],
                        "riscos": "Exige baseline.",
                        "fontes_evidencia": ["https://docs.nvidia.com/triton/"],
                    }
                ]
            }
        }
    }
    impact = {
        "impact_json": {
            "kpis_sugeridos": ["p99 latency (ms)"],
            "incertezas": ["Volume atual nao informado."],
            "estimativas_impacto": [],
        }
    }

    result = POCBlueprintAgent().generate("Startup Teste", refinement, impact)

    assert result["workstreams"][0]["technology"] == "Triton"
    assert "Baseline medido" in result["workstreams"][0]["acceptance_criteria"][0]
    assert "https://docs.nvidia.com/triton/" in result["markdown"]
    assert "sem assumir ganhos" in result["purpose"]
