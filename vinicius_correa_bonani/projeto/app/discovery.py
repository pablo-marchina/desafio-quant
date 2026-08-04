"""Descoberta autônoma de startups — do tema à lista de nomes.

A partir de um TEMA, descobre uma LISTA de nomes de startups brasileiras de IA —
reusando a busca, o scraper e o LLM. NÃO faz a análise completa: produz a lista
para revisão humana, que então alimenta o `batch`.

    fluxo:  tema → busca → raspa listas/notícias → LLM extrai nomes → lista
    uso:    python -m app.discovery "startups brasileiras de IA em saúde"
            python -m app.discovery "fintechs de IA" --analisar   # encadeia o batch
"""

import re
import sys
import time

from app.llm import chat, chat_structured
from app.scraper import extract_text, fetch_url, permitido_por_robots
from app.search_planner import _buscar
from app.state import EmpresaDescoberta, ListaEmpresasDescritas

MAX_CONTEXTO = 14000

_INSTRUCAO = (
    "Extraia uma lista de STARTUPS BRASILEIRAS de IA mencionadas no texto.\n"
    "Para cada uma, devolva o nome próprio limpo e uma DESCRIÇÃO DE UMA FRASE "
    "(o que a empresa faz), baseada SOMENTE no texto; se o texto não disser o "
    "que ela faz, deixe a descrição vazia (não invente).\n"
    "Inclua apenas startups (empresas jovens) brasileiras cujo core envolve inteligência artificial.\n"
    "NÃO inclua: big techs (Google, Microsoft...), fundos/VCs, aceleradoras, universidades, "
    "veículos de notícia, nem empresas estrangeiras. Não duplique."
)


def _coletar_texto(tema: str, top_n: int = 5) -> str:
    """Busca listas/notícias sobre o tema e devolve o texto raspado concatenado."""
    queries = [
        f"melhores startups brasileiras de IA {tema}",
        f"startups de inteligência artificial {tema} Brasil",
        f"site:startups.com.br {tema}",
    ]
    vistos: set[str] = set()
    partes: list[str] = []
    for q in queries:
        for hit in _buscar(q, top_n):
            url = hit.get("href") or hit.get("url") or ""
            if not url or url in vistos:
                continue
            vistos.add(url)
            if not permitido_por_robots(url):
                continue
            html = fetch_url(url)
            if not html:
                continue
            texto = extract_text(html)
            if texto.strip():
                partes.append(texto)
    return "\n\n---\n\n".join(partes)[:MAX_CONTEXTO]


def extrair_empresas(texto: str) -> list[EmpresaDescoberta]:
    """LLM extrai startups (nome + descrição de 1 frase) do texto raspado.

    O modo JSON da Groq falha DETERMINISTICAMENTE com certos textos raspados
    ("json_validate_failed" com geração vazia), então repetir igual não basta.
    Degraus: 1) structured com o texto cheio; 2) structured com o texto pela
    metade (texto menor quebra menos); 3) texto puro, "Nome :: descrição" por
    linha, que não passa pelo validador de JSON.
    """
    if not texto.strip():
        return []
    structured = chat_structured(ListaEmpresasDescritas)
    for corte in (len(texto), MAX_CONTEXTO // 2):
        try:
            resultado: ListaEmpresasDescritas = structured.invoke(
                f"{_INSTRUCAO}\n\nTEXTO:\n{texto[:corte]}"
            )
            return resultado.empresas
        except Exception:
            time.sleep(1.0)

    # último recurso, sem structured output: parseia a resposta linha a linha
    resposta = chat().invoke(
        f"{_INSTRUCAO}\n"
        "Responda APENAS uma empresa por linha, no formato "
        "'Nome :: descrição em uma frase', sem numeração nem marcadores.\n\n"
        f"TEXTO:\n{texto[: MAX_CONTEXTO // 2]}"
    )
    empresas: list[EmpresaDescoberta] = []
    for linha in str(resposta.content).splitlines():
        limpo = re.sub(r"^[\s\-\*•\d\.\)]+", "", linha).strip()
        if not limpo:
            continue
        nome, _, descricao = limpo.partition("::")
        nome = nome.strip()
        if nome and len(nome) < 80:
            empresas.append(EmpresaDescoberta(nome=nome, descricao=descricao.strip()))
    return empresas


def extrair_nomes(texto: str) -> list[str]:
    """Só os nomes (compat: CLI e testes monkeypatcham esta função)."""
    return [e.nome for e in extrair_empresas(texto)]


def descobrir_detalhado(tema: str, n: int = 10) -> list[dict]:
    """Tema → até `n` startups como {nome, descricao}, deduplicadas por nome."""
    vistos: set[str] = set()
    limpas: list[dict] = []
    for e in extrair_empresas(_coletar_texto(tema)):
        chave = e.nome.strip().lower()
        if not chave or chave in vistos:
            continue
        vistos.add(chave)
        limpas.append({"nome": e.nome.strip(), "descricao": e.descricao.strip()})
    return limpas[:n]


def descobrir(tema: str, n: int = 10) -> list[str]:
    """Tema → lista de até `n` nomes de startups brasileiras de IA (deduplicada)."""
    nomes = extrair_nomes(_coletar_texto(tema))
    vistos: set[str] = set()
    limpos: list[str] = []
    for nome in nomes:
        chave = nome.strip().lower()
        if not chave or chave in vistos:
            continue
        vistos.add(chave)
        limpos.append(nome.strip())
    return limpos[:n]


def main() -> None:
    args = [a for a in sys.argv[1:] if a != "--analisar"]
    analisar = "--analisar" in sys.argv
    tema = " ".join(args) or "startups brasileiras de IA"

    print(f"Descobrindo startups para: '{tema}'…\n")
    nomes = descobrir(tema)
    if not nomes:
        print("Nenhuma startup encontrada (busca pode ter falhado ou tema muito restrito).")
        return
    for i, nome in enumerate(nomes, 1):
        print(f"  {i:>2}. {nome}")

    if analisar:
        from app import batch
        print(f"\nAnalisando as {len(nomes)} empresas…")
        batch.analisar_lote(nomes)


if __name__ == "__main__":
    main()
