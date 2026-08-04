from __future__ import annotations

from abc import ABC, abstractmethod

from src.models import Evidence

from ..schemas import StructuredStartupExtraction


class StructuredExtractionProvider(ABC):
    @abstractmethod
    def extract(
        self,
        startup_name: str,
        evidences: list[Evidence],
    ) -> StructuredStartupExtraction:
        raise NotImplementedError
