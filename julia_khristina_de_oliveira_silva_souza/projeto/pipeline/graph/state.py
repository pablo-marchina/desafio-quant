from typing import TypedDict, List, Optional, Annotated
import operator


class StartupData(TypedDict):
    id: Optional[str]
    nome: str
    website: str
    setor: str
    descricao: Optional[str]
    produto_principal: Optional[str]
    tecnologias_detectadas: List[str]
    fontes_url: List[str]


class AgentState(TypedDict):
    setor_alvo: str
    consulta_usuario: Optional[str]

    queries_geradas: List[dict]

    startups_coletadas: Annotated[List[StartupData], operator.add]
    erros: Annotated[List[str], operator.add]

    startups_classificadas: List[dict]

    startups_validadas: List[dict]

    recomendacoes_rag: List[dict]

    recomendacoes_finais: List[dict]

    briefings: List[dict]

    etapa_atual: str
    iteracao: int
