from scraper.api.services.action_report_service import ActionReportService
import httpx


def test_action_report_default_model_is_paid(monkeypatch):
    monkeypatch.delenv("REPORT_OPENROUTER_MODEL", raising=False)
    monkeypatch.delenv("REPORT_OPENROUTER_FALLBACK_MODELS", raising=False)
    monkeypatch.setenv("OPENROUTER_MODEL", "openai/gpt-oss-20b:free")

    service = ActionReportService()

    assert service.model == "~google/gemini-flash-latest"
    assert "google/gemini-2.5-flash" in service.fallback_models


def test_action_report_service_calls_openrouter_and_persists(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    monkeypatch.setenv("REPORT_OPENROUTER_MODEL", "openai/gpt-oss-20b:free")
    captured = {}
    saved = {}

    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "choices": [
                    {
                        "message": {
                            "content": (
                                '{"executive_summary":"Priorizar piloto.",'
                                '"next_actions":[{"action":"Executar PoC",'
                                '"priority":"Alta"}],'
                                '"nvidia_focus":["NIM"],'
                                '"bigtech_implications":["Comparar SLA"],'
                                '"risks":["Dados insuficientes"],'
                                '"open_questions":["Orcamento?"],'
                                '"markdown_report":"### Acme — CNPJ não informado\\nRelatorio.",'
                                '"score_ai_native":82}'
                            )
                        }
                    }
                ]
            }

    def fake_post(url, **kwargs):
        captured["url"] = url
        captured["kwargs"] = kwargs
        return FakeResponse()

    class FakeStartupService:
        def update_startup(self, startup_id, data):
            saved["startup_id"] = startup_id
            saved["data"] = data
            return {"id": startup_id, **data}

    monkeypatch.setattr(
        "scraper.api.services.action_report_service.httpx.post",
        fake_post,
    )
    service = ActionReportService(FakeStartupService())

    report = service.generate(
        {
            "id": "startup-1",
            "company_name": "Acme",
            "description": "Plataforma de IA.",
            "nvidia_recommendation": {
                "recommendations": [{"produto": "NVIDIA NIM"}]
            },
            "competitive_analysis": {
                "final_answer": "Big tech tem maior escala.",
                "structured_output": {
                    "comparacao_competitiva": {
                        "servico_bigtech_validado": {
                            "candidato_empresa": "Microsoft",
                            "candidato_url": "https://azure.microsoft.com/product",
                        },
                        "comparacao_bigtechs_resumida": {
                            "equivalentes_big_tech": [
                                {"empresa": "Microsoft", "produto": "Azure AI"}
                            ]
                        },
                    }
                },
            },
        },
        lambda _: None,
        objective="priorizar proximos passos",
        context={"produto_alvo": "NIM"},
    )

    assert captured["url"].endswith("/chat/completions")
    assert captured["kwargs"]["json"]["model"] == "openai/gpt-oss-20b:free"
    payload_text = captured["kwargs"]["json"]["messages"][1]["content"]
    assert "contexto_negociado_fase_1" in payload_text
    assert "benchmark_competitivo" in payload_text
    assert report["executive_summary"] == "Priorizar piloto."
    assert report["markdown_report"].startswith("### Acme")
    assert report["benchmark_competitivo"]["posicionamento"]
    assert report["next_actions"][0]["action"] == "Executar PoC"
    assert saved["startup_id"] == "startup-1"
    assert saved["data"]["action_report"]["company_name"] == "Acme"


def test_action_report_retries_paid_fallback_on_model_404(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    monkeypatch.setenv("REPORT_OPENROUTER_MODEL", "invalid/removed-model")
    monkeypatch.setenv("REPORT_OPENROUTER_FALLBACK_MODELS", "google/gemini-2.5-flash")
    calls = []

    class FakeResponse:
        def __init__(self, status_code, model):
            self.status_code = status_code
            self.model = model

        def raise_for_status(self):
            if self.status_code >= 400:
                request = httpx.Request("POST", "https://openrouter.ai/api/v1/chat/completions")
                response = httpx.Response(self.status_code, request=request)
                raise httpx.HTTPStatusError("Not Found", request=request, response=response)

        def json(self):
            return {
                "choices": [
                    {
                        "message": {
                            "content": '{"executive_summary":"ok","markdown_report":"### Acme"}'
                        }
                    }
                ]
            }

    def fake_post(_, **kwargs):
        model = kwargs["json"]["model"]
        calls.append(model)
        return FakeResponse(404 if model == "invalid/removed-model" else 200, model)

    monkeypatch.setattr(
        "scraper.api.services.action_report_service.httpx.post",
        fake_post,
    )

    report = ActionReportService().generate(
        {
            "id": "startup-1",
            "company_name": "Acme",
            "description": "Plataforma de IA.",
            "nvidia_recommendation": {"recommendations": [{"produto": "NVIDIA NIM"}]},
        },
        lambda _: None,
    )

    assert calls == ["invalid/removed-model", "google/gemini-2.5-flash"]
    assert report["model"] == "google/gemini-2.5-flash"


def test_action_report_service_falls_back_on_openrouter_429(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    saved = {}

    class FakeResponse:
        status_code = 429

        def raise_for_status(self):
            request = httpx.Request("POST", "https://openrouter.ai/api/v1/chat/completions")
            response = httpx.Response(429, request=request)
            raise httpx.HTTPStatusError("Too Many Requests", request=request, response=response)

    class FakeStartupService:
        def update_startup(self, startup_id, data):
            saved["startup_id"] = startup_id
            saved["data"] = data
            return {"id": startup_id, **data}

    monkeypatch.setattr(
        "scraper.api.services.action_report_service.httpx.post",
        lambda *_, **__: FakeResponse(),
    )

    report = ActionReportService(FakeStartupService()).generate(
        {
            "id": "startup-1",
            "company_name": "Acme",
            "cnpj": "123",
            "description": "Plataforma de IA.",
            "ai_dependency_level": "AI_ENABLED",
            "nvidia_recommendation": {
                "recommendations": [{"produto": "NVIDIA NIM"}],
                "gaps": [{"gap": "latencia"}],
            },
        },
        lambda _: None,
        context={"produto_alvo": "recomende você mesmo"},
    )

    assert report["structured_output"]["fallback"] is True
    assert "429" in report["executive_summary"]
    assert report["markdown_report"].startswith("### Acme")
    assert saved["data"]["action_report"]["benchmark_competitivo"]["posicionamento"]


def test_action_report_service_falls_back_on_wrapped_429_message(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")

    service = ActionReportService()

    def fake_call_openrouter(*_, **__):
        raise RuntimeError(
            "Client error '429 Too Many Requests' for url "
            "'https://openrouter.ai/api/v1/chat/completions'"
        )

    monkeypatch.setattr(service, "_call_openrouter", fake_call_openrouter)

    report = service.generate(
        {
            "id": "startup-1",
            "company_name": "Acme",
            "description": "Plataforma de IA.",
            "nvidia_recommendation": {
                "recommendations": [{"produto": "NVIDIA NIM"}],
            },
        },
        lambda _: None,
    )

    assert report["structured_output"]["fallback"] is True
    assert "429" in report["executive_summary"]
