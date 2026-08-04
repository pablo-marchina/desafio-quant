from __future__ import annotations

from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import UUID

from app.persistence.batch_repository import BatchRepository, TERMINAL_ITEM_STATUSES


class BatchAcceptanceReport:
    def __init__(self, repository: BatchRepository) -> None:
        self.repository = repository
        self.db = repository.persistence.db

    def generate(
        self,
        batch_id: UUID,
        output_path: Path,
        allow_incomplete: bool = False,
    ) -> Path:
        batch = self.repository.get_batch(batch_id)
        if not allow_incomplete and batch["status"] not in {"completed", "partial", "failed"}:
            raise ValueError("O lote ainda nao esta em estado terminal")
        items = self.repository.list_items(batch_id)
        runs = self._runs(items)
        usage = (
            self.db.table("external_api_usage")
            .select("provider,units,estimated_cost_usd,cache_hit,success")
            .eq("batch_run_id", str(batch_id))
            .execute()
            .data
            or []
        )
        markdown = render_batch_report(batch, items, runs, usage)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(markdown, encoding="utf-8")
        return output_path

    def _runs(self, items: list[dict[str, Any]]) -> list[dict[str, Any]]:
        runs = []
        for item in items:
            run_id = item.get("pipeline_run_id")
            if not run_id:
                continue
            response = (
                self.db.table("pipeline_runs")
                .select("id,status,duration_ms,warnings,source_errors,errors")
                .eq("id", run_id)
                .limit(1)
                .execute()
            )
            if response.data:
                runs.append(response.data[0])
        return runs


def render_batch_report(
    batch: dict[str, Any],
    items: list[dict[str, Any]],
    runs: list[dict[str, Any]],
    usage: list[dict[str, Any]],
) -> str:
    item_statuses = Counter(item.get("status", "unknown") for item in items)
    classifications = Counter(
        (item.get("result_summary") or {}).get("classificacao") or "unknown"
        for item in items
        if item.get("status") in TERMINAL_ITEM_STATUSES
    )
    terminal = [item for item in items if item.get("status") in TERMINAL_ITEM_STATUSES]
    traceable = [
        item for item in terminal if item.get("pipeline_run_id") or item.get("last_error")
    ]
    partial_count = item_statuses.get("partial", 0)
    partial_ratio = partial_count / len(terminal) if terminal else 0.0
    duration_seconds = _duration_seconds(batch)
    warning_count = sum(len(run.get("warnings") or []) for run in runs)
    source_error_count = sum(len(run.get("source_errors") or []) for run in runs)
    critical_error_count = sum(len(run.get("errors") or []) for run in runs)
    total_units = sum(int(row.get("units") or 0) for row in usage)
    cache_hits = sum(1 for row in usage if row.get("cache_hit"))
    api_failures = sum(1 for row in usage if not row.get("success") and row.get("units"))
    estimated_cost = sum(float(row.get("estimated_cost_usd") or 0) for row in usage)
    is_terminal = batch.get("status") in {"completed", "partial", "failed"}
    gates = {
        "50/50 em estado terminal": len(terminal) == int(batch.get("total_items") or 0),
        "100% dos terminais rastreaveis": len(traceable) == len(terminal),
        "Menos de 10% partial": bool(terminal) and partial_ratio < 0.10,
        "Revisao humana da amostra": False,
    }
    lines = [
        f"# Relatorio de Aceitacao do Lote {batch['id']}",
        "",
        f"**Estado do relatorio:** {'FINAL' if is_terminal else 'INTERMEDIARIO'}",
        f"**Status do lote:** {batch.get('status')}",
        f"**Gerado em:** {datetime.now(UTC).isoformat()}",
        f"**Duracao observada:** {duration_seconds:.1f} segundos",
        "",
        "## Progresso",
        "",
        f"- Total: {batch.get('total_items', len(items))}",
        f"- Terminais: {len(terminal)}",
    ]
    lines.extend(f"- {status}: {count}" for status, count in sorted(item_statuses.items()))
    lines.extend(["", "## Classificacoes"])
    lines.extend(f"- {label}: {count}" for label, count in sorted(classifications.items()))
    lines.extend(
        [
            "",
            "## Qualidade e Rastreabilidade",
            "",
            f"- Runs persistidos: {len(runs)}",
            f"- Warnings: {warning_count}",
            f"- Erros de fonte: {source_error_count}",
            f"- Erros criticos: {critical_error_count}",
            f"- Taxa partial: {partial_ratio:.1%}",
            "",
            "## APIs Externas",
            "",
            f"- Unidades cobraveis registradas: {total_units}",
            f"- Cache hits: {cache_hits}",
            f"- Falhas: {api_failures}",
            f"- Custo estimado configurado: USD {estimated_cost:.4f}",
            "",
            "## Gates",
            "",
        ]
    )
    lines.extend(f"- [{'x' if passed else ' '}] {name}" for name, passed in gates.items())
    pending = ["A concordancia e a utilidade dependem do preenchimento humano da amostra."]
    if partial_count:
        pending.append("Casos partial devem ser revisados por causa antes da aprovacao final.")
    if api_failures:
        pending.append(
            "APIs externas registraram falhas; confirmar creditos e credenciais antes de producao."
        )
    lines.extend(["", "## Pendencias", ""])
    lines.extend(f"- {item}" for item in pending)
    return "\n".join(lines) + "\n"


def _duration_seconds(batch: dict[str, Any]) -> float:
    started = _parse_datetime(batch.get("started_at") or batch.get("created_at"))
    finished = _parse_datetime(batch.get("finished_at")) or datetime.now(UTC)
    return max((finished - started).total_seconds(), 0.0) if started else 0.0


def _parse_datetime(value: Any) -> datetime | None:
    if not value:
        return None
    return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
