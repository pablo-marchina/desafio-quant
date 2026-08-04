"""Config central do TAPI (F0.3).

Uso: `from packages.config import get_settings; s = get_settings()`.
"""

from .settings import RerankerProvider, Settings, get_settings

__all__ = ["Settings", "get_settings", "RerankerProvider"]
