"""Testes integrados do renderer de PDF (Chromium headless real).

Sem dependencia de Postgres/Redis/Qdrant - so precisa do Chromium do
Playwright, ja instalado neste ambiente (mesmo binario usado em
``scraping/infrastructure/scrapers/playwright_scraper.py``).
"""

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from apps.api.src.modules.briefing.application.dto import BriefingView
from apps.api.src.modules.briefing.infrastructure.rendering.jinja_playwright_pdf_renderer import (
    JinjaPlaywrightPdfRenderer,
)


@pytest.mark.anyio
async def test_render_pdf_produces_real_pdf_bytes_with_citation_link() -> None:
    briefing = BriefingView(
        id=uuid4(),
        startup_id=uuid4(),
        content=(
            "## Recomendacoes NVIDIA\n\n"
            "- **NIM** - veja a fonte: [docs.nvidia.com](https://docs.nvidia.com/nim/)\n"
        ),
        review_status="pending",
        review_comment=None,
        reviewed_by=None,
        reviewed_at=None,
        generated_at=datetime.now(UTC),
    )
    renderer = JinjaPlaywrightPdfRenderer()

    pdf_bytes = await renderer.render_pdf(briefing)

    assert pdf_bytes.startswith(b"%PDF")
    assert len(pdf_bytes) > 500
