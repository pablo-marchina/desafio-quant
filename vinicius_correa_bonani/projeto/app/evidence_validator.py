"""Evidence Validator — grounding (faithfulness check) dos fatos da empresa.

Antes de seguir para o RAG, checa se as afirmações que o Extractor produziu
(`dados_estruturados`) estão de fato sustentadas pelos trechos coletados
(`conteudo_bruto`) — não apenas se há fontes suficientes. Conceito:
Chain-of-Verification / grounding.

Duas camadas:
  1. `estrutura_suficiente` — pré-gate barato, sem LLM (≥ 3 domínios de fonte
     distintos E `setor`/`descricao` preenchidos). Rodadas magras nem chamam o LLM.
  2. `verificar_afirmacoes` — o faithfulness check por LLM: para cada CAMPO preenchido,
     diz se os trechos o sustentam. Campos de ALTO RISCO sem lastro (funding/founders/
     clientes) são removidos de `dados_estruturados`; o veredito de cada campo é
     registrado em `afirmacoes_verificadas` (rastreabilidade).

Schema de saída é PLANO (booleanos fixos por campo) — o json_schema da Groq é frágil
com estruturas aninhadas (ver CLAUDE.md). Se a chamada falhar mesmo assim, o nó degrada
para a regra mecânica em vez de derrubar o pipeline.

É o ponto do loop: se a evidência for insuficiente e ainda houver tentativas, o grafo
volta ao Search Planner (teto em `tentativas`). Incrementa `tentativas` a cada checagem.
"""

from urllib.parse import urlparse

from pydantic import BaseModel

from app.config import settings
from app.llm import chat_structured
from app.state import DadosEmpresa, RadarState, VerificacaoAfirmacao

MIN_DOMINIOS = 3   # piso de fontes distintas; rodadas magras voltam ao Scraper (loop)

# Campos factuais que mais machucam se alucinados: removidos quando sem lastro.
CAMPOS_ALTO_RISCO = ("funding", "founders", "clientes")

# teto de contexto enviado ao LLM (evita estourar tokens com páginas longas)
MAX_CONTEXTO = 12000


def _dominio(url: str) -> str:
    host = urlparse(url).netloc.lower()
    return host[4:] if host.startswith("www.") else host


def estrutura_suficiente(state: RadarState) -> bool:
    """Pré-gate mecânico (sem LLM): ≥ MIN_DOMINIOS fontes distintas E campos-chave."""
    dominios = {_dominio(t.get("fonte", "")) for t in state.conteudo_bruto}
    dominios.discard("")
    dados = state.dados_estruturados
    campos_ok = bool(dados and dados.setor and dados.descricao)
    return len(dominios) >= MIN_DOMINIOS and campos_ok


class _SaidaGrounding(BaseModel):
    """Saída PLANA (json_schema da Groq é frágil com aninhamento): um booleano por campo.
    True = os trechos sustentam a afirmação daquele campo."""

    setor_ok: bool = False
    descricao_ok: bool = False
    funding_ok: bool = False
    founders_ok: bool = False
    clientes_ok: bool = False
    tecnologias_ok: bool = False


_INSTRUCAO = (
    "Você audita afirmações sobre uma startup contra os TRECHOS coletados de páginas web. "
    "Para CADA campo listado, decida se algum trecho o sustenta explicitamente e marque o "
    "booleano correspondente (ex.: setor_ok). Marque true só se houver lastro nos trechos; "
    "senão false. Não use conhecimento externo nem infira; julgue SÓ pelos trechos. "
    "Responda no schema pedido."
)


def _afirmacoes(dados: DadosEmpresa) -> list[tuple[str, str]]:
    """Pares (campo, valor) dos campos não-vazios a verificar — um por campo.
    Campos de lista (founders/clientes/tecnologias) viram um único item juntado."""
    pares: list[tuple[str, str]] = []
    if dados.setor:
        pares.append(("setor", dados.setor))
    if dados.descricao:
        pares.append(("descricao", dados.descricao))
    if dados.funding:
        pares.append(("funding", dados.funding))
    if dados.founders:
        pares.append(("founders", ", ".join(dados.founders)))
    if dados.clientes:
        pares.append(("clientes", ", ".join(dados.clientes)))
    if dados.tecnologias:
        pares.append(("tecnologias", ", ".join(dados.tecnologias)))
    return pares


def verificar_afirmacoes(
    dados: DadosEmpresa, conteudo_bruto: list[dict]
) -> list[VerificacaoAfirmacao]:
    """Faithfulness check por LLM: cada campo preenchido × trechos → veredito."""
    pares = _afirmacoes(dados)
    if not pares:
        return []

    trechos = "\n\n---\n\n".join(
        f"[fonte: {t.get('fonte', '')}]\n{t.get('texto', '')}" for t in conteudo_bruto
    )[:MAX_CONTEXTO]
    lista = "\n".join(f"- {campo}: {valor}" for campo, valor in pares)
    prompt = (
        f"{_INSTRUCAO}\n\n"
        f"EMPRESA-ALVO: {dados.nome}\n\n"
        f"AFIRMAÇÕES A VERIFICAR (por campo):\n{lista}\n\n"
        f"TRECHOS COLETADOS:\n{trechos}"
    )
    structured = chat_structured(_SaidaGrounding)
    saida: _SaidaGrounding = structured.invoke(prompt)

    return [
        VerificacaoAfirmacao(
            campo=campo, valor=valor, sustentada=getattr(saida, f"{campo}_ok", False)
        )
        for campo, valor in pares
    ]


def _campo_sustentado(vereditos: list[VerificacaoAfirmacao], campo: str) -> bool:
    """True se o campo aparece e todas as suas afirmações estão sustentadas."""
    do_campo = [v for v in vereditos if v.campo == campo]
    return bool(do_campo) and all(v.sustentada for v in do_campo)


def _limpar_alto_risco(
    dados: DadosEmpresa, vereditos: list[VerificacaoAfirmacao]
) -> DadosEmpresa:
    """Remove de uma cópia dos dados os campos de alto risco sem lastro (por campo)."""
    limpo = dados.model_copy(deep=True)
    nao_sustentados = {v.campo for v in vereditos if not v.sustentada}
    if "funding" in nao_sustentados:
        limpo.funding = None
    if "founders" in nao_sustentados:
        limpo.founders = []
    if "clientes" in nao_sustentados:
        limpo.clientes = []
    return limpo


def evidence_validator(state: RadarState) -> dict:
    tentativas = state.tentativas + 1
    dados = state.dados_estruturados

    # Fallback mecânico: sem grounding, sem chave LLM, ou nada para verificar.
    if (
        not settings.grounding_habilitado
        or not settings.llm_api_key
        or not dados
        or not state.conteudo_bruto
    ):
        return {"evidencias_ok": estrutura_suficiente(state), "tentativas": tentativas}

    # o grounding é um reforço: se a chamada falhar (ex.: Groq recusa o JSON), degrada
    # para a regra mecânica em vez de derrubar o pipeline inteiro.
    try:
        vereditos = verificar_afirmacoes(dados, state.conteudo_bruto)
    except Exception as e:  # noqa: BLE001 — degradar é intencional
        print(f"[evidence_validator] grounding falhou ({e}); usando regra mecânica.")
        return {"evidencias_ok": estrutura_suficiente(state), "tentativas": tentativas}

    dados_limpo = _limpar_alto_risco(dados, vereditos)

    # gate estrito: estrutura OK E os campos-chave de fato ancorados nas fontes
    evidencias_ok = (
        estrutura_suficiente(state)
        and _campo_sustentado(vereditos, "setor")
        and _campo_sustentado(vereditos, "descricao")
    )
    return {
        "evidencias_ok": evidencias_ok,
        "afirmacoes_verificadas": vereditos,
        "dados_estruturados": dados_limpo,
        "tentativas": tentativas,
    }
