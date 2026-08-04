"""Testes da compactacao de textos enviados aos agentes."""

from apps.api.src.modules.startups.application.evidence_text_cleaner import (
    MAX_EVIDENCE_CHARS_FOR_EXTRACTION,
    compact_evidence_text,
)


def test_compact_evidence_text_keeps_ai_signals_and_drops_navigation_noise() -> None:
    raw = "\n".join(
        [
            "[evidence_id=ev-1]",
            "Menu",
            "Newsletter",
            "NeuralMind",
            "NeuralMind",
            "Desenvolvemos Agentes de IA que buscam as informacoes certas.",
            "A NeuralMind foi pioneira no treinamento do BERTimbau.",
            "O NeuralSearchX usa busca semantica e LLMs em documentos.",
            "Related posts",
            "Welcome Back!",
            "Login to your account below",
            "Terms of Service",
            "Privacy Policy",
        ]
    )

    compacted = compact_evidence_text(raw)

    assert compacted.startswith("[evidence_id=ev-1]")
    assert "Agentes de IA" in compacted
    assert "BERTimbau" in compacted
    assert "NeuralSearchX" in compacted
    assert "newsletter" not in compacted.lower()
    assert "login" not in compacted.lower()
    assert "NeuralMind NeuralMind" not in compacted


def test_compact_evidence_text_limits_large_low_signal_pages() -> None:
    raw = "\n".join(
        [
            "[evidence_id=ev-2]",
            "NeuralMind cria modelos proprietarios de IA para NLP em producao.",
            *[f"Linha generica de baixa informacao {index}" for index in range(200)],
            "PrioScan utiliza IA para priorizar exames em hospitais.",
        ]
    )

    compacted = compact_evidence_text(raw)

    assert len(compacted) <= MAX_EVIDENCE_CHARS_FOR_EXTRACTION
    assert "modelos proprietarios de IA" in compacted
    assert "PrioScan utiliza IA" in compacted
    assert "Linha generica de baixa informacao 199" not in compacted
