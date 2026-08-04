from datetime import UTC, datetime

from app.agents.briefing_generator_agent import BriefingGeneratorAgent


def _payload():
    return {
        "startup_profile": {
            "startup_name": "Startup Teste",
            "site_oficial": "https://startup.example",
            "categoria": "Fintech",
            "descricao_curta": "Plataforma financeira com IA.",
            "cidade": "Sao Paulo",
            "estado": "SP",
            "pais": "Brasil",
        },
        "classificacao_ia": {
            "startup": "Startup Teste",
            "classificacao": "AI-enabled",
            "nivel_maturidade": 3,
            "confianca_classificacao": 0.84,
            "justificativa": "Evidencias qualificadas.",
            "tecnologias_utilizadas": {},
            "necessidades_limitacoes": ["Reduzir latencia"],
        },
        "recomendacao_refinada": {
            "startup": "Startup Teste",
            "recomendacao_refinada": {
                "tecnologias_priorizadas": [
                    {
                        "tecnologia": "Triton",
                        "ordem": 1,
                        "fase": "curto_prazo",
                        "problema_resolvido": "Latencia.",
                        "beneficio": "Serving de modelos documentado pela NVIDIA.",
                        "dependencias": ["containerizacao"],
                        "riscos": "Validar em POC.",
                        "complexidade": "media",
                        "fontes_evidencia": ["https://docs.nvidia.com/triton"],
                    }
                ],
                "roadmap": {
                    "curto_prazo": {"tecnologias": ["Triton"], "acoes": ["Executar POC."]},
                    "medio_prazo": {"tecnologias": [], "acoes": []},
                    "longo_prazo": {"tecnologias": [], "acoes": []},
                },
                "fit_score": 0.86,
                "alertas": [],
                "perguntas_startup": ["Qual o baseline de latencia?"],
            },
        },
        "estimativa_impacto": {
            "startup": "Startup Teste",
            "estimativas_impacto": [
                {
                    "tecnologia": "Triton",
                    "impacto_tecnico": {
                        "latencia": "A mensurar em prova de conceito.",
                        "custo": "A mensurar em prova de conceito.",
                        "vazao": "Benchmark oficial reporta 2x no workload avaliado.",
                        "escalabilidade": "A mensurar em prova de conceito.",
                        "governanca_seguranca": "A mensurar em prova de conceito.",
                    },
                    "impacto_negocio": "Validar impacto no produto.",
                    "fontes_evidencia": ["https://docs.nvidia.com/triton/benchmark"],
                    "confianca": "alta",
                    "premissas": ["Workload representativo."],
                }
            ],
            "indice_impacto_agregado": 77,
            "kpis_sugeridos": ["p99 latency (ms)"],
            "incertezas": ["Baseline nao informado."],
            "resumo_executivo": "Potencial condicionado a POC.",
        },
        "validacao_evidencias": {
            "startup": "Startup Teste",
            "evidencias_validadas": [],
            "evidencias_medias": [],
            "evidencias_descartadas": [],
            "resumo_consolidado": {
                "tecnologias_detectadas": [],
                "fontes_corroboradas": 0,
                "afirmacoes_chave": [],
                "nota_geral_qualidade_evidencias": 0.8,
            },
            "erros_validacao": [],
        },
    }


def test_briefing_generator_renders_required_sections_and_sources():
    agent = BriefingGeneratorAgent(now=lambda: datetime(2026, 6, 27, tzinfo=UTC))
    markdown = agent.generate(_payload())

    assert markdown.startswith("# Briefing NVIDIA Inception - Startup Teste")
    assert "**Data:** 2026-06-27" in markdown
    for section in range(1, 10):
        assert f"## {section}." in markdown
    assert "## 3. Aderencia ao NVIDIA Inception" in markdown
    assert "Elegibilidade:** unknown" in markdown
    assert "| Triton | Curto Prazo |" in markdown
    assert "https://docs.nvidia.com/triton/benchmark" in markdown
    assert "77/100" in markdown


def test_briefing_generator_does_not_add_unsupported_percentages():
    agent = BriefingGeneratorAgent(now=lambda: datetime(2026, 6, 27, tzinfo=UTC))
    markdown = agent.generate(_payload())

    assert "reducao de 60%" not in markdown.lower()
    assert "A mensurar" in markdown
    assert len(markdown) < 12000
