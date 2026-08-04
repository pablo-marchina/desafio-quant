"""Relevance Filter Agent — entre o Scraper e o Enricher.

O Scraper descobre TODAS as startups listadas nos diretórios (centenas de
nomes), sem relação com a consulta. Sem este filtro, o pipeline enriqueceria e
qualificaria as primeiras N de cada diretório às cegas — e o resultado de
"startups de finanças" vinha cheio de lavanderia, energia e saúde (o problema
que o gestor notou). Este nó usa a CONSULTA + os `search_terms` (que até então
eram gerados e ignorados) para selecionar só as startups plausivelmente
relevantes, ANTES do enriquecimento caro (busca web + LLM + RAG).

Decisões de design:
  - Filtra na DESCOBERTA (barato: só nomes + setor quando a fonte dá), não
    depois — economiza a parte cara, que só roda nas selecionadas.
  - LLM com saída estruturada: o modelo usa o nome/setor + conhecimento próprio
    para julgar relevância (ex.: sabe que "AbacatePay" é pagamentos). É o melhor
    sinal disponível antes de visitar o site da startup.
  - Teto `max_startups`: limita quantas seguem para o enriquecimento.
  - RESILIENTE: se o LLM falhar, cai no comportamento antigo (primeiras N) em vez
    de derrubar o pipeline (tratamento de erro explícito).
  - Sem startups ou sem query => passa direto (nada a filtrar).
"""
from langchain_core.messages import HumanMessage, SystemMessage
from loguru import logger
from pydantic import BaseModel

from agents.state import RadarState
from core.config import settings
from core.llm import get_llm

SYSTEM_PROMPT = """Você é o filtro de relevância do NVISION. Recebe a CONSULTA \
do gestor (e termos de busca relacionados) e uma lista de startups descobertas \
em diretórios (nome e, quando houver, setor).

Sua tarefa: selecionar APENAS as startups plausivelmente relevantes à consulta \
— mesmo tema/setor/problema. Use o nome, o setor e seu conhecimento sobre o que \
cada empresa faz. Se o nome/setor não indicar relação com a consulta, EXCLUA \
(é melhor uma lista curta e on-topic do que uma longa e genérica).

Devolva `selected_names` com os nomes EXATOS (como vieram na lista) das \
selecionadas, e uma frase de `reasoning`."""


class _Selection(BaseModel):
    """Saída estruturada do LLM: os nomes selecionados + a justificativa."""

    selected_names: list[str]
    reasoning: str


def _listagem(raw_startups: list[dict]) -> str:
    """Formata a lista compacta (nome + setor) para o prompt."""
    linhas = []
    for r in raw_startups:
        setor = r.get("sector")
        linhas.append(f"- {r['name']}" + (f" (setor: {setor})" if setor else ""))
    return "\n".join(linhas)


def relevance_node(state: RadarState) -> dict:
    """Nó de filtro: seleciona as startups relevantes à consulta."""
    raw_startups = state.get("raw_startups", [])
    query = state.get("query", "")
    search_terms = state.get("search_terms", [])

    # Nada a filtrar — passa direto (sem custo de LLM).
    if not raw_startups or not query:
        return {
            "raw_startups": raw_startups[: settings.max_startups],
            "messages": [("ai", f"[relevance] sem filtro (entrada vazia): "
                                 f"{len(raw_startups)} startups")],
        }

    try:
        llm = get_llm().with_structured_output(_Selection)
        humano = (
            f"Consulta: {query}\n"
            f"Termos de busca: {', '.join(search_terms)}\n\n"
            f"Startups descobertas:\n{_listagem(raw_startups)}"
        )
        sel: _Selection = llm.invoke(
            [SystemMessage(content=SYSTEM_PROMPT), HumanMessage(content=humano)]
        )
        escolhidos = {n.strip().lower() for n in sel.selected_names}
        filtradas = [r for r in raw_startups if r["name"].strip().lower() in escolhidos]
        erro = False
    except Exception:  # LLM fora do ar/parse — só aqui há degradação
        logger.exception("relevance: filtro falhou")
        filtradas = []
        erro = True

    if erro:
        # RESILIÊNCIA: o LLM caiu — não dá pra julgar relevância, então mantém as
        # primeiras N (melhor algum resultado do que zero por uma falha técnica).
        filtradas = raw_startups[: settings.max_startups]
        nota = "fallback (LLM falhou)"
    else:
        # Só as RELEVANTES, até o teto. Sem completar a lista com startups
        # off-topic: se o filtro aprovou poucas (ou nenhuma), é mais honesto
        # devolver poucas (ou nenhuma) do que reencher com ruído — era esse o
        # propósito do filtro. Lista vazia aqui = nada on-topic foi descoberto.
        filtradas = filtradas[: settings.max_startups]
        nota = "filtradas por relevância"

    return {
        "raw_startups": filtradas,
        "messages": [
            ("ai", f"[relevance] {len(filtradas)}/{len(raw_startups)} {nota} "
                   f"(query: {query!r})"),
        ],
    }
