"""Logging estruturado compartilhado entre modulos e workers.

Unico ponto de entrada: ``get_logger(name)`` e ``bind_context(**ids)``.
Ver ``logger.py`` para detalhes.
"""

from apps.api.src.shared.logging.logger import bind_context, get_logger, log_job

__all__ = ["bind_context", "get_logger", "log_job"]
