"""Estado compartilhado do grafo multi-agente (RadarState).

No LangGraph o `State` é o objeto que TRAFEGA entre os nós. Cada nó recebe
o estado atual e devolve um dicionário com as chaves que quer atualizar —
o LangGraph faz o merge. Usar `TypedDict` mantém isso explícito e tipado.

Para a Semana 1 o estado é mínimo. Ele cresce a cada entregável:
  - Semana 2: + startups extraídas, classificação, confiança
  - Semana 3: + chunks RAG, recomendações, briefing
"""
from typing import Annotated, TypedDict

from langgraph.graph.message import add_messages


class RadarState(TypedDict, total=False):
    """Estado que percorre o grafo de agentes.

    `total=False` => todas as chaves são opcionais; cada nó preenche só o
    que lhe cabe, como num pipeline.
    """

    # Consulta original do gestor (entrada do Search Planner)
    query: str

    # Saída do Search Planner: termos de busca + fontes priorizadas
    search_terms: list[str]
    sources: list[str]

    # Saída do Scraper: startups cruas descobertas nas fontes (cada item é um
    # RawStartup serializado com .model_dump()). Ainda NÃO estruturadas — o
    # Extractor Agent enriquece depois (setor, funding, stack, sinais de IA).
    raw_startups: list[dict]

    # Saída do Extractor: startups já ESTRUTURADAS (cada item é um
    # StructuredStartup serializado com .model_dump()) — produto, setor,
    # estágio, funding, stack e os sinais de IA que o Classifier vai usar.
    extracted_startups: list[dict]

    # Saída do Classifier: startups ROTULADAS como AI-native / AI-enabled /
    # Non-AI (cada item é um ClassifiedStartup serializado, que aninha o
    # StructuredStartup + label, justificativa e confiança da evidência).
    classified_startups: list[dict]

    # Saída do Evidence Validator: startups com a confiança VALIDADA por regras
    # (cada item é um ValidatedStartup serializado, que aninha o
    # ClassifiedStartup + validation_confidence + issues encontradas).
    validated_startups: list[dict]

    # Contador de passagens pelo Evidence Validator. É a GUARDA DE TERMINAÇÃO da
    # aresta condicional: o roteamento só volta pro scraper enquanto este número
    # for menor que MAX_ATTEMPTS, evitando loop infinito no grafo.
    validation_attempts: int

    # Saída do NVIDIA RAG Agent: para CADA startup, os trechos da base de
    # conhecimento NVIDIA mais relevantes ao perfil dela — já recuperados por
    # vetor e reranqueados pelo Cohere, com proveniência (tech + url) para
    # citação. Cada item: {name, query, chunks:[RerankedChunk serializado]}.
    # É o insumo do Recommendation Agent (próxima estação).
    rag_contexts: list[dict]

    # Saída do Recommendation Agent: para CADA startup, as tecnologias NVIDIA
    # recomendadas (derivadas do contexto RAG por REGRAS explícitas), cada uma
    # com relevância, nível de confiança e citação. Cada item é um
    # StartupRecommendation serializado — insumo do Briefing Agent.
    recommendations: list[dict]

    # Saída do Briefing Agent: o relatório executivo final por startup, em
    # markdown, juntando identidade + classificação + validação + stack NVIDIA
    # recomendada (com citações) + fit score + sinal de confiança. Cada item é
    # um Briefing serializado {name, label, markdown} — entregue à interface.
    briefings: list[dict]

    # `add_messages` é um reducer do LangGraph: em vez de sobrescrever,
    # ACUMULA mensagens. Útil para depurar o raciocínio dos agentes.
    messages: Annotated[list, add_messages]
