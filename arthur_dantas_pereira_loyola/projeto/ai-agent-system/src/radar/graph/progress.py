from __future__ import annotations

import threading

from radar.database.repository import update_run_step_status

_STEP_ORDER = [
    "search_planner",
    "scraper",
    "extractor",
    "validator",
    "classifier",
    "nvidia_rag",
    "recommendation",
    "briefing",
]


class PipelineTracker:
    def __init__(self, run_id: int):
        self.run_id = run_id

    def start(self, step_key: str, detail: str = "") -> None:
        update_run_step_status(
            self.run_id, step_key,
            status="running",
            detail=detail or f"Executando {_step_label(step_key)}...",
            error_message=None,
        )

    def complete(self, step_key: str, detail: str = "") -> None:
        update_run_step_status(
            self.run_id,
            step_key,
            status="completed",
            detail=detail or None,
        )

    def fail(self, step_key: str, error: str, detail: str = "") -> None:
        update_run_step_status(
            self.run_id, step_key,
            status="error",
            detail=detail or f"{_step_label(step_key)} falhou",
            error_message=error,
        )

    def set_detail(self, step_key: str, detail: str) -> None:
        update_run_step_status(
            self.run_id, step_key,
            detail=detail,
        )

    def ensure_steps_registered(self) -> None:
        for sk in _STEP_ORDER:
            update_run_step_status(self.run_id, sk, status="idle")


_tracker_local = threading.local()


def get_tracker() -> PipelineTracker | None:
    return getattr(_tracker_local, "tracker", None)


def set_tracker(tracker: PipelineTracker | None) -> None:
    _tracker_local.tracker = tracker


def _step_label(key: str) -> str:
    labels = {
        "search_planner": "Search Planner",
        "scraper": "Scraper",
        "extractor": "Extractor",
        "classifier": "Classifier",
        "validator": "Validator",
        "nvidia_rag": "RAG Agent",
        "recommendation": "Recommendation",
        "briefing": "Briefing",
    }
    return labels.get(key, key)

