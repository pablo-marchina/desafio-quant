"""Evidence Validator Agent — sexta estação do grafo, e o PRIMEIRO ciclo.

O Classifier diz "esta startup é AI-native" e com que confiança *na evidência
textual*. O Evidence Validator olha por outro eixo: a QUALIDADE e a
CONSISTÊNCIA da evidência por trás do rótulo, e emite uma `validation_confidence`
própria. Quando a coleta foi fraca demais, ele pode mandar o grafo RECOLETAR.

Por que baseado em REGRAS (sem LLM):
  - Princípio do projeto: "estruture como regras explícitas antes de usar LLM". Validar
    consistência é justamente o tipo de coisa que regras fazem bem: transparente,
    determinístico, barato e testável offline sem nenhum LLM falso.
  - Deixa a mecânica da ARESTA CONDICIONAL cristalina, sem ruído de LLM.
  Um refinamento via LLM (ex.: detectar contradições sutis) fica como futuro.

⭐ A aresta condicional (conceito novo de LangGraph): depois deste nó, a função
`route_after_validation` decide o caminho — voltar pro `scraper` (recoletar) ou
seguir pro fim. Para NÃO criar loop infinito, há uma GUARDA DE TERMINAÇÃO:
`validation_attempts` é incrementado a cada passagem e o roteamento só recoleta
enquanto `attempts < MAX_ATTEMPTS`.

Nota honesta: voltar pro scraper com as MESMAS fontes recoleta o mesmo conteúdo
— justifica-se como *retry* de coleta instável (rede/enricher que falhou). Uma
versão mais esperta voltaria pro search_planner para AMPLIAR termos/fontes.
"""
from typing import Literal

from langgraph.graph import END

from agents.classifier import ClassifiedStartup
from agents.state import RadarState
from pydantic import BaseModel

# Guardas da aresta condicional.
MAX_ATTEMPTS = 2      # no máximo 1 re-coleta (1ª passagem + 1 retry)
LOW_RATIO_LIMIAR = 0.5  # recoleta só se >= metade das startups ficou em "low"

Confidence = Literal["high", "medium", "low"]
# Rótulos que EXIGEM sinais de IA para serem consistentes.
_LABELS_DE_IA = {"AI-native", "AI-enabled"}


class ValidatedStartup(BaseModel):
    """Startup com a confiança validada. Aninha o ClassifiedStartup que entrou,
    para que recommendation/briefing tenham toda a cadeia num objeto só."""

    classified: ClassifiedStartup
    validation_confidence: Confidence
    issues: list[str]


def _validar(classified: ClassifiedStartup) -> ValidatedStartup:
    """Aplica as regras de validação a UMA startup classificada.

    Ordem das regras importa: as ressalvas que forçam "low" têm prioridade
    sobre a herança da confiança do classifier.
    """
    startup = classified.startup
    issues: list[str] = []
    confidence: Confidence = classified.confidence  # ponto de partida: herda

    # Regra 1: sem conteúdo coletado, não há evidência real para sustentar nada.
    if startup.extraction_basis == "metadata":
        issues.append("sem conteúdo coletado")
        confidence = "low"

    # Regra 2: rótulo de IA sem nenhum sinal textual é uma inconsistência —
    # o classifier afirmou IA, mas o extractor não achou evidência que sustente.
    if classified.label in _LABELS_DE_IA and not startup.ai_signals:
        issues.append("rótulo de IA sem sinais textuais")
        confidence = "low"

    return ValidatedStartup(
        classified=classified, validation_confidence=confidence, issues=issues
    )


def evidence_validator_node(state: RadarState) -> dict:
    """Nó 6 do grafo: valida a confiança de cada classificação (por regras)."""
    classificadas = state.get("classified_startups", [])
    # Incrementa a guarda de terminação a cada passagem (overwrite no estado).
    tentativa = state.get("validation_attempts", 0) + 1

    validadas: list[ValidatedStartup] = []
    contagem: dict[str, int] = {"high": 0, "medium": 0, "low": 0}
    for item in classificadas:
        resultado = _validar(ClassifiedStartup(**item))
        validadas.append(resultado)
        contagem[resultado.validation_confidence] += 1

    return {
        "validated_startups": [v.model_dump() for v in validadas],
        "validation_attempts": tentativa,
        "messages": [
            (
                "ai",
                f"[evidence_validator] tentativa {tentativa}: {len(validadas)} "
                f"validadas ({contagem['high']} high, {contagem['medium']} medium, "
                f"{contagem['low']} low)",
            )
        ],
    }


def route_after_validation(state: RadarState) -> str:
    """Função da ARESTA CONDICIONAL: decide o caminho após o validator.

    Volta pro `scraper` (recoletar) só se DUAS condições valerem:
      - fração de startups em "low" >= LOW_RATIO_LIMIAR (coleta fraca demais), e
      - ainda há orçamento de tentativas (`attempts < MAX_ATTEMPTS`) — a guarda
        que garante terminação do loop.
    Caso contrário, segue para END.
    """
    validadas = state.get("validated_startups", [])
    tentativas = state.get("validation_attempts", 0)

    if not validadas:
        return END

    lows = sum(1 for v in validadas if v["validation_confidence"] == "low")
    fracao_low = lows / len(validadas)

    if fracao_low >= LOW_RATIO_LIMIAR and tentativas < MAX_ATTEMPTS:
        return "scraper"
    return END
