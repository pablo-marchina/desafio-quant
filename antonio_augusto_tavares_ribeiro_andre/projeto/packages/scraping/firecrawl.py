"""Extração limpa de páginas via Firecrawl (F1.2).

Segundo estágio do pipeline de scraping (F1): dada uma URL candidata (vinda da
busca F1.1 ou das seeds §9), devolve o **conteúdo principal já limpo** em markdown
— sem boilerplate de nav/rodapé — pronto para chunking/RAG (F3) e para virar
evidência rastreável (F1.9). É o adapter para páginas "bem-comportadas"; sites que
dependem de JS pesado vão para o Playwright (F1.3) e o roteador (F1.7) decide qual
usar.

Usa o Firecrawl (`FIRECRAWL_API_KEY`, F0.3). A guarda de quota de free tier (F1.8)
e o respeito a robots.txt/rate limit entram no roteador/compliance; aqui é só o
adapter de extração puro. O client é importado de forma preguiçosa para que o
parsing (`_parse`) seja testável sem `firecrawl-py` instalado nem rede — espelha o
adapter de busca (F1.1).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from functools import lru_cache
from typing import Any

from packages.config import get_settings


@dataclass(frozen=True)
class ExtractedPage:
    """Conteúdo limpo de uma página, pronto para chunking/RAG (F3) e evidência (F1.9).

    `markdown` é o conteúdo principal extraído (sem nav/rodapé). `metadata` carrega
    o restante devolvido pela fonte (`og:*`, `language`, etc.) sem perda, para o
    enriquecimento de perfil (F2) decidir o que aproveitar. A proveniência completa
    (hash + `fetched_at` na tabela `evidence`) é montada em F1.9 a partir daqui.
    """

    url: str
    markdown: str
    title: str = ""
    description: str = ""
    status_code: int | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def is_empty(self) -> bool:
        """True se a extração não rendeu texto útil (página vazia/bloqueada)."""
        return not self.markdown.strip()


@lru_cache
def _client() -> Any:
    """`Firecrawl` (SDK v2) cacheado (import preguiçoso). Requer `FIRECRAWL_API_KEY`."""
    key = get_settings().firecrawl_api_key
    if not key:
        raise RuntimeError("FIRECRAWL_API_KEY ausente — configure o .env para a extração (F1.2).")
    from firecrawl import Firecrawl

    return Firecrawl(api_key=key)


def _as_dict(response: Any) -> dict[str, Any]:
    """Normaliza a resposta do Firecrawl para dict (SDK pode devolver objeto/pydantic)."""
    if isinstance(response, dict):
        return response
    if hasattr(response, "model_dump"):  # pydantic (Document, SDK v2)
        return response.model_dump()
    if hasattr(response, "__dict__"):
        return vars(response)
    return {}


def _parse(url: str, payload: dict[str, Any]) -> ExtractedPage:
    """Converte a resposta do Firecrawl em `ExtractedPage` (puro, testável offline).

    O `Document` do SDK v2 expõe `markdown` + `metadata` (snake_case: `source_url`,
    `status_code`); alguns retornos REST crus embrulham em `data` e usam camelCase
    (`sourceURL`, `statusCode`) — aceitamos ambos. A URL final da fonte (segue
    redirecionamentos) tem prioridade sobre a URL pedida.
    """
    data = payload.get("data", payload)
    metadata = data.get("metadata") or {}
    return ExtractedPage(
        url=metadata.get("source_url") or metadata.get("sourceURL") or url,
        markdown=data.get("markdown") or "",
        title=metadata.get("title") or "",
        description=metadata.get("description") or "",
        status_code=metadata.get("status_code") or metadata.get("statusCode"),
        metadata=metadata,
    )


def scrape(
    url: str,
    *,
    only_main_content: bool = True,
    timeout_ms: int = 30_000,
) -> ExtractedPage:
    """Extrai o conteúdo principal de `url` em markdown limpo, pronto para RAG.

    `only_main_content=True` descarta nav/rodapé/anúncios (default p/ qualidade de
    RAG). `timeout_ms` limita a espera por página lenta. O resultado pode vir vazio
    (`ExtractedPage.is_empty`) quando a fonte bloqueia ou exige JS — nesse caso o
    roteador (F1.7) cai para o Playwright (F1.3).
    """
    if not url.strip():
        raise ValueError("url vazia")
    document = _client().scrape(
        url,
        formats=["markdown"],
        only_main_content=only_main_content,
        timeout=timeout_ms,
    )
    return _parse(url, _as_dict(document))
