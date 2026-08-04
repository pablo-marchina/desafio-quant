"""Extractor — transforma o conteúdo bruto em dados estruturados.

Transforma o conteúdo bruto coletado em dados estruturados (structured output via
LLM Groq, schema DadosEmpresa). NÃO grava no banco: a persistência acontece uma vez
no fim do pipeline (db.salvar_resultado, chamada pelo runner). A extração é função
separada do nó, para ser testável sem LLM.
"""

from app.llm import chat_structured
from app.state import DadosEmpresa, RadarState

# teto de contexto enviado ao LLM (evita estourar tokens com páginas longas)
MAX_CONTEXTO = 12000

_INSTRUCAO = (
    "Você extrai dados públicos de uma startup a partir de trechos de páginas web. "
    "Preencha apenas com o que estiver no texto; não invente. Deixe campos vazios "
    "quando não houver informação. Responda no schema pedido."
)


def extract_dados(textos: list[str], nome: str, fontes: list[str]) -> DadosEmpresa:
    """Chama o LLM com structured output e devolve um DadosEmpresa."""
    contexto = "\n\n---\n\n".join(textos)[:MAX_CONTEXTO]
    structured = chat_structured(DadosEmpresa)
    prompt = f"{_INSTRUCAO}\n\nEmpresa-alvo: {nome}\n\nTrechos:\n{contexto}"
    dados: DadosEmpresa = structured.invoke(prompt)

    # garante rastreabilidade e identidade mínimas
    if not dados.nome:
        dados.nome = nome
    if not dados.fontes:
        dados.fontes = fontes
    return dados


def extractor(state: RadarState) -> dict:
    nome = state.alvos[0] if state.alvos else state.consulta
    textos = [t["texto"] for t in state.conteudo_bruto]
    fontes = [t["fonte"] for t in state.conteudo_bruto]

    if textos:
        dados = extract_dados(textos, nome=nome, fontes=fontes)
    else:
        dados = DadosEmpresa(nome=nome, fontes=fontes)

    return {"dados_estruturados": dados}
