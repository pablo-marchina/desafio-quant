"""Testes unitarios do reescritor de prosa Gemini via LangChain."""

import pytest

from apps.api.src.modules.agents.domain.exceptions import AgentBriefingError
from apps.api.src.modules.agents.infrastructure.llm.langchain_gemini_briefing_prose_rewriter import (
    BriefingProseResponse,
    LangChainGeminiBriefingProseRewriter,
)

ORIGINAL_CONTENT = (
    "# Briefing Executivo — Acme AI\n\n"
    "## Evidencias Principais\n"
    "- [Site oficial](https://acme.example.com/about) — website\n\n"
    "## Proximas Acoes\n"
    "- Agendar conversa tecnica.\n"
)


class FakeStructuredModel:
    def __init__(self, response: BriefingProseResponse) -> None:
        self.response = response
        self.received_messages = None

    async def ainvoke(self, messages, config=None):
        self.received_messages = messages
        return self.response


class FailingStructuredModel:
    async def ainvoke(self, messages, config=None):
        raise RuntimeError("Gemini timeout simulado")


def test_rewriter_requires_api_key() -> None:
    with pytest.raises(ValueError):
        LangChainGeminiBriefingProseRewriter(api_key="", model="gemini-test")


def test_rewriter_requires_model() -> None:
    with pytest.raises(ValueError):
        LangChainGeminiBriefingProseRewriter(api_key="fake-key", model="")


@pytest.mark.anyio
async def test_rewrite_returns_llm_content_when_citations_preserved() -> None:
    rewritten = (
        "# Briefing Executivo — Acme AI\n\n"
        "## Evidencias Principais\n"
        "- [Site oficial](https://acme.example.com/about) — pagina institucional\n\n"
        "## Proximas Acoes\n"
        "- Marcar reuniao tecnica com o time da Acme.\n"
    )
    structured_model = FakeStructuredModel(BriefingProseResponse(content=rewritten))
    rewriter = LangChainGeminiBriefingProseRewriter(
        api_key="fake-key",
        model="gemini-test",
        structured_model=structured_model,
    )

    result = await rewriter.rewrite(ORIGINAL_CONTENT)

    assert result == rewritten


@pytest.mark.anyio
async def test_rewrite_falls_back_to_original_when_citation_is_lost() -> None:
    """Guarda em codigo: se a reescrita perder uma URL, devolve o original."""

    rewritten_without_citation = (
        "# Briefing Executivo — Acme AI\n\n"
        "## Evidencias Principais\n"
        "- Acme tem presenca online solida.\n\n"
        "## Proximas Acoes\n"
        "- Marcar reuniao tecnica.\n"
    )
    structured_model = FakeStructuredModel(
        BriefingProseResponse(content=rewritten_without_citation)
    )
    rewriter = LangChainGeminiBriefingProseRewriter(
        api_key="fake-key",
        model="gemini-test",
        structured_model=structured_model,
    )

    result = await rewriter.rewrite(ORIGINAL_CONTENT)

    assert result == ORIGINAL_CONTENT


@pytest.mark.anyio
async def test_rewrite_without_urls_in_original_always_passes_through() -> None:
    content_without_urls = "# Briefing Executivo — Acme AI\n\nSem evidencias ainda.\n"
    rewritten = "# Briefing Executivo — Acme AI\n\nNenhuma evidencia coletada ainda.\n"
    structured_model = FakeStructuredModel(BriefingProseResponse(content=rewritten))
    rewriter = LangChainGeminiBriefingProseRewriter(
        api_key="fake-key",
        model="gemini-test",
        structured_model=structured_model,
    )

    result = await rewriter.rewrite(content_without_urls)

    assert result == rewritten


@pytest.mark.anyio
async def test_rewrite_wraps_llm_failure() -> None:
    rewriter = LangChainGeminiBriefingProseRewriter(
        api_key="fake-key",
        model="gemini-test",
        structured_model=FailingStructuredModel(),
    )

    with pytest.raises(AgentBriefingError):
        await rewriter.rewrite(ORIGINAL_CONTENT)


def test_build_messages_sends_full_content() -> None:
    rewriter = LangChainGeminiBriefingProseRewriter(
        api_key="fake-key",
        model="gemini-test",
        structured_model=FakeStructuredModel(BriefingProseResponse(content="x")),
    )

    messages = rewriter._build_messages(ORIGINAL_CONTENT)

    assert len(messages) == 2
    assert "Briefing Agent" in messages[0].content
    assert messages[1].content == ORIGINAL_CONTENT
