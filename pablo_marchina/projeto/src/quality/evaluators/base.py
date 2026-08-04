from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from sqlalchemy.orm import Session


class BaseQualityEvaluator(ABC):
    def __init__(self, session: Session) -> None:
        self.session = session

    @abstractmethod
    def evaluate(self, analysis_run_id: str) -> dict[str, Any]: ...
