from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any, Iterable
from uuid import UUID

from app.persistence.models import (
    BatchDeadLetter,
    BatchItem,
    BatchItemStatus,
    BatchRun,
    BatchStatus,
)
from app.persistence.persistence_service import PersistenceError, PipelinePersistence


TERMINAL_ITEM_STATUSES = {"completed", "partial", "failed", "skipped"}


class BatchRepository:
    """Persist and recover durable batch execution state in Supabase."""

    def __init__(self, persistence: PipelinePersistence) -> None:
        self.persistence = persistence
        self.db = persistence.db

    @classmethod
    def from_env(cls) -> "BatchRepository":
        return cls(PipelinePersistence.from_env())

    def create_batch(
        self,
        source_path: str,
        startups: list[dict[str, Any]],
        options: dict[str, Any] | None = None,
    ) -> UUID:
        if not startups:
            raise ValueError("O lote deve conter pelo menos uma startup")
        run = BatchRun(
            source_path=source_path,
            total_items=len(startups),
            options=options or {},
        )
        try:
            response = self.db.table("batch_runs").insert(
                run.model_dump(
                    mode="json",
                    exclude={"id", "created_at", "updated_at"},
                    exclude_none=True,
                )
            ).execute()
            batch_id = UUID(_first_required(response, "batch_runs.insert")["id"])
            items = [
                BatchItem(
                    batch_run_id=batch_id,
                    startup_external_id=str(startup["startup_id"]),
                    startup_name=str(startup["nome"]),
                    startup_payload=startup,
                ).model_dump(
                    mode="json",
                    exclude={"id", "created_at", "updated_at"},
                    exclude_none=True,
                )
                for startup in startups
            ]
            self.db.table("batch_items").insert(items).execute()
            return batch_id
        except Exception as exc:
            raise PersistenceError(f"create_batch: {exc}") from exc

    def get_batch(self, batch_id: UUID) -> dict[str, Any]:
        response = (
            self.db.table("batch_runs")
            .select("*")
            .eq("id", str(batch_id))
            .limit(1)
            .execute()
        )
        return _first_required(response, f"Lote nao encontrado: {batch_id}")

    def list_items(
        self,
        batch_id: UUID,
        statuses: Iterable[BatchItemStatus | str] | None = None,
    ) -> list[dict[str, Any]]:
        response = (
            self.db.table("batch_items")
            .select("*")
            .eq("batch_run_id", str(batch_id))
            .execute()
        )
        rows = list(getattr(response, "data", None) or [])
        allowed = set(statuses or [])
        if allowed:
            rows = [row for row in rows if row.get("status") in allowed]
        return sorted(rows, key=lambda row: (row.get("created_at") or "", row["startup_name"]))

    def start_batch(self, batch_id: UUID) -> None:
        current = self.get_batch(batch_id)
        if current["status"] == "cancelled":
            raise ValueError("Lote cancelado nao pode ser iniciado")
        updates: dict[str, Any] = {"status": "running", "finished_at": None}
        if not current.get("started_at"):
            updates["started_at"] = datetime.now(UTC).isoformat()
        self._update_batch(batch_id, updates)

    def queue_batch(self, batch_id: UUID) -> None:
        current = self.get_batch(batch_id)
        if current["status"] == "completed":
            raise ValueError("Lote concluido nao pode ser reenfileirado")
        self._update_batch(
            batch_id,
            {
                "status": "pending",
                "worker_id": None,
                "heartbeat_at": None,
                "lease_expires_at": None,
                "finished_at": None,
            },
        )

    def claim_next_batch(
        self,
        worker_id: str,
        lease_seconds: int = 120,
    ) -> dict[str, Any] | None:
        candidates = (
            self.db.table("batch_runs")
            .select("*")
            .eq("status", "pending")
            .order("created_at")
            .limit(5)
            .execute()
        )
        now_value = datetime.now(UTC)
        now = now_value.isoformat()
        lease_expires_at = (now_value + timedelta(seconds=lease_seconds)).isoformat()
        for candidate in list(getattr(candidates, "data", None) or []):
            response = (
                self.db.table("batch_runs")
                .update(
                    {
                        "status": "running",
                        "worker_id": worker_id,
                        "heartbeat_at": now,
                        "lease_expires_at": lease_expires_at,
                        "started_at": candidate.get("started_at") or now,
                        "finished_at": None,
                    }
                )
                .eq("id", candidate["id"])
                .eq("status", "pending")
                .execute()
            )
            data = getattr(response, "data", None) or []
            if data:
                return data[0]
            current = self.get_batch(UUID(candidate["id"]))
            if current.get("worker_id") == worker_id and current.get("status") == "running":
                return current
        return None

    def heartbeat(self, batch_id: UUID, worker_id: str, lease_seconds: int = 120) -> None:
        now = datetime.now(UTC)
        self.db.table("batch_runs").update(
            {
                "heartbeat_at": now.isoformat(),
                "lease_expires_at": (now + timedelta(seconds=lease_seconds)).isoformat(),
            }
        ).eq("id", str(batch_id)).eq("worker_id", worker_id).eq("status", "running").execute()

    def recover_stale_batches(self, stale_after_minutes: int = 30) -> int:
        threshold = datetime.now(UTC) - timedelta(minutes=stale_after_minutes)
        response = self.db.table("batch_runs").select("*").eq("status", "running").execute()
        recovered = 0
        for batch in list(getattr(response, "data", None) or []):
            lease_expires = _parse_datetime(batch.get("lease_expires_at"))
            heartbeat = _parse_datetime(batch.get("heartbeat_at") or batch.get("updated_at"))
            if lease_expires is not None and lease_expires > datetime.now(UTC):
                continue
            if lease_expires is None and heartbeat is not None and heartbeat >= threshold:
                continue
            batch_id = UUID(batch["id"])
            self.recover_interrupted_items(batch_id)
            self.queue_batch(batch_id)
            recovered += 1
        return recovered

    def recover_interrupted_items(self, batch_id: UUID) -> int:
        running = self.list_items(batch_id, statuses={"running"})
        for item in running:
            self._update_item(
                UUID(item["id"]),
                {
                    "status": "pending",
                    "last_error": "Execucao anterior interrompida; item devolvido para a fila.",
                    "started_at": None,
                },
            )
        return len(running)

    def requeue_retryable_items(self, batch_id: UUID, max_attempts: int) -> int:
        failed = self.list_items(batch_id, statuses={"failed"})
        retryable = [item for item in failed if int(item.get("attempt_count") or 0) < max_attempts]
        for item in retryable:
            self._update_item(
                UUID(item["id"]),
                {"status": "pending", "finished_at": None},
            )
        return len(retryable)

    def requeue_partial_items(self, batch_id: UUID) -> int:
        partial = self.list_items(batch_id, statuses={"partial"})
        for item in partial:
            self._update_item(
                UUID(item["id"]),
                {
                    "status": "pending",
                    "pipeline_run_id": None,
                    "last_error": None,
                    "result_summary": {},
                    "started_at": None,
                    "finished_at": None,
                },
            )
        return len(partial)

    def start_item(self, item_id: UUID) -> None:
        item = self.get_item(item_id)
        self._update_item(
            item_id,
            {
                "status": "running",
                "attempt_count": int(item.get("attempt_count") or 0) + 1,
                "last_error": None,
                "started_at": datetime.now(UTC).isoformat(),
                "finished_at": None,
            },
        )

    def finish_item(
        self,
        item_id: UUID,
        status: BatchItemStatus,
        pipeline_run_id: UUID | None = None,
        result_summary: dict[str, Any] | None = None,
        error: str | None = None,
    ) -> None:
        if status not in TERMINAL_ITEM_STATUSES:
            raise ValueError(f"Status final de item invalido: {status}")
        self._update_item(
            item_id,
            {
                "status": status,
                "pipeline_run_id": str(pipeline_run_id) if pipeline_run_id else None,
                "result_summary": result_summary or {},
                "last_error": error,
                "finished_at": datetime.now(UTC).isoformat(),
            },
        )

    def get_item(self, item_id: UUID) -> dict[str, Any]:
        response = (
            self.db.table("batch_items")
            .select("*")
            .eq("id", str(item_id))
            .limit(1)
            .execute()
        )
        return _first_required(response, f"Item de lote nao encontrado: {item_id}")

    def finalize_batch(self, batch_id: UUID) -> dict[str, Any]:
        items = self.list_items(batch_id)
        counts = {status: 0 for status in TERMINAL_ITEM_STATUSES}
        for item in items:
            if item["status"] in counts:
                counts[item["status"]] += 1
        processed = sum(counts.values())
        total = len(items)
        if processed < total:
            status: BatchStatus = "running"
            finished_at = None
        elif counts["failed"] == total:
            status = "failed"
            finished_at = datetime.now(UTC).isoformat()
        elif counts["failed"] or counts["partial"]:
            status = "partial"
            finished_at = datetime.now(UTC).isoformat()
        else:
            status = "completed"
            finished_at = datetime.now(UTC).isoformat()
        updates = {
            "status": status,
            "processed_items": processed,
            "succeeded_items": counts["completed"],
            "partial_items": counts["partial"],
            "failed_items": counts["failed"],
            "finished_at": finished_at,
        }
        if finished_at:
            updates["lease_expires_at"] = None
        self._update_batch(batch_id, updates)
        return self.get_batch(batch_id)

    def cancel_batch(self, batch_id: UUID) -> None:
        self._update_batch(
            batch_id,
            {
                "status": "cancelled",
                "finished_at": datetime.now(UTC).isoformat(),
                "lease_expires_at": None,
            },
        )

    def fail_batch(self, batch_id: UUID, error: str) -> None:
        current = self.get_batch(batch_id)
        errors = list(current.get("errors") or [])
        errors.append(error[:2000])
        self._update_batch(
            batch_id,
            {
                "status": "failed",
                "errors": errors,
                "heartbeat_at": datetime.now(UTC).isoformat(),
                "finished_at": datetime.now(UTC).isoformat(),
                "lease_expires_at": None,
            },
        )

    def is_cancelled(self, batch_id: UUID) -> bool:
        return self.get_batch(batch_id)["status"] == "cancelled"

    def list_batches(self, limit: int = 20) -> list[dict[str, Any]]:
        response = (
            self.db.table("batch_runs")
            .select("*")
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
        )
        return list(getattr(response, "data", None) or [])

    def dead_letter_exhausted_items(self, batch_id: UUID, max_attempts: int) -> int:
        failed = self.list_items(batch_id, statuses={"failed"})
        exhausted = [item for item in failed if int(item.get("attempt_count") or 0) >= max_attempts]
        for item in exhausted:
            model = BatchDeadLetter(
                batch_run_id=batch_id,
                batch_item_id=UUID(item["id"]),
                startup_external_id=item["startup_external_id"],
                startup_name=item["startup_name"],
                startup_payload=item.get("startup_payload") or {},
                attempt_count=int(item["attempt_count"]),
                last_error=item.get("last_error") or "Falha sem mensagem",
            )
            self.db.table("batch_dead_letters").upsert(
                model.model_dump(
                    mode="json",
                    exclude={"id", "failed_at", "resolved_at", "created_at"},
                    exclude_none=True,
                ),
                on_conflict="batch_item_id",
            ).execute()
        return len(exhausted)

    def list_dead_letters(self, batch_id: UUID) -> list[dict[str, Any]]:
        response = (
            self.db.table("batch_dead_letters")
            .select("*")
            .eq("batch_run_id", str(batch_id))
            .execute()
        )
        return list(getattr(response, "data", None) or [])

    def replay_dead_letter(self, dead_letter_id: UUID) -> UUID:
        response = (
            self.db.table("batch_dead_letters")
            .select("*")
            .eq("id", str(dead_letter_id))
            .limit(1)
            .execute()
        )
        letter = _first_required(response, f"Dead letter nao encontrada: {dead_letter_id}")
        item_id = UUID(letter["batch_item_id"])
        self._update_item(
            item_id,
            {
                "status": "pending",
                "attempt_count": 0,
                "last_error": None,
                "started_at": None,
                "finished_at": None,
            },
        )
        self.db.table("batch_dead_letters").update(
            {"resolved_at": datetime.now(UTC).isoformat()}
        ).eq("id", str(dead_letter_id)).execute()
        self.queue_batch(UUID(letter["batch_run_id"]))
        return item_id

    def _update_batch(self, batch_id: UUID, values: dict[str, Any]) -> None:
        self.db.table("batch_runs").update(values).eq("id", str(batch_id)).execute()

    def _update_item(self, item_id: UUID, values: dict[str, Any]) -> None:
        self.db.table("batch_items").update(values).eq("id", str(item_id)).execute()


def _first_required(response: Any, operation: str) -> dict[str, Any]:
    data = getattr(response, "data", None)
    row = data[0] if isinstance(data, list) and data else data
    if not isinstance(row, dict):
        raise PersistenceError(operation)
    return row


def _parse_datetime(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)
    except ValueError:
        return None
