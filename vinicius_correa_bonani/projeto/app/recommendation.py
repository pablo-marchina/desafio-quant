"""Recommendation — cruza gaps da empresa × portfólio NVIDIA (recomendar) e pontua
a startup (pontuar), como DUAS tarefas separadas.

Antes era uma chamada só (recomendar + notas juntas), o que diluía as duas. Agora:
- `recomendar` produz só a `Recomendacao` (7 campos), raciocinando sobre o gap.
- `pontuar` produz só as 4 notas (`Score`), com rubrica ancorada por eixo.
- `pontuar_em_painel` roda `pontuar` com N juízes e faz a MÉDIA das notas (reduz o
  ruído do julgamento subjetivo — é o análogo numérico da self-consistency do Classifier).

O código calcula o `composto` (pesos configuráveis, via `score.compor`). LLM = Groq
(via app.llm). Structured output plano (mais robusto no json_schema da Groq).
"""

from typing import Optional

from pydantic import BaseModel, Field

from app.config import settings
from app.llm import chat_structured
from app.score import EIXOS, compor
from app.state import Classificacao, DadosEmpresa, RadarState, Recomendacao, Score


def _contexto(dados: DadosEmpresa, classificacao: Optional[Classificacao], contexto_rag: list[str]) -> str:
    contexto = "\n".join(contexto_rag) or "(sem contexto recuperado)"
    classif = classificacao.model_dump_json() if classificacao else "{}"
    return (
        f"PERFIL DA EMPRESA:\n{dados.model_dump_json(indent=2)}\n\n"
        f"CLASSIFICAÇÃO AI-NATIVE:\n{classif}\n\n"
        f"CONTEXTO NVIDIA (trechos com fonte):\n{contexto}"
    )


# ---------------------------------------------------------------- recomendar

_INSTRUCAO_REC = (
    "Você recomenda tecnologias NVIDIA para uma startup, para o gerente de Startups & VCs.\n"
    "O campo `tecnologias` deve conter SÓ produtos NVIDIA a ADOTAR (ex.: Triton, TensorRT-LLM, "
    "NIM, NeMo, RAPIDS) — NÃO liste o stack atual da empresa nem ferramentas de terceiros "
    "(PyTorch, ONNX, AWS, etc.).\n"
    "Use APENAS produtos que aparecem no CONTEXTO NVIDIA fornecido — não invente specs nem nomes "
    "de produto. Para cada afirmação técnica, cite a fonte (URL) no campo evidencias.\n"
    "Raciocine sobre o gap: em qual camada a startup trava e qual tecnologia NVIDIA destrava.\n"
    "justificativa_negocio em linguagem de negócio (custo por token, latência, defensibilidade)."
)


def recomendar(
    dados: DadosEmpresa, classificacao: Optional[Classificacao], contexto_rag: list[str]
) -> Recomendacao:
    """Só a recomendação (7 campos). Sem notas — pontuação é tarefa à parte."""
    prompt = f"{_INSTRUCAO_REC}\n\n{_contexto(dados, classificacao, contexto_rag)}"
    structured = chat_structured(Recomendacao)
    return structured.invoke(prompt)


# ------------------------------------------------------------------ pontuar

class _SaidaNotas(BaseModel):
    """As 4 notas (0–10). Sem `composto` — esse é calculado pelo código (score.compor)."""

    ai_native: float = 0.0
    nvidia_fit: float = 0.0
    tracao: float = 0.0
    time_ia: float = 0.0


_INSTRUCAO_NOTAS = (
    "Você é um analista de VC pontuando uma startup em 4 eixos, de 0 a 10. Use a rubrica "
    "ancorada (seja rigoroso; a nota alimenta um ranking):\n"
    "- ai_native: 0-3 = só chama API de terceiro; 4-6 = algum modelo/dado próprio; "
    "7-10 = modelo E dado proprietários e controla a própria inferência (Tractian = 10).\n"
    "- nvidia_fit: FORÇA da oportunidade de adoção NVIDIA (uplift), NÃO o quanto a empresa está "
    "atrasada. Empresa madura que já roda inferência/treino em escala é ALTO fit, não baixo. "
    "0-3 = sem caminho claro de adoção; 4-6 = adoção possível de valor moderado; 7-10 = caminho "
    "claro e de alto valor numa camada que uma tech NVIDIA do contexto serve (serving/inferência, "
    "dados em GPU, robótica). Tractian = alto.\n"
    "- tracao: 0-3 = pré-seed/sem tração; 4-6 = seed com clientes; 7-10 = Series B+ e receita relevante.\n"
    "- time_ia: 0-3 = sem sinal de time de IA; 4-6 = alguns engenheiros de ML; "
    "7-10 = founders/liderança técnica fortes em IA.\n"
    "Julgue SÓ pelo material fornecido; não invente. Onde faltar sinal FACTUAL (tração/time/dados), "
    "pontue baixo (não médio) — isso NÃO se aplica a nvidia_fit, que mede oportunidade, não deficiência."
)


def pontuar(
    dados: DadosEmpresa, classificacao: Optional[Classificacao], contexto_rag: list[str]
) -> Score:
    """Um juiz: as 4 notas com rubrica ancorada. Temperatura > 0 p/ o painel variar."""
    prompt = f"{_INSTRUCAO_NOTAS}\n\n{_contexto(dados, classificacao, contexto_rag)}"
    structured = chat_structured(_SaidaNotas, temperature=settings.score_temperatura)
    s: _SaidaNotas = structured.invoke(prompt)
    return Score(ai_native=s.ai_native, nvidia_fit=s.nvidia_fit, tracao=s.tracao, time_ia=s.time_ia)


def pontuar_em_painel(
    dados: DadosEmpresa,
    classificacao: Optional[Classificacao],
    contexto_rag: list[str],
    n: int | None = None,
) -> Score:
    """Painel de juízes: pontua `n` vezes e devolve a MÉDIA de cada eixo."""
    n = n or settings.score_n_juizes
    votos = [pontuar(dados, classificacao, contexto_rag) for _ in range(n)]
    media = {eixo: round(sum(getattr(v, eixo) for v in votos) / len(votos), 2) for eixo in EIXOS}
    return Score(**media)


# --------------------------------------------------------------------- nó

def recommendation(state: RadarState) -> dict:
    dados = state.dados_estruturados or DadosEmpresa(nome=state.consulta)
    rec = recomendar(dados, state.classificacao_detalhe, state.contexto_rag)
    notas = pontuar_em_painel(dados, state.classificacao_detalhe, state.contexto_rag)
    notas.composto = compor(notas)
    return {"recomendacao": rec, "score": notas}
