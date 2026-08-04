"""Excecoes do modulo briefing."""


class BriefingError(Exception):
    """Erro base do modulo briefing."""


class BriefingNotFoundError(BriefingError):
    """Briefing nao encontrado."""


class StartupProfileUnavailableError(BriefingError):
    """Perfil da startup nao pode ser lido no modulo startups."""


class BriefingRenderingError(BriefingError):
    """Falha ao renderizar o briefing em PDF."""
