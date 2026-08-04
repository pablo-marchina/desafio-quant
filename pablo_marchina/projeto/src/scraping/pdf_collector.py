"""PDF document collector.

Downloads PDFs via httpx and extracts text using PyMuPDF (fitz).
"""

from __future__ import annotations

import logging
import tempfile
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

import httpx

from src.scraping.fetcher import _get_client
from src.scraping.strategies import register

logger = logging.getLogger(__name__)


@dataclass
class PdfResult:
    url: str
    title: str | None
    pages: int = 0
    text: str = ""
    error: str | None = None
    fetched_at: datetime = field(default_factory=lambda: datetime.now(UTC))


def extract_pdf(url: str, timeout: int = 30) -> PdfResult:
    """Download and extract text from a PDF at *url*.

    Uses the shared httpx client from ``fetcher`` for connection pooling
    and consistent user-agent / timeout handling.
    """
    result = PdfResult(url=url)
    try:
        import fitz  # PyMuPDF  # noqa: PLC0415

        client = _get_client()
        resp = client.get(url, timeout=timeout)
        resp.raise_for_status()

        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            tmp.write(resp.content)
            tmp_path = Path(tmp.name)

        try:
            doc = fitz.open(str(tmp_path))
            result.pages = len(doc)
            result.title = doc.metadata.get("title")
            text_parts: list[str] = []
            for page in doc:
                text_parts.append(page.get_text())
            result.text = "\n\n".join(text_parts).strip()
            doc.close()
            logger.info("PDF_OK  url=%s  pages=%d  chars=%d", url, result.pages, len(result.text))
        finally:
            tmp_path.unlink(missing_ok=True)

    except httpx.HTTPStatusError as exc:
        result.error = f"HTTP {exc.response.status_code}: {exc}"
    except httpx.TimeoutException as exc:
        result.error = f"Timeout after {timeout}s: {exc}"
    except Exception as exc:
        result.error = f"{type(exc).__name__}: {exc}"

    return result


@register("pdf")
def collect_pdf(source) -> PdfResult | None:
    from src.scraping.source_registry import SourceRecord

    if not isinstance(source, SourceRecord):
        return None

    return extract_pdf(source.base_url)
