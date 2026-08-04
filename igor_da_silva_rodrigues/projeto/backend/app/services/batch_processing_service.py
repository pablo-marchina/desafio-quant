from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable, cast
from uuid import UUID

from pydantic import BaseModel, Field

from app.core.observability import LOGGER
from app.persistence.batch_repository import BatchRepository
from app.persistence.models import BatchItemStatus
from app.persistence.pipeline_with_persistence import run_pipeline_with_persistence
from app.persistence.web_cache import web_usage_context


PipelineRunner = Callable[[dict[str, Any]], dict[str, Any]]


class BatchExecutionOptions(BaseModel):
    """Validated controls for one curated startup batch."""

    limit: int | None = Field(default=None, ge=1, le=50)
    startup_ids: list[str] = Field(default_factory=list, max_length=50)
    include_ineligible: bool = True
    max_attempts: int = Field(default=2, ge=1, le=3)
    stop_on_error: bool = False


class CuratedStartupLoader:
    """Load only curated JSON files from the project's controlled data directory."""

    def __init__(self, base_dir: Path | None = None) -> None:
        backend_dir = Path(__file__).resolve().parents[2]
        self.base_dir = (base_dir or backend_dir / "data" / "curated" / "_cubo").resolve()

    def latest_path(self) -> Path:
        files = sorted(self.base_dir.glob("*.json"), key=lambda path: path.stat().st_mtime)
        if not files:
            raise FileNotFoundError(f"Nenhum arquivo CURATED encontrado em {self.base_dir}")
        return files[-1]

    def load(self, source_path: str | Path | None = None) -> tuple[Path, list[dict[str, Any]]]:
        path = self._resolve_path(source_path)
        payload = json.loads(path.read_text(encoding="utf-8"))
        startups = payload.get("startups") if isinstance(payload, dict) else None
        if not isinstance(startups, list):
            raise ValueError("Arquivo CURATED deve conter uma lista em 'startups'")
        valid = []
        for index, startup in enumerate(startups):
            if not isinstance(startup, dict) or not startup.get("startup_id") or not startup.get("nome"):
                raise ValueError(f"Startup CURATED invalida no indice {index}")
            valid.append(startup)
        return path, valid

    def select(
        self,
        startups: list[dict[str, Any]],
        options: BatchExecutionOptions,
    ) -> list[dict[str, Any]]:
        selected = startups
        if options.startup_ids:
            requested = set(options.startup_ids)
            selected = [item for item in selected if item["startup_id"] in requested]
            missing = requested - {item["startup_id"] for item in selected}
            if missing:
                raise ValueError("startup_ids nao encontrados: " + ", ".join(sorted(missing)))
        if not options.include_ineligible:
            selected = [
                item for item in selected if item.get("decisao_pipeline", {}).get("prosseguir") is True
            ]
        if options.limit is not None:
            selected = selected[: options.limit]
        if not selected:
            raise ValueError("Nenhuma startup atende aos filtros do lote")
        return selected

    def _resolve_path(self, source_path: str | Path | None) -> Path:
        if source_path is None:
            return self.latest_path()
        candidate = Path(source_path)
        if not candidate.is_absolute():
            candidate = self.base_dir / candidate.name
        resolved = candidate.resolve()
        try:
            resolved.relative_to(self.base_dir)
        except ValueError as exc:
            raise ValueError("source_path deve estar dentro do diretorio CURATED") from exc
        if not resolved.is_file() or resolved.suffix.lower() != ".json":
            raise FileNotFoundError(f"Arquivo CURATED invalido: {resolved}")
        return resolved


class BatchProcessingService:
    """Execute durable startup investigations one item at a time."""

    def __init__(
        self,
        repository: BatchRepository,
        loader: CuratedStartupLoader | None = None,
        pipeline_runner: PipelineRunner | None = None,
    ) -> None:
        self.repository = repository
        self.loader = loader or CuratedStartupLoader()
        self.pipeline_runner = pipeline_runner or self._run_persistent_pipeline

    @classmethod
    def from_env(cls) -> "BatchProcessingService":
        return cls(BatchRepository.from_env())

    def create_batch(
        self,
        source_path: str | Path | None = None,
        options: BatchExecutionOptions | dict[str, Any] | None = None,
    ) -> UUID:
        validated = (
            options
            if isinstance(options, BatchExecutionOptions)
            else BatchExecutionOptions.model_validate(options or {})
        )
        path, startups = self.loader.load(source_path)
        selected = self.loader.select(startups, validated)
        batch_id = self.repository.create_batch(
            source_path=str(path),
            startups=selected,
            options=validated.model_dump(mode="json"),
        )
        LOGGER.info("batch_created", batch_id=str(batch_id), total_items=len(selected))
        return batch_id

    def run_batch(
        self,
        batch_id: UUID,
        resume: bool = False,
        worker_id: str | None = None,
    ) -> dict[str, Any]:
        batch = self.repository.get_batch(batch_id)
        if batch["status"] == "running" and not resume:
            raise ValueError("Lote ja esta em execucao")
        if batch["status"] in {"completed", "cancelled"} and not resume:
            raise ValueError(f"Lote com status {batch['status']} nao pode ser reiniciado")
        options = BatchExecutionOptions.model_validate(batch.get("options") or {})
        self.repository.recover_interrupted_items(batch_id)
        if resume:
            self.repository.requeue_retryable_items(batch_id, options.max_attempts)
        self.repository.start_batch(batch_id)

        stop_requested = False
        while not stop_requested:
            pending = self.repository.list_items(batch_id, statuses={"pending"})
            if not pending:
                requeued = self.repository.requeue_retryable_items(
                    batch_id,
                    options.max_attempts,
                )
                if not requeued:
                    break
                pending = self.repository.list_items(batch_id, statuses={"pending"})
            for item in pending:
                if self.repository.is_cancelled(batch_id):
                    stop_requested = True
                    break
                if worker_id:
                    self.repository.heartbeat(batch_id, worker_id)
                with web_usage_context(str(batch_id), item["startup_name"]):
                    failed = not self._process_item(item)
                self.repository.finalize_batch(batch_id)
                if worker_id:
                    self.repository.heartbeat(batch_id, worker_id)
                if failed and options.stop_on_error:
                    stop_requested = True
                    break
        self.repository.dead_letter_exhausted_items(batch_id, options.max_attempts)
        final = self.repository.finalize_batch(batch_id)
        LOGGER.info(
            "batch_finished",
            batch_id=str(batch_id),
            status=final["status"],
            processed=final["processed_items"],
            total=final["total_items"],
        )
        return final

    def queue_batch(
        self,
        batch_id: UUID,
        resume: bool = False,
        reprocess_partial: bool = False,
    ) -> dict[str, Any]:
        batch = self.repository.get_batch(batch_id)
        if batch["status"] == "running":
            raise ValueError("Lote em execucao nao pode ser reenfileirado")
        options = BatchExecutionOptions.model_validate(batch.get("options") or {})
        self.repository.recover_interrupted_items(batch_id)
        if resume:
            self.repository.requeue_retryable_items(batch_id, options.max_attempts)
        if reprocess_partial:
            self.repository.requeue_partial_items(batch_id)
        self.repository.queue_batch(batch_id)
        return self.repository.get_batch(batch_id)

    def _process_item(self, item: dict[str, Any]) -> bool:
        item_id = UUID(item["id"])
        self.repository.start_item(item_id)
        try:
            payload = _pipeline_payload(item["startup_payload"])
            payload["thread_id"] = str(item_id)
            result = self.pipeline_runner(payload)
            result_status = result.get("status", "falha")
            item_status = cast(BatchItemStatus, {
                "completo": "completed",
                "parcial": "partial",
            }.get(result_status, "failed"))
            run_id = _optional_uuid(result.get("pipeline_run_id"))
            error = _error_summary(result.get("errors", [])) if item_status != "completed" else None
            self.repository.finish_item(
                item_id,
                item_status,
                pipeline_run_id=run_id,
                result_summary={
                    "status": result_status,
                    "classificacao": result.get("classificacao"),
                    "nivel_maturidade": result.get("nivel_maturidade"),
                    "indice_impacto": (result.get("impacto_estimado") or {}).get(
                        "indice_impacto_agregado"
                    ),
                    "briefing_disponivel": bool(result.get("briefing_markdown")),
                },
                error=error,
            )
            return item_status != "failed"
        except Exception as exc:
            self.repository.finish_item(item_id, "failed", error=str(exc)[:2000])
            LOGGER.error(
                "batch_item_failed",
                item_id=str(item_id),
                startup=item["startup_name"],
                error=str(exc),
            )
            return False

    def _run_persistent_pipeline(self, payload: dict[str, Any]) -> dict[str, Any]:
        return run_pipeline_with_persistence(
            payload,
            persistence=self.repository.persistence,
            use_cache=True,
        )


def _pipeline_payload(startup: dict[str, Any]) -> dict[str, Any]:
    return {
        "external_id": startup["startup_id"],
        "startup_name": startup["nome"],
        "site_oficial": startup.get("site"),
        "categoria": startup.get("categoria"),
        "descricao_curta": startup.get("descricao_curta"),
        "cidade": startup.get("cidade"),
        "estado": startup.get("estado"),
        "pais": startup.get("pais") or "Brasil",
        "contexto": (
            "Identificar evidencias de uso de IA, maturidade tecnica, impacto potencial "
            "e aderencia a stack NVIDIA."
        ),
    }


def _optional_uuid(value: Any) -> UUID | None:
    try:
        return UUID(str(value)) if value else None
    except ValueError:
        return None


def _error_summary(errors: list[Any]) -> str | None:
    if not errors:
        return None
    return " | ".join(str(error) for error in errors)[:2000]
