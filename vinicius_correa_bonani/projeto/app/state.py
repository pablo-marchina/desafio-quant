"""RadarState — o contrato central que viaja por todo o grafo.

Cada nó lê os campos de que precisa e retorna apenas um dict parcial com o
que atualizou; o LangGraph mescla esse dict no State.
"""

from typing import Literal, Optional

from pydantic import BaseModel, Field


class ListaEmpresas(BaseModel):
    """Saída do passo de descoberta — nomes de startups extraídos de listas/notícias."""

    empresas: list[str] = Field(default_factory=list)


class EmpresaDescoberta(BaseModel):
    """Uma startup descoberta: nome + descrição curta tirada do próprio texto."""

    nome: str
    descricao: str = ""


class ListaEmpresasDescritas(BaseModel):
    """Saída da descoberta com descrições — ajuda o analista a priorizar."""

    empresas: list[EmpresaDescoberta] = Field(default_factory=list)


class DadosEmpresa(BaseModel):
    """Saída estruturada do Extractor (structured output via LLM).

    Dados públicos da empresa: produto, setor,
    clientes, funding, founders e tecnologias. `fontes` guarda as URLs usadas
    (rastreabilidade).
    """

    nome: str = ""
    setor: Optional[str] = None
    descricao: str = ""                                  # o que a empresa faz / produto
    founders: list[str] = Field(default_factory=list)
    funding: Optional[str] = None
    clientes: list[str] = Field(default_factory=list)
    tecnologias: list[str] = Field(default_factory=list)  # stack / sinais de IA
    fontes: list[str] = Field(default_factory=list)       # URLs usadas


class VerificacaoAfirmacao(BaseModel):
    """Veredito do grounding (Evidence Validator) para uma afirmação sobre a empresa.

    Para cada campo não-vazio do `DadosEmpresa`, o faithfulness check diz se algum
    trecho coletado o sustenta e qual fonte (URL) o ancora. Dá rastreabilidade e
    alimenta a decisão do loop.
    """

    campo: str                          # nome do campo verificado (ex.: "funding")
    valor: str = ""                     # o valor afirmado
    sustentada: bool = False            # há trecho coletado que sustenta?
    fonte: Optional[str] = None         # URL do trecho que sustenta (se houver)


class Classificacao(BaseModel):
    """Saída estruturada do Classifier — os 3 eixos AI-native (CLAUDE.md).

    `rotulo` é usado pelo desvio condicional do grafo; os 3 eixos e a
    justificativa dão rastreabilidade ao julgamento.
    """

    rotulo: Literal["ai-native", "ai-enabled", "non-ai"]
    eixo_produto: str = ""          # a IA é o core do valor? (se remove a IA, sobra produto?)
    eixo_dados_modelo: str = ""     # tem dado proprietário e/ou modelo próprio?
    eixo_stack: str = ""            # controla custo/latência da própria inferência?
    justificativa: str = ""


class Recomendacao(BaseModel):
    """Saída estruturada do Recommendation Agent.

    Os 7 campos da recomendação. O agente deve
    produzir isto como structured output (não texto solto) e toda recomendação
    precisa citar a origem (campo `evidencias`).
    """

    tecnologias: list[str] = Field(default_factory=list)        # 1. tecnologias NVIDIA recomendadas
    justificativa_tecnica: str = ""                             # 2. por que tecnicamente
    justificativa_negocio: str = ""                             # 3. por que para o negócio (custo, latência, defensibilidade)
    prioridade: Optional[str] = None                            # 4. nível de prioridade (ex.: alta/média/baixa)
    complexidade: Optional[str] = None                          # 5. complexidade de implementação
    proxima_acao: str = ""                                      # 6. próxima ação sugerida para o time NVIDIA
    evidencias: list[str] = Field(default_factory=list)         # 7. evidências/fontes usadas


class Score(BaseModel):
    """Score composto (brief). As 4 notas (0–10) são julgadas pelo LLM; `composto`
    é a soma ponderada calculada pelo código (pesos configuráveis em settings)."""

    ai_native: float = 0.0      # quão AI-native (alinhado à classificação)
    nvidia_fit: float = 0.0     # tamanho do gap/uplift que a NVIDIA destrava
    tracao: float = 0.0         # tração / sinais de funding/VC
    time_ia: float = 0.0        # força do time de IA (founders/tecnologias)
    composto: float = 0.0       # Σ wᵢ·notaᵢ (código)


class RadarState(BaseModel):
    consulta: str = ""                                  # entrada do usuário
    alvos: list[str] = Field(default_factory=list)      # empresas a investigar
    urls_busca: list[str] = Field(default_factory=list)  # URLs a coletar (Search Planner)
    conteudo_bruto: list[dict] = Field(default_factory=list)   # trechos + fonte
    dados_estruturados: Optional[DadosEmpresa] = None   # schema extraído (structured output)
    classificacao: Optional[str] = None                 # rótulo: "ai-native" | "ai-enabled" | "non-ai"
    classificacao_detalhe: Optional[Classificacao] = None  # análise rica dos 3 eixos
    evidencias_ok: bool = False                         # gate do Evidence Validator
    afirmacoes_verificadas: list[VerificacaoAfirmacao] = Field(default_factory=list)  # vereditos do grounding
    tentativas: int = 0                                 # teto do loop do Validator
    contexto_rag: list[str] = Field(default_factory=list)      # trechos NVIDIA recuperados
    recomendacao: Optional[Recomendacao] = None         # saída estruturada (7 campos)
    score: Optional[Score] = None                       # score composto (4 notas + composto)
    briefing: str = ""                                  # relatório executivo final
