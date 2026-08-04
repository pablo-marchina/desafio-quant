from datetime import datetime, timezone
import re

import httpx
import trafilatura
from bs4 import BeautifulSoup
from fastapi import HTTPException

from app.schemas import CollectResponse, SourceMetadata

def get_page_title(html: str) -> str | None:
    soup = BeautifulSoup(html, "html.parser")

    if soup.title and soup.title.string:
        return soup.title.string.strip()

    return None


def extract_clean_text(html: str, url: str) -> tuple[str, str]:
    extracted_text = trafilatura.extract(
        html,
        url=url,
        include_links=False,
        include_tables=True,
        favor_precision=True
    )

    if extracted_text:
        clean_text = extracted_text
        extraction_method = "trafilatura"
    else:
        soup = BeautifulSoup(html, "html.parser")

        for tag in soup(["script", "style", "nav", "footer", "header", "noscript"]):
            tag.decompose()

        clean_text = soup.get_text(" ", strip=True)
        extraction_method = "beautifulsoup_fallback"

    clean_text = re.sub(r"\s+", " ", clean_text).strip()

    if not clean_text:
        raise ValueError("Não foi possível extrair texto útil desta página.")

    return clean_text[:15000], extraction_method


async def collect_source(startup_name: str, url: str) -> CollectResponse:
    try:
        async with httpx.AsyncClient(
            timeout=20,
            follow_redirects=True,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 Chrome/122 Safari/537.36"
                )
            }
        ) as client:
            response = await client.get(url)
            response.raise_for_status()

    except httpx.HTTPStatusError as error:
        raise HTTPException(
            status_code=502,
            detail=f"A fonte respondeu com erro HTTP {error.response.status_code}."
        ) from error

    except httpx.RequestError as error:
        raise HTTPException(
            status_code=502,
            detail=(
                "Não foi possível acessar esta fonte pública. "
                f"Motivo: {type(error).__name__} - {str(error)}"
            )
        ) from error

    try:
        clean_text, extraction_method = extract_clean_text(
            html=response.text,
            url=url
        )
    except ValueError as error:
        raise HTTPException(
            status_code=422,
            detail=str(error)
        ) from error

    return CollectResponse(
        startup_name=startup_name,
        source=SourceMetadata(
            url=url,
            title=get_page_title(response.text),
            extraction_method=extraction_method
        ),
        collected_at=datetime.now(timezone.utc),
        text_characters=len(clean_text),
        word_count=len(clean_text.split()),
        clean_text=clean_text
    )