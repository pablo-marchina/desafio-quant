"""Excecoes do modulo recommendations."""


class RecommendationError(Exception):
    """Erro base do modulo recommendations."""


class RecommendationNotFoundError(RecommendationError):
    """Recomendacao nao encontrada."""


class StartupProfileUnavailableError(RecommendationError):
    """Perfil da startup nao pode ser lido no modulo startups."""
