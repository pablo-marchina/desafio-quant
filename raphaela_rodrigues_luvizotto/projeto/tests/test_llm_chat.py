from __future__ import annotations

from src.api import llm_chat


class _FakeResponse:
    def __init__(self, content: str) -> None:
        self.content = content


class _FakeChatGroqOk:
    def __init__(self, **kwargs) -> None:
        self.kwargs = kwargs

    def invoke(self, messages):
        return _FakeResponse("Resposta via Groq.")


class _FakeChatGroqRateLimit:
    def __init__(self, **kwargs) -> None:
        self.kwargs = kwargs

    def invoke(self, messages):
        raise RuntimeError("Error code: 429 - rate_limit_exceeded")


def test_answer_chat_message_falls_back_when_rag_is_unavailable(monkeypatch):
    monkeypatch.setattr(llm_chat, "GROQ_API_KEY", "test-key")

    def _raise_rag_error(query: str):
        raise RuntimeError("sentence-transformers nao esta instalado")

    monkeypatch.setattr(llm_chat, "answer_query", _raise_rag_error)
    monkeypatch.setattr(llm_chat, "ChatGroq", _FakeChatGroqOk)

    result = llm_chat.answer_chat_message(
        "Quais produtos NVIDIA fazem sentido?",
        {"name": "NeuralCare AI", "summary": "Health AI"},
    )

    assert result["answer"] == "Resposta via Groq."
    assert result["provider"] == "groq"
    assert result["ragStatus"] == "fallback"
    assert "sentence-transformers" in result["ragWarning"]
    assert result["sources"] == []


def test_answer_chat_message_uses_openrouter_when_groq_fails(monkeypatch):
    monkeypatch.setattr(llm_chat, "GROQ_API_KEY", "test-key")
    monkeypatch.setattr(llm_chat, "OPENROUTER_API_KEY", "openrouter-key")
    monkeypatch.setattr(llm_chat, "ChatGroq", _FakeChatGroqRateLimit)
    monkeypatch.setattr(
        llm_chat,
        "answer_query",
        lambda query: llm_chat.RagResult(query=query, summary="", items=[], metadata={}),
    )

    def _fake_openrouter(messages):
        return "Resposta via OpenRouter.", "openrouter"

    monkeypatch.setattr(llm_chat, "_invoke_openrouter", _fake_openrouter)

    result = llm_chat.answer_chat_message(
        "Quais produtos NVIDIA fazem sentido?",
        {"name": "NeuralCare AI", "summary": "Health AI"},
    )

    assert result["answer"] == "Resposta via OpenRouter."
    assert result["provider"] == "openrouter"
    assert any("groq:" in item for item in result["providerErrors"])


def test_answer_chat_message_uses_local_fallback_when_all_llms_fail(monkeypatch):
    monkeypatch.setattr(llm_chat, "GROQ_API_KEY", "test-key")
    monkeypatch.setattr(llm_chat, "OPENROUTER_API_KEY", "openrouter-key")
    monkeypatch.setattr(llm_chat, "ChatGroq", _FakeChatGroqRateLimit)
    monkeypatch.setattr(
        llm_chat,
        "answer_query",
        lambda query: llm_chat.RagResult(query=query, summary="", items=[], metadata={}),
    )

    def _raise_openrouter(messages):
        raise RuntimeError("OpenRouter indisponivel")

    monkeypatch.setattr(llm_chat, "_invoke_openrouter", _raise_openrouter)

    result = llm_chat.answer_chat_message(
        "Quais produtos NVIDIA fazem sentido?",
        {
            "name": "NeuralCare AI",
            "summary": "Health AI",
            "classification": "AI-native candidata",
            "recommendations": [{"nextStep": "Agendar conversa tecnica."}],
        },
    )

    assert result["provider"] == "local_fallback"
    assert "Health AI" in result["answer"]
    assert "Agendar conversa tecnica." in result["answer"]
    assert any("groq:" in item for item in result["providerErrors"])
    assert any("openrouter:" in item for item in result["providerErrors"])
