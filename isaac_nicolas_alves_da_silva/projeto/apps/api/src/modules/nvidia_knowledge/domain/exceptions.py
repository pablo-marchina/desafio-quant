"""Excecoes do modulo NVIDIA Knowledge."""


class NvidiaKnowledgeError(Exception):
    """Erro base do modulo NVIDIA Knowledge."""


class NvidiaTechnologyNotFoundError(NvidiaKnowledgeError):
    """Tecnologia NVIDIA nao encontrada."""
