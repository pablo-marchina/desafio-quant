from __future__ import annotations

import threading

from radar.database.repository import (
    ensure_contact_discovery_steps_registered,
    update_contact_discovery_step,
)

_STEP_LABELS = {
    "preparing_queries": "Preparando queries de busca",
    "searching_web": "Buscando paginas de contato",
    "extracting_contacts": "Extraindo informacoes de contato",
    "fallback_sources": "Extraindo de fontes existentes",
    "cross_referencing": "Cruzando referencias",
    "saving_result": "Salvando resultado",
}


class ContactDiscoveryTracker:
    def __init__(self, discovery_id: int):
        self.discovery_id = discovery_id

    def start(self, step_key: str, detail: str = "") -> None:
        update_contact_discovery_step(
            self.discovery_id, step_key,
            status="running",
            detail=detail or _step_label(step_key),
            error_message=None,
        )

    def complete(self, step_key: str, detail: str = "") -> None:
        update_contact_discovery_step(
            self.discovery_id, step_key,
            status="completed",
            detail=detail or None,
        )

    def fail(self, step_key: str, error: str, detail: str = "") -> None:
        update_contact_discovery_step(
            self.discovery_id, step_key,
            status="error",
            detail=detail or f"{_step_label(step_key)} falhou",
            error_message=error,
        )

    def set_detail(self, step_key: str, detail: str) -> None:
        update_contact_discovery_step(
            self.discovery_id, step_key,
            detail=detail,
        )

    def ensure_steps_registered(self) -> None:
        ensure_contact_discovery_steps_registered(self.discovery_id)


_tracker_local = threading.local()


def get_contact_tracker() -> ContactDiscoveryTracker | None:
    return getattr(_tracker_local, "contact_tracker", None)


def set_contact_tracker(tracker: ContactDiscoveryTracker | None) -> None:
    _tracker_local.contact_tracker = tracker


def _step_label(key: str) -> str:
    return _STEP_LABELS.get(key, key)
