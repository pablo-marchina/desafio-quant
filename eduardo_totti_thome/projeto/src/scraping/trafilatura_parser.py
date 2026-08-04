"""Extrai o texto principal de um HTML usando o trafilatura.

O trafilatura remove automaticamente menu, rodapé, anúncios e outros ruídos,
devolvendo apenas o conteúdo relevante da página.
"""

from __future__ import annotations

import trafilatura


def extract_main_text(html: str, url: str | None = None) -> str | None:
    """Devolve o texto principal limpo da página.

    Retorna None quando o trafilatura não identifica conteúdo aproveitável
    (acontece em páginas muito "leves", como home pages só com imagens).
    O parâmetro `url` é opcional e só ajuda o trafilatura em alguns casos.
    """
    return trafilatura.extract(html, url=url, favor_recall=True)
