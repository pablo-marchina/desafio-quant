from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel, Field


class BenchmarkDataset(BaseModel):
    dataset_id: str
    name: str
    version: str
    path: str
    task_type: str
    source_policy_ref: str
    created_by: str = "product"
    notes: str = ""


class BenchmarkDatasetRegistry(BaseModel):
    datasets: list[BenchmarkDataset] = Field(default_factory=list)

    def add(self, dataset: BenchmarkDataset) -> None:
        existing = {item.dataset_id for item in self.datasets}
        if dataset.dataset_id in existing:
            raise ValueError(f"Duplicate dataset_id: {dataset.dataset_id}")
        self.datasets.append(dataset)

    def get(self, dataset_id: str) -> BenchmarkDataset:
        for dataset in self.datasets:
            if dataset.dataset_id == dataset_id:
                return dataset
        raise KeyError(dataset_id)

    @classmethod
    def load(cls, path: Path) -> BenchmarkDatasetRegistry:
        if not path.exists():
            return cls()
        payload = json.loads(path.read_text(encoding="utf-8"))
        return cls.model_validate(payload)

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(self.model_dump(mode="json"), indent=2, sort_keys=True, ensure_ascii=True) + "\n",
            encoding="utf-8",
        )
