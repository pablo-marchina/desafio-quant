"""Camada de persistência do TAPI (F0.6).

Uso: `from packages.db import Company, Run, get_session`.
As migrações ficam em `migrations/` (Alembic); `SQLModel.metadata` é o target.
"""

from .engine import get_engine, get_session
from .models import Company, Evidence, Founder, Recommendation, Run, Score

__all__ = [
    "get_engine",
    "get_session",
    "Run",
    "Company",
    "Founder",
    "Evidence",
    "Score",
    "Recommendation",
]
