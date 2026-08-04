"""Exceções conhecidas pelo domínio do módulo agents.

Seguem o mesmo espírito das exceções de ``scraping``: descrevem situações
esperadas pelo negócio, sem saber como serão apresentadas ao usuário final.
"""


class AgentError(Exception):
    """Classe base para todos os erros conhecidos do módulo agents."""


class AgentInvestigationError(AgentError):
    """A investigação não pôde ser concluída por um motivo conhecido.

    Exemplos: o provedor de LLM falhou, devolveu uma resposta inválida, ou um
    limite operacional (tokens, iterações, tempo) foi atingido antes de uma
    decisão final.

    A camada que chama o módulo agents (hoje, o adaptador dentro de
    ``scraping``) decide como reagir a este erro — por exemplo, tratando a
    investigação como inconclusiva.
    """


class AgentPlanningError(AgentError):
    """O agente nao conseguiu gerar um plano de busca valido."""


class AgentSearchExecutionError(AgentError):
    """O executor de busca web nao conseguiu devolver URLs candidatas."""


class AgentClassificationError(AgentError):
    """O agente nao conseguiu classificar a maturidade de IA da startup."""


class AgentExtractionError(AgentError):
    """O agente nao conseguiu extrair dados estruturados das evidencias."""


class AgentRagQueryError(AgentError):
    """O agente nao conseguiu consultar a base de conhecimento NVIDIA via RAG."""


class AgentRecommendationError(AgentError):
    """O agente nao conseguiu gerar ou revisar recomendacoes para a startup."""


class AgentBriefingError(AgentError):
    """O agente nao conseguiu gerar ou reescrever o briefing da startup."""


class AgentTaskDispatchError(AgentError):
    """O job de agente nao foi publicado na fila."""


class UnsupportedAgentJobError(AgentError):
    """O worker recebeu um tipo de job de agente ainda nao suportado."""


class AgentRunNotFoundError(AgentError):
    """A execucao de agente solicitada nao existe."""


class AgentServiceUnavailableError(AgentError):
    """O servico de agente requerido nao esta configurado (ex: chave de API ausente)."""


class AgentRunInterruptedError(AgentError):
    """O grafo pausou a execucao aguardando revisao humana."""


class InvalidAgentRunTransitionError(AgentError):
    """A execucao de agente tentou mudar para um estado invalido."""


class InvalidAgentStepTransitionError(AgentError):
    """A etapa de agente tentou mudar para um estado invalido."""
