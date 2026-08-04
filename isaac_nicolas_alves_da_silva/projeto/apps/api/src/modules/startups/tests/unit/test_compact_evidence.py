from apps.api.src.modules.startups.application.evidence_text_cleaner import (
    MAX_EVIDENCE_CHARS_FOR_EXTRACTION,
    compact_evidence_text,
)


def test_collapses_whitespace() -> None:
    assert compact_evidence_text("a\n\n   b\t c") == "a b c"


def test_caps_length() -> None:
    out = compact_evidence_text("x " * 10000)
    assert len(out) <= MAX_EVIDENCE_CHARS_FOR_EXTRACTION


def test_keeps_body_words() -> None:
    txt = "Menu Home Contato " + "NeuralMind treina modelos BERT em portugues " * 3
    assert "BERT" in compact_evidence_text(txt)


def test_removes_short_navigation_and_newsletter_lines() -> None:
    txt = "\n".join(
        [
            "Menu",
            "Copa do Mundo FIFA",
            "Assine nossa newsletter",
            "NeuralMind treina modelos BERT em portugues para NLP juridico.",
        ]
    )

    out = compact_evidence_text(txt)

    assert "Menu" not in out
    assert "newsletter" not in out
    assert "Copa do Mundo FIFA" not in out
    assert "BERT" in out


def test_deduplicates_repeated_lines() -> None:
    txt = "\n".join(
        [
            "NeuralMind desenvolve IA para visao computacional.",
            "NeuralMind desenvolve IA para visao computacional.",
            "Clientes usam a plataforma em producao.",
        ]
    )

    out = compact_evidence_text(txt)

    assert out.count("NeuralMind desenvolve") == 1
    assert "Clientes usam" in out
