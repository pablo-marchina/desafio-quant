"""HTML parsing helpers for extracting clean text from fetched pages."""

from __future__ import annotations

import logging

from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

try:
    import trafilatura
except ImportError:
    trafilatura = None

try:
    from selectolax.parser import HTMLParser as SelectolaxParser
except ImportError:
    SelectolaxParser = None

try:
    from readability import Document as ReadabilityDoc
except ImportError:
    ReadabilityDoc = None


def extract_clean_text(raw_html: str) -> str:
    """Extract readable text from HTML using the best available parser.

    Priority: readability-lxml (article) > trafilatura > selectolax > bs4.
    """
    if ReadabilityDoc is not None:
        try:
            doc = ReadabilityDoc(raw_html)
            summary = doc.summary()
            if summary:
                soup = BeautifulSoup(summary, "html.parser")
                text = soup.get_text(separator=" ", strip=True)
                if len(text) > 100:
                    return text
        except Exception as exc:
            logger.debug("readability-lxml parser failed: %s", exc)

    if trafilatura is not None:
        try:
            extracted = trafilatura.extract(raw_html)
            if extracted:
                text = extracted.strip()
                if len(text) > 50:
                    return text
        except Exception as exc:
            logger.debug("trafilatura parser failed: %s", exc)

    if SelectolaxParser is not None:
        try:
            parser = SelectolaxParser(raw_html)
            body = parser.root
            if body is not None:
                text = body.text(separator=" ", strip=True)
                if text.strip():
                    return text.strip()
        except Exception as exc:
            logger.debug("selectolax parser failed: %s", exc)

    soup = BeautifulSoup(raw_html, "html.parser")
    return soup.get_text(separator=" ", strip=True)
