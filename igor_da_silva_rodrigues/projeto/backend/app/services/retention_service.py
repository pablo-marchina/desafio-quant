from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from app.persistence.persistence_service import PipelinePersistence


@dataclass(frozen=True)
class RetentionPolicy:
    trace_days: int = 90
    raw_days: int = 180
    pipeline_cache_days: int = 30
    rate_limit_days: int = 2


@dataclass(frozen=True)
class RetentionAction:
    kind: str
    target: str
    cutoff: str


class RetentionService:
    """Plan and execute bounded retention without following paths outside managed roots."""

    def __init__(
        self,
        persistence: PipelinePersistence | None = None,
        backend_dir: Path | None = None,
        policy: RetentionPolicy | None = None,
    ) -> None:
        self.persistence = persistence
        self.backend_dir = (backend_dir or Path(__file__).resolve().parents[2]).resolve()
        self.policy = policy or RetentionPolicy()
        self.raw_dir = (self.backend_dir / "data" / "raw").resolve()
        self.pipeline_cache_dir = (self.backend_dir / "data" / "cache" / "pipeline").resolve()

    def run(self, execute: bool = False, now: datetime | None = None) -> dict[str, Any]:
        now_value = now or datetime.now(UTC)
        actions = self._filesystem_actions(now_value)
        if self.persistence is not None:
            actions.extend(self._trace_actions(now_value))
        if execute:
            self._execute_filesystem(actions)
            if self.persistence is not None:
                self._execute_database(now_value, actions)
        return {
            "mode": "execute" if execute else "dry-run",
            "policy": asdict(self.policy),
            "total_actions": len(actions),
            "actions": [asdict(action) for action in actions],
        }

    def _filesystem_actions(self, now: datetime) -> list[RetentionAction]:
        actions = []
        actions.extend(
            self._expired_files(self.raw_dir, now - timedelta(days=self.policy.raw_days), "raw")
        )
        actions.extend(
            self._expired_files(
                self.pipeline_cache_dir,
                now - timedelta(days=self.policy.pipeline_cache_days),
                "pipeline_cache",
            )
        )
        return actions

    def _expired_files(self, root: Path, cutoff: datetime, kind: str) -> list[RetentionAction]:
        if not root.exists():
            return []
        actions = []
        for path in root.rglob("*"):
            if not path.is_file() or path.is_symlink():
                continue
            resolved = path.resolve()
            resolved.relative_to(root)
            modified = datetime.fromtimestamp(path.stat().st_mtime, tz=UTC)
            if modified < cutoff:
                actions.append(RetentionAction(kind, str(resolved), cutoff.isoformat()))
        return actions

    def _trace_actions(self, now: datetime) -> list[RetentionAction]:
        persistence = self._require_persistence()
        cutoff = now - timedelta(days=self.policy.trace_days)
        response = (
            persistence.db.table("pipeline_runs")
            .select("id,trace_path,created_at")
            .lt("created_at", cutoff.isoformat())
            .execute()
        )
        return [
            RetentionAction("trace", row["trace_path"], cutoff.isoformat())
            for row in response.data or []
            if row.get("trace_path")
        ]

    def _execute_filesystem(self, actions: list[RetentionAction]) -> None:
        for action in actions:
            if action.kind not in {"raw", "pipeline_cache"}:
                continue
            path = Path(action.target).resolve()
            allowed_root = self.raw_dir if action.kind == "raw" else self.pipeline_cache_dir
            path.relative_to(allowed_root)
            path.unlink(missing_ok=True)

    def _execute_database(self, now: datetime, actions: list[RetentionAction]) -> None:
        persistence = self._require_persistence()
        trace_paths = [action.target for action in actions if action.kind == "trace"]
        if trace_paths:
            persistence.supabase.storage.from_(persistence.bucket).remove(trace_paths)
            for path in trace_paths:
                persistence.db.table("pipeline_runs").update({"trace_path": None}).eq(
                    "trace_path", path
                ).execute()
        persistence.db.table("web_content_cache").delete().lt(
            "expires_at", now.isoformat()
        ).execute()
        persistence.db.table("revoked_auth_tokens").delete().lt(
            "expires_at", now.isoformat()
        ).execute()
        rate_cutoff = now - timedelta(days=self.policy.rate_limit_days)
        persistence.db.table("api_rate_limits").delete().lt(
            "updated_at", rate_cutoff.isoformat()
        ).execute()

    def _require_persistence(self) -> PipelinePersistence:
        if self.persistence is None:
            raise RuntimeError("Persistencia obrigatoria para a politica de banco e traces")
        return self.persistence
