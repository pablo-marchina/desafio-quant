import unittest

from agents.nvidia import briefing_agent as briefing_module
from agents.nvidia.competitive import graph as competitive_graph_module
from agents.nvidia.briefing_agent import (
    clean_briefing,
    compact_competitive_payload,
)
from agents.nvidia.graph import (
    infer_output_mode,
    route_after_rag,
    route_after_recommendation,
)
from agents.nvidia.competitive.graph import (
    route_after_scraper,
    route_after_validation,
)
from agents.nvidia.startup_context_agent import route_after_startup_context


def test_competitive_graph_retries_after_scraper_rejection(monkeypatch):
    scraper_calls = 0

    def fake_search_string(_):
        return {
            "search_string_gerada": "business analytics SaaS",
            "categoria_funcional": "analytics empresarial",
            "bigtech_candidatos_testados": [],
            "bigtech_tentativas": 0,
            "bigtech_validacao_status": "pendente",
            "dados_insuficientes": [],
        }

    def fake_scraper(_):
        nonlocal scraper_calls
        scraper_calls += 1
        return {
            "bigtech_tentativas": scraper_calls,
            "bigtech_validacao_status": (
                "rejeitado" if scraper_calls == 1 else "esgotado"
            ),
        }

    monkeypatch.setattr(
        competitive_graph_module,
        "search_string_generator_agent",
        fake_search_string,
    )
    monkeypatch.setattr(
        competitive_graph_module,
        "bigtech_scraper_agent",
        fake_scraper,
    )
    monkeypatch.setattr(
        competitive_graph_module,
        "competitive_synthesis_agent",
        lambda _: {"structured_output": {}},
    )
    monkeypatch.setattr(
        competitive_graph_module,
        "briefing_agent",
        lambda _: {"briefing": "concluído"},
    )

    result = competitive_graph_module.build_competitive_graph().invoke({})

    assert scraper_calls == 2
    assert result["bigtech_validacao_status"] == "esgotado"
    assert result["briefing"] == "concluído"


class AgentGraphTests(unittest.TestCase):
    def test_rag_mode_ends_after_rag_agent(self):
        self.assertEqual(route_after_rag({"output_mode": "rag"}), "end")

    def test_recommendation_mode_ends_after_recommendation_agent(self):
        self.assertEqual(
            route_after_recommendation({"output_mode": "recommendation"}),
            "end",
        )

    def test_briefing_mode_runs_complete_flow(self):
        self.assertEqual(route_after_rag({"output_mode": "briefing"}), "recommendation")
        self.assertEqual(
            route_after_recommendation({"output_mode": "briefing"}),
            "briefing",
        )

    def test_competitive_mode_runs_on_demand_flow(self):
        self.assertEqual(
            route_after_recommendation({"output_mode": "competitive"}),
            "competitive",
        )

    def test_user_commands_select_distinct_flows(self):
        self.assertEqual(
            infer_output_mode("comparar com big techs"), "competitive"
        )
        self.assertEqual(infer_output_mode("match NVIDIA"), "recommendation")
        self.assertEqual(infer_output_mode("produza um briefing"), "briefing")

    def test_startup_lookup_failure_stops_before_rag(self):
        self.assertEqual(
            route_after_startup_context(
                {"startup_lookup_status": "nao_encontrada"}
            ),
            "end",
        )
        self.assertEqual(
            route_after_startup_context({"startup_lookup_status": "encontrada"}),
            "rag",
        )

    def test_rejected_candidate_loops_and_exhausted_search_continues(self):
        self.assertEqual(
            route_after_validation({"bigtech_validacao_status": "rejeitado"}),
            "scraper",
        )
        self.assertEqual(
            route_after_validation({"bigtech_validacao_status": "esgotado"}),
            "synthesis",
        )
        self.assertEqual(
            route_after_scraper({"bigtech_validacao_status": "esgotado"}),
            "synthesis",
        )
        self.assertEqual(
            route_after_scraper({"bigtech_validacao_status": "rejeitado"}),
            "scraper",
        )

    def test_removes_qwen_thinking_block_from_briefing(self):
        content = "<think>internal reasoning</think>\n\nFinal briefing"

        self.assertEqual(clean_briefing(content), "Final briefing")

    def test_competitive_briefing_payload_is_bounded(self):
        huge = "x" * 10000
        payload = compact_competitive_payload(
            {
                "structured_output": {
                    "schema_version": "competitive-analysis/v1",
                    "startup_estado_atual": {
                        "empresa": "Acme",
                        "servico_analisado": huge,
                        "fontes": [{"evidencia": huge}] * 20,
                    },
                    "entrega1": {
                        "gaps_identificados": [{"evidencia": huge}] * 20,
                        "recomendacoes_nvidia": [{"justificativa": huge}] * 20,
                        "resposta_rag": huge,
                    },
                    "comparacao_competitiva": {
                        "servico_bigtech_validado": {
                            "candidato_conteudo": {
                                "descricao_oficial": huge,
                                "trecho_relevante": huge,
                            }
                        },
                        "comparacao_estado_atual": {
                            "pontos_fortes_startup": [
                                {"evidencia": huge}
                            ]
                            * 20
                        },
                    },
                }
            }
        )
        import json

        self.assertLess(len(json.dumps(payload)), 15000)

    def test_competitive_briefing_falls_back_on_model_limit(self):
        class FailingCompletions:
            def create(self, **kwargs):
                raise RuntimeError("413 request too large")

        class FakeClient:
            class Chat:
                completions = FailingCompletions()

            chat = Chat()

        original_groq = briefing_module.Groq
        original_required_env = briefing_module.required_env
        try:
            briefing_module.Groq = lambda **_: FakeClient()
            briefing_module.required_env = lambda _: "key"
            result = briefing_module.briefing_agent(
                {
                    "output_mode": "competitive",
                    "structured_output": {
                        "startup_estado_atual": {
                            "empresa": "Acme",
                            "servico_analisado": "SaaS",
                        },
                        "entrega1": {
                            "gaps_identificados": [],
                            "recomendacoes_nvidia": [],
                        },
                        "comparacao_competitiva": {
                            "status_validacao": "esgotado"
                        },
                        "dados_insuficientes": ["sem equivalente"],
                    },
                }
            )
        finally:
            briefing_module.Groq = original_groq
            briefing_module.required_env = original_required_env
        self.assertIn("Acme", result["final_answer"])
        self.assertIn("sem equivalente", result["final_answer"])


if __name__ == "__main__":
    unittest.main()
