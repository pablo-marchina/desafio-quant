from __future__ import annotations

from pathlib import Path
from typing import Any

from src.governance.catalog_loader import (
    load_maximal_catalog,
    slug_to_module_name,
)
from src.governance.catalog_schemas import (
    CandidateStatus,
    ExpectedRuntimeUse,
    MaximalCandidateEntry,
)
from src.governance.schemas import GateReport


class RuntimeCatalog:
    _instance: RuntimeCatalog | None = None

    def __init__(self, csv_path: Path | None = None) -> None:
        self._entries: dict[str, MaximalCandidateEntry] = {}
        self._by_category: dict[str, list[MaximalCandidateEntry]] = {}
        self._initialized = False
        self._csv_path = csv_path

    @classmethod
    def initialize(cls, csv_path: Path | None = None) -> RuntimeCatalog:
        instance = RuntimeCatalog(csv_path)
        instance.load()
        RuntimeCatalog._instance = instance
        return instance

    @classmethod
    def get_instance(cls) -> RuntimeCatalog:
        if cls._instance is None:
            cls._instance = RuntimeCatalog()
            cls._instance.load()
        return cls._instance

    def load(self) -> None:
        entries = load_maximal_catalog(self._csv_path) if self._csv_path else load_maximal_catalog()
        self._entries = {e.candidate_id: e for e in entries}
        self._by_category.clear()
        for entry in entries:
            self._by_category.setdefault(entry.category, []).append(entry)
        self._initialized = True

    @property
    def is_loaded(self) -> bool:
        return self._initialized

    @property
    def all_entries(self) -> list[MaximalCandidateEntry]:
        return list(self._entries.values())

    @property
    def count(self) -> int:
        return len(self._entries)

    def get(self, candidate_id: str) -> MaximalCandidateEntry | None:
        return self._entries.get(candidate_id)

    def find_by_name(self, name: str) -> list[MaximalCandidateEntry]:
        return [e for e in self._entries.values() if e.name.lower() == name.lower()]

    def get_by_category(self, category: str) -> list[MaximalCandidateEntry]:
        return self._by_category.get(category, [])

    def get_categories(self) -> list[str]:
        return sorted(self._by_category)

    def get_active_runtime_entries(self) -> list[MaximalCandidateEntry]:
        return [
            e for e in self._entries.values() if e.expected_runtime_use == ExpectedRuntimeUse.ACTIVE_PRODUCT_RUNTIME
        ]

    def get_governance_entries(self) -> list[MaximalCandidateEntry]:
        return [
            e
            for e in self._entries.values()
            if e.expected_runtime_use == ExpectedRuntimeUse.CANDIDATE_OR_SUPPORTING_GOVERNANCE
        ]

    def get_benchmarked_entries(self) -> list[MaximalCandidateEntry]:
        return [e for e in self._entries.values() if e.status == CandidateStatus.BENCHMARKED]

    def get_by_status(self, status: CandidateStatus) -> list[MaximalCandidateEntry]:
        return [e for e in self._entries.values() if e.status == status]

    def get_summary(self) -> dict[str, Any]:
        by_status: dict[str, int] = {}
        by_runtime_use: dict[str, int] = {}
        for entry in self._entries.values():
            s = entry.status.value
            by_status[s] = by_status.get(s, 0) + 1
            ru = entry.expected_runtime_use.value if entry.expected_runtime_use else "unknown"
            by_runtime_use[ru] = by_runtime_use.get(ru, 0) + 1
        return {
            "total_candidates": len(self._entries),
            "by_status": by_status,
            "by_expected_runtime_use": by_runtime_use,
            "categories": sorted(self._by_category),
            "is_loaded": self._initialized,
        }

    def check_catalog_complete(self) -> GateReport:
        failures: list[str] = []
        warnings: list[str] = []
        for entry in self._entries.values():
            if not entry.candidate_id:
                failures.append(f"Entry '{entry.name}' missing candidate_id")
            if not entry.name:
                failures.append(f"Entry {entry.candidate_id} missing name")
            if not entry.category:
                warnings.append(f"Entry '{entry.name}' missing category")
        return GateReport(
            gate_id="check_candidate_catalog_complete",
            status="PASS" if not failures else "FAIL",
            checked_items=len(self._entries),
            failures=failures,
            warnings=warnings,
        )

    def module_for_candidate(self, candidate_id: str) -> str:
        return slug_to_module_name(candidate_id)
