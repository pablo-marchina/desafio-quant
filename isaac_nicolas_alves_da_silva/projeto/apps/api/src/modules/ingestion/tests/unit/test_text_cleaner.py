"""Testes do TextCleaner."""

from apps.api.src.modules.ingestion.application.text_cleaner import TextCleaner


def _clean(text: str) -> str:
    return TextCleaner().clean(text)


def test_clean_empty_string() -> None:
    assert _clean("") == ""


def test_clean_none_like_empty() -> None:
    assert _clean("   ") == ""


def test_clean_normalizes_crlf() -> None:
    result = _clean("linha1\r\nlinha2\rlinha3")
    assert "\r" not in result
    assert result == "linha1\nlinha2\nlinha3"


def test_clean_removes_control_characters() -> None:
    text = "hello\x01world\x07!\x1f"
    result = _clean(text)
    # Chars de controle sao removidos (nao substituidos por espaco)
    assert result == "helloworld!"
    assert "\x01" not in result
    assert "\x07" not in result


def test_clean_collapses_multiple_blank_lines() -> None:
    text = "paragrafo1\n\n\n\nparagrafo2"
    result = _clean(text)
    assert "\n\n\n" not in result
    assert "paragrafo1" in result
    assert "paragrafo2" in result


def test_clean_trims_whitespace_in_lines() -> None:
    text = "  hello   world  \n  foo  bar  "
    result = _clean(text)
    assert result == "hello world\nfoo bar"


def test_clean_strips_leading_trailing_blank() -> None:
    text = "\n\nhello\n\n"
    result = _clean(text)
    assert result == "hello"
