"""Tests for src.scraping.parser."""

from src.scraping.parser import extract_clean_text


def test_extract_with_trafilatura() -> None:
    """Structured HTML with <article> — trafilatura should extract clean text."""
    html = (
        "<html><body><article>"
        "<h1>Test Title</h1>"
        "<p>This is a paragraph of text that should be extracted.</p>"
        "</article></body></html>"
    )
    result = extract_clean_text(html)
    assert "Test Title" in result
    assert "paragraph of text" in result


def test_extract_fallback_bs4() -> None:
    """Plain HTML without article tags — may fall back to BeautifulSoup."""
    html = "<html><body><div>Fallback content using BeautifulSoup.</div></body></html>"
    result = extract_clean_text(html)
    assert "Fallback content" in result


def test_extract_empty_html() -> None:
    result = extract_clean_text("")
    assert result == ""


def test_extract_removes_tags() -> None:
    html = "<html><body><p>Hello <b>world</b>!</p></body></html>"
    result = extract_clean_text(html)
    assert "<b>" not in result
    assert "Hello" in result
    assert "world" in result
