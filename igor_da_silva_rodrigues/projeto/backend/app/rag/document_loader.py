from __future__ import annotations

import re
import unicodedata
from typing import Any

import fitz
import requests

from app.agents.scraper_agent import FirecrawlClient, TrafilaturaExtractor, USER_AGENT
from app.core.schemas import KnowledgeSourceInput, LoadedKnowledgeDocument


class NVIDIADocumentLoader:
    def __init__(
        self,
        session: requests.Session | None = None,
        firecrawl_client: Any | None = None,
        trafilatura_extractor: Any | None = None,
        timeout: int = 30,
    ) -> None:
        self.session = session or requests.Session()
        self.timeout = timeout
        self.firecrawl = firecrawl_client or FirecrawlClient(self.session, timeout=timeout)
        self.trafilatura = trafilatura_extractor or TrafilaturaExtractor(self.session, timeout=timeout)

    def load(self, source: KnowledgeSourceInput) -> LoadedKnowledgeDocument:
        if source.url.lower().endswith(".pdf"):
            content = self._load_pdf(source.url)
        else:
            content = self._load_html(source.url)
        cleaned = clean_document_text(content)
        if len(cleaned) < 100:
            raise ValueError(f"Conteúdo insuficiente em {source.url}")
        return LoadedKnowledgeDocument(titulo=source.titulo, content=cleaned, source=source)

    def _load_html(self, url: str) -> str:
        try:
            page = self.firecrawl.scrape(url)
            return page.get("conteudo_markdown") or page.get("conteudo_textual") or ""
        except (requests.RequestException, ValueError):
            page = self.trafilatura.extract(url)
            return page.get("conteudo_textual") or ""

    def _load_pdf(self, url: str) -> str:
        response = self.session.get(
            url,
            headers={"User-Agent": USER_AGENT},
            timeout=self.timeout,
        )
        response.raise_for_status()
        document = fitz.open(stream=response.content, filetype="pdf")
        return "\n".join(page.get_text("text") for page in document)


def clean_document_text(text: str) -> str:
    normalized = unicodedata.normalize("NFKC", text).replace("\ufffd", "")
    lines = [re.sub(r"\s+", " ", line).strip() for line in normalized.splitlines()]
    frequency: dict[str, int] = {}
    for line in lines:
        if line:
            frequency[line] = frequency.get(line, 0) + 1

    cleaned = []
    previous = None
    for line in lines:
        if not line or line == previous:
            continue
        if frequency.get(line, 0) > 3 and len(line) < 120 and not line.startswith("#"):
            continue
        cleaned.append(line)
        previous = line
    return "\n".join(cleaned).strip()
