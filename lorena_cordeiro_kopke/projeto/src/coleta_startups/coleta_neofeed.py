from __future__ import annotations
import json
import os
import sys
from pathlib import Path
from playwright.sync_api import sync_playwright

URL_BASE = 'https://neofeed.com.br/startups/'

_RAIZ = Path(__file__).resolve().parent.parent.parent
_SAIDA_PADRAO = str(_RAIZ / 'data/jsons/artigos_nomes_empresas/artigos_brutos.json')


def _chromium_executable() -> str | None:
    """Retorna o executável Chromium disponível (headless shell ou full chrome como fallback)."""
    base = Path(os.environ.get("LOCALAPPDATA", "")) / "ms-playwright"
    headless = next(base.glob("chromium_headless_shell-*/chrome-headless-shell-win64/chrome-headless-shell.exe"), None)
    if headless and headless.exists():
        return str(headless)
    full = next(base.glob("chromium-*/chrome-win64/chrome.exe"), None)
    if full and full.exists():
        return str(full)
    return None


def contar_artigos(page) -> int:
    return page.locator('article').count()


def carregar_mais_artigos(page, cliques_max: int = 10) -> int:
    """Clica no botão 'Carregar mais' repetidamente para trazer artigos
    mais antigos, que por padrão não vêm na primeira renderização da
    página. Cada clique tende a carregar um novo lote de artigos via AJAX.

    cliques_max controla até quantos lotes extras você quer buscar —
    aumente esse número pra pegar um histórico maior (mais antigo)."""
    anterior = contar_artigos(page)
    for _ in range(cliques_max):
        botao = page.get_by_text('Carregar mais', exact=False)
        if botao.count() == 0:
            break  # não há mais o que carregar
        try:
            botao.first.click(timeout=5000)
            page.wait_for_function(
                f"document.querySelectorAll('article').length > {anterior}",
                timeout=8000,
            )
        except Exception:
            break  # botão não respondeu a tempo, ou esgotou os artigos
        anterior = contar_artigos(page)
    return anterior


def coletar(cliques_max: int = 3, caminho_saida: str = _SAIDA_PADRAO) -> list[dict]:
    """Só raspa e salva os dados brutos (título, url, tags) — não faz
    nenhuma extração de nome nem filtro de qualidade. Essa etapa é cara
    (abre navegador, depende do site no ar), por isso fica isolada: você
    só precisa rodar de novo quando quiser dados mais recentes, não a
    cada ajuste de filtro."""
    with sync_playwright() as p:
        browser = p.chromium.launch(executable_path=_chromium_executable())
        page = browser.new_page()
        page.goto(URL_BASE, wait_until='domcontentloaded', timeout=60000)
        page.wait_for_selector('article', timeout=30000)

        total = carregar_mais_artigos(page, cliques_max=cliques_max)
        print(f"[info] {total} artigos carregados após cliques em 'Carregar mais'")

        artigos = page.eval_on_selector_all(
            'article',
            """(arts) => arts.map((art) => {
                const h = art.querySelector('h2, h3');
                const titulo = h?.innerText?.trim() || '';
                const a = h ? (h.querySelector('a') || h.closest('a')) : null;
                const link = a?.href || '';
                const tags = [...art.querySelectorAll('a[rel="tag"], .tag-links a, .cat-links a')]
                    .map((a) => a.innerText.trim().toLowerCase());
                return { titulo, url: link, tags };
            })"""
        )

        browser.close()

    Path(caminho_saida).parent.mkdir(parents=True, exist_ok=True)
    with open(caminho_saida, 'w', encoding='utf-8') as f:
        json.dump(artigos, f, ensure_ascii=False, indent=2)
    print(f"[info] {len(artigos)} artigos brutos salvos em {caminho_saida}")

    return artigos


if __name__ == '__main__':
    # uso: python coleta_neofeed.py [numero_de_cliques_em_carregar_mais] [caminho_de_saida]
    cliques = int(sys.argv[1]) if len(sys.argv) > 1 else 10
    saida = sys.argv[2] if len(sys.argv) > 2 else _SAIDA_PADRAO
    coletar(cliques_max=cliques, caminho_saida=saida)