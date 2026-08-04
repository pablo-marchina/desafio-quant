"""Startup Classifier Agent — quinta estação do grafo.

O Extractor entrega StructuredStartup (com `ai_signals` — as evidências
textuais de IA). O Classifier lê esse retrato e rotula cada startup em três
categorias, que orientam toda a abordagem comercial do Inception:

  - AI-native : IA é o NÚCLEO do produto — sem IA, ele não existe (modelos
                próprios, IA como diferencial central).
  - AI-enabled: usa IA como FEATURE de apoio, mas o core do negócio é outro.
  - Non-AI    : sem evidência de uso de IA.

Decisões de design (espelham o Extractor, já aprovado):
  - Uma chamada de LLM POR STARTUP: erro isolado por item, contexto focado.
    Batching fica como otimização futura.
  - `extraction_basis == "metadata"` => SEM LLM: startup sem conteúdo coletado
    não tem texto a julgar. Rotula provisoriamente como Non-AI/low — conservador
    (não afirma IA sem evidência) e sinaliza ao evidence_validator/loop de
    re-scrape que deve revisitar.
  - Erro POR STARTUP: uma classificação que falha vira fallback Non-AI/low +
    log, não derruba as demais.

`confidence` aqui mede a FORÇA DA EVIDÊNCIA TEXTUAL para o rótulo. O Evidence
Validator (à frente) é outro eixo: corrobora a confiabilidade das FONTES.
"""
from typing import Literal

from langchain_core.messages import HumanMessage, SystemMessage
from loguru import logger
from pydantic import BaseModel

from agents.extractor import StructuredStartup
from agents.state import RadarState
from core.llm import get_llm

# Rótulos que o LLM atribui quando HÁ conteúdo para julgar.
LabelLLM = Literal["AI-native", "AI-enabled", "Non-AI"]
# Rótulos possíveis na SAÍDA do nó: + "Indeterminado" para quando não houve
# conteúdo coletado (metadata) ou a classificação falhou. Honestidade > falso
# Non-AI: "não conseguimos ler o site" não é a mesma coisa que "não usa IA".
Label = Literal["AI-native", "AI-enabled", "Non-AI", "Indeterminado"]
Confidence = Literal["high", "medium", "low"]

SYSTEM_PROMPT = """Você é o Classifier do NVISION. A partir do retrato \
estruturado de uma startup brasileira, classifique a MATURIDADE DE IA em UMA \
categoria. Mire em PRECISÃO: nem inflar (rótulo de IA sem evidência), nem \
subestimar (ignorar IA real que está na descrição mesmo quando `ai_signals` \
vier vazio).

Categorias:
- "AI-native": IA é o NÚCLEO — sem IA o produto não existe. Inclui tanto quem \
TREINA modelos próprios quanto quem CONSTRÓI o produto inteiro sobre IA de \
TERCEIROS (ex.: "assistente jurídico com LLM", "busca semântica com \
embeddings"). Pergunta-chave: se tirar a IA, ainda sobra produto? Se NÃO, é \
AI-native — mesmo que o modelo seja de terceiros.
- "AI-enabled": o CORE do negócio é outro e a IA é uma FEATURE de apoio (ex.: um \
ERP que ganhou um assistente; um marketplace com recomendação). Tirar a IA \
degrada, mas o produto continua existindo.
- "Non-AI": sem evidência de uso ou desenvolvimento de IA.

Como decidir (evita os erros comuns):
- Baseie-se em `ai_signals`; MAS se vierem vazios e a description/tech_stack \
indicarem IA com clareza (ex.: "visão computacional", "modelos de ML", "LLM"), \
considere essa evidência também — não rotule Non-AI só porque a lista de sinais \
ficou curta.
- "IA"/"inteligência artificial" SÓ no marketing, sem evidência concreta de uso, \
NÃO é IA: classifique pela evidência real (provável Non-AI, ou confiança baixa).
- Processar muitos dados, usar GPU ou automatizar por regras NÃO é IA por si só \
(dados ≠ IA; automação ≠ IA).
- Usar IA de terceiros JÁ é usar IA: o que separa AI-native de AI-enabled é se a \
IA é o NÚCLEO ou apenas uma feature.

Exemplos:
1. "assistente jurídico que gera petições com LLM; RAG sobre jurisprudência" → \
AI-native (high): a IA é o produto.
2. "ERP financeiro para PMEs; adicionou um chatbot de suporte com IA" → \
AI-enabled (high): core é o ERP, IA é feature.
3. "marketplace de fretes que conecta transportadoras a embarcadores" (sem \
sinais de IA) → Non-AI (high).
4. "plataforma 'powered by AI' de gestão de RH", sem nenhum sinal concreto → \
Non-AI ou AI-enabled com confiança LOW: marketing não é evidência.

Devolva também:
- `rationale`: 1–2 frases citando os sinais/trechos que embasaram o rótulo.
- `confidence`: força da EVIDÊNCIA — "high" (sinais claros e diretos), "medium" \
(indiretos/parciais), "low" (fraca, ambígua ou só marketing).
"""


class _ClassificationResult(BaseModel):
    """O que o LLM decide. `name`/dados ficam fora: pertencem ao nó."""

    label: LabelLLM
    rationale: str
    confidence: Confidence


class ClassifiedStartup(BaseModel):
    """Startup rotulada — saída do Classifier. Aninha o StructuredStartup que
    entrou, para que recommendation/briefing tenham tudo num objeto só."""

    startup: StructuredStartup
    label: Label
    rationale: str
    confidence: Confidence


def _provisorio(startup: StructuredStartup, rationale: str) -> ClassifiedStartup:
    """Classificação SEM LLM quando não dá para julgar: "Indeterminado"/low.
    Usada quando não há conteúdo (metadata) ou a chamada falhou. Não afirma IA
    sem texto, mas TAMBÉM não afirma Non-AI: só não foi possível determinar."""
    return ClassifiedStartup(
        startup=startup, label="Indeterminado", rationale=rationale, confidence="low"
    )


def _classificar(structured_llm, startup: StructuredStartup) -> _ClassificationResult:
    """Uma chamada de LLM para uma startup. `structured_llm` já vem com
    `with_structured_output(_ClassificationResult)` aplicado."""
    retrato = startup.model_dump_json(indent=2)
    prompt = [
        SystemMessage(content=SYSTEM_PROMPT),
        HumanMessage(content=f"Retrato estruturado da startup:\n{retrato}"),
    ]
    return structured_llm.invoke(prompt)


def classifier_node(state: RadarState) -> dict:
    """Nó 5 do grafo: rotula cada startup estruturada em AI-native/enabled/Non-AI."""
    extracted = state.get("extracted_startups", [])

    classificadas: list[ClassifiedStartup] = []
    contagem: dict[str, int] = {
        "AI-native": 0, "AI-enabled": 0, "Non-AI": 0, "Indeterminado": 0,
    }
    # Instanciado preguiçosamente: startups só-metadata nem tocam o LLM.
    structured_llm = None

    for item in extracted:
        startup = StructuredStartup(**item)

        if startup.extraction_basis == "metadata":
            resultado = _provisorio(
                startup, "sem conteúdo coletado; classificação provisória"
            )
            classificadas.append(resultado)
            contagem[resultado.label] += 1
            continue

        try:
            if structured_llm is None:
                structured_llm = get_llm().with_structured_output(_ClassificationResult)
            r = _classificar(structured_llm, startup)
            resultado = ClassifiedStartup(
                startup=startup,
                label=r.label,
                rationale=r.rationale,
                confidence=r.confidence,
            )
        except Exception:  # uma startup não pode derrubar as outras
            logger.exception("classifier falhou em {}", startup.name)
            resultado = _provisorio(startup, "falha na classificação; rótulo provisório")

        classificadas.append(resultado)
        contagem[resultado.label] += 1

    return {
        "classified_startups": [c.model_dump() for c in classificadas],
        "messages": [
            (
                "ai",
                f"[classifier] {len(classificadas)} classificadas "
                f"({contagem['AI-native']} AI-native, "
                f"{contagem['AI-enabled']} AI-enabled, "
                f"{contagem['Non-AI']} Non-AI, "
                f"{contagem['Indeterminado']} indeterminado)",
            )
        ],
    }
