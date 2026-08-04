"""Excecoes de dominio do modulo startup_discovery."""


class DiscoveryRunNotFoundError(Exception):
    """DiscoveryRun nao encontrado pelo id informado."""


class InvalidDiscoveryRunTransitionError(Exception):
    """Transicao de status invalida para um DiscoveryRun."""


class InvalidCandidateTransitionError(Exception):
    """Transicao de status invalida para um StartupDiscoveryCandidate."""


class CandidateNotFoundError(Exception):
    """StartupDiscoveryCandidate nao encontrado pelo id informado."""
