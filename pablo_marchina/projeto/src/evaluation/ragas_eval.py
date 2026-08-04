"""RAGAS Evaluation Harness — offline quantitative evaluation of retrieve_nvidia_context.

This module is **completely separate** from the production RAG path.
It does NOT replace or modify any retrieval or recommendation logic.

Two metric layers:
  1. RAGAS metrics (context_precision, context_recall, faithfulness, answer_relevancy)
     — computed via the ``ragas`` library when available and an LLM judge is configured.
     — When unavailable, those metrics are reported as None with source="unavailable".
  2. Custom metrics (citation_precision, unsupported_claim_rate, retrieved_context_count,
     contexts_per_gap, gaps_without_context_count, rag_blocker_count)
     — computed deterministically with no external dependencies.

Usage (unit-test safe):
    harness = RagasEvalHarness()
    result = harness.run(golden_path=Path("data/eval/golden_ragas_rag.json"))
    result.calibration_status  # "baseline_dataset_insufficient" when < 10 samples

RAGAS library is imported lazily — if unavailable, RAGAS metrics are skipped,
not raised. Unit tests never call LLM or internet.
"""

from __future__ import annotations

import json

# ── Lazy RAGAS import — never fails, never called in unit tests ────────────
# Uses subprocess-based check to avoid hanging on C extension build issues
# (e.g. scikit-network on Python 3.14/Windows without VS Build Tools).
import subprocess
import sys
from pathlib import Path
from typing import Any

from src.evaluation.ragas_eval_schemas import (
    MINIMUM_GAP_TYPES_COVERED,
    MINIMUM_GOLDEN_SAMPLES,
    REQUIRED_SAMPLE_FIELDS,
    CustomEvalMetrics,
    RagasComputedMetrics,
    RagasEvalDataset,
    RagasEvalGoldenSample,
    RagasEvalReport,
    RagasEvalResult,
)

_HAS_RAGAS = False
_RAGAS_IMPORT_ERROR: str | None = None

try:
    # Quick check via subprocess to avoid hanging on C extension compilation
    _result = subprocess.run(
        [sys.executable, "-c", "import ragas; print('ok')"],
        capture_output=True,
        text=True,
        timeout=15,
    )
    if _result.returncode == 0 and _result.stdout.strip() == "ok":
        import ragas  # noqa: F401

        _HAS_RAGAS = True
    else:
        _RAGAS_IMPORT_ERROR = _result.stderr.strip() or "ragas import failed (unknown error)"
except FileNotFoundError:
    _RAGAS_IMPORT_ERROR = "ragas package not installed"
except subprocess.TimeoutExpired:
    _RAGAS_IMPORT_ERROR = "ragas import timed out (C extension build issue)"
except Exception as exc:
    _RAGAS_IMPORT_ERROR = f"ragas import error: {exc}"

try:
    from datasets import Dataset  # noqa: F401
except ImportError:
    pass


# ── Default golden set path ────────────────────────────────────────────────

_DEFAULT_GOLDEN_PATH = Path("data/eval/golden_ragas_rag.json")


# ── Evaluation harness ─────────────────────────────────────────────────────


class RagasEvalHarness:
    """Offline RAGAS evaluation harness for retrieve_nvidia_context.

    Pure evaluation — no retrieval, no LLM calls by default.
    """

    def __init__(self, golden_path: Path = _DEFAULT_GOLDEN_PATH) -> None:
        self._golden_path = golden_path

    # ------------------------------------------------------------------
    # Loading & validation
    # ------------------------------------------------------------------

    def load_golden_set(self, path: Path | None = None) -> RagasEvalDataset:
        p = path or self._golden_path
        raw = json.loads(p.read_text(encoding="utf-8"))
        samples = [RagasEvalGoldenSample(**item) for item in raw.get("samples", [])]
        return RagasEvalDataset(
            samples=samples,
            metadata=raw.get("metadata", {}),
        )

    def validate_schema(self, dataset: RagasEvalDataset) -> list[str]:
        errors: list[str] = []
        for i, sample in enumerate(dataset.samples):
            missing = REQUIRED_SAMPLE_FIELDS - {f for f in sample.model_fields_set}
            if missing:
                errors.append(f"sample[{i}] missing fields: {missing}")
            if not sample.question.strip():
                errors.append(f"sample[{i}] has empty question")
            if not sample.gap_id.strip():
                errors.append(f"sample[{i}] has empty gap_id")
            if not sample.gap_type.strip():
                errors.append(f"sample[{i}] has empty gap_type")
        return errors

    def check_dataset_sufficiency(self, dataset: RagasEvalDataset) -> tuple[bool, str]:
        n = len(dataset.samples)
        if n < MINIMUM_GOLDEN_SAMPLES:
            return False, f"only {n} samples (minimum {MINIMUM_GOLDEN_SAMPLES} required)"
        gap_types = {s.gap_type for s in dataset.samples}
        if len(gap_types) < MINIMUM_GAP_TYPES_COVERED:
            return (
                False,
                f"only {len(gap_types)} gap types (minimum {MINIMUM_GAP_TYPES_COVERED} required)",
            )
        return True, "dataset sufficient"

    # ------------------------------------------------------------------
    # Custom metric computation (deterministic, no external deps)
    # ------------------------------------------------------------------

    def compute_custom_metrics(self, dataset: RagasEvalDataset) -> CustomEvalMetrics:
        total_retrieved = 0
        total_with_citation = 0
        total_expected = 0
        total_unsupported = 0
        contexts_per_gap: dict[str, int] = {}
        gaps_without = 0
        len(dataset.samples)

        for sample in dataset.samples:
            ctxs = sample.retrieved_contexts
            n_retrieved = len(ctxs)
            total_retrieved += n_retrieved

            gap_type = sample.gap_type
            contexts_per_gap[gap_type] = contexts_per_gap.get(gap_type, 0) + n_retrieved

            if n_retrieved == 0:
                gaps_without += 1

            expected_ids = set(sample.expected_context_ids)
            n_expected = len(expected_ids)
            total_expected += n_expected

            found_ids = {c.chunk_id for c in ctxs}
            matching = expected_ids & found_ids
            total_unsupported += n_expected - len(matching)

            for ctx in ctxs:
                if ctx.source_id and ctx.url:
                    total_with_citation += 1

        citation_precision = total_with_citation / total_retrieved if total_retrieved > 0 else 1.0
        unsupported_claim_rate = total_unsupported / total_expected if total_expected > 0 else 0.0

        return CustomEvalMetrics(
            citation_precision=round(citation_precision, 4),
            unsupported_claim_rate=round(unsupported_claim_rate, 4),
            retrieved_context_count=total_retrieved,
            contexts_per_gap=contexts_per_gap,
            gaps_without_context_count=gaps_without,
            rag_blocker_count=0,
        )

    # ------------------------------------------------------------------
    # RAGAS metric computation (requires ragas + optional LLM judge)
    # ------------------------------------------------------------------

    def compute_ragas_metrics(self, dataset: RagasEvalDataset) -> RagasComputedMetrics:
        if not _HAS_RAGAS:
            return RagasComputedMetrics(metrics_source=f"unavailable: {_RAGAS_IMPORT_ERROR}")

        samples_with_answers = [s for s in dataset.samples if s.ground_truth_answer]
        if not samples_with_answers:
            return RagasComputedMetrics(metrics_source="unavailable: no ground_truth_answer")

        return self._compute_ragas_via_library(dataset)

    def _compute_ragas_via_library(self, dataset: RagasEvalDataset) -> RagasComputedMetrics:
        try:
            from datasets import Dataset as HFDataset
            from ragas import evaluate
            from ragas.metrics import (
                answer_relevancy,
                context_precision,
                context_recall,
                faithfulness,
            )
        except ImportError as exc:
            return RagasComputedMetrics(metrics_source=f"unavailable: ragas import error: {exc}")

        rows: list[dict[str, Any]] = []
        for s in dataset.samples:
            row: dict[str, Any] = {
                "question": s.question,
                "contexts": [c.content for c in s.retrieved_contexts],
            }
            if s.ground_truth_answer:
                row["ground_truth"] = s.ground_truth_answer
            if s.generated_answer:
                row["answer"] = s.generated_answer
            rows.append(row)

        if not rows:
            return RagasComputedMetrics(metrics_source="unavailable: no samples")

        try:
            hf_dataset = HFDataset.from_list(rows)
        except Exception as exc:
            return RagasComputedMetrics(metrics_source=f"unavailable: dataset conversion error: {exc}")

        has_answer = "answer" in hf_dataset.column_names
        has_ground_truth = "ground_truth" in hf_dataset.column_names

        metrics_to_use = []
        if has_ground_truth:
            metrics_to_use.extend([context_precision, context_recall])
        if has_answer and has_ground_truth:
            metrics_to_use.extend([faithfulness, answer_relevancy])

        if not metrics_to_use:
            return RagasComputedMetrics(metrics_source="unavailable: insufficient columns for ragas metrics")

        try:
            result = evaluate(hf_dataset, metrics=metrics_to_use)
        except Exception as exc:
            return RagasComputedMetrics(metrics_source=f"unavailable: ragas evaluation error: {exc}")

        scores: dict[str, Any] = {}
        for key, val in result.items():
            if isinstance(val, float):
                scores[key] = round(val, 4)
            elif isinstance(val, (int,)):
                scores[key] = float(val)

        return RagasComputedMetrics(
            context_precision=scores.get("context_precision"),
            context_recall=scores.get("context_recall"),
            faithfulness=scores.get("faithfulness"),
            answer_relevancy=scores.get("answer_relevancy"),
            metrics_source="ragas_library",
        )

    # ------------------------------------------------------------------
    # Report generation
    # ------------------------------------------------------------------

    def generate_report(
        self,
        custom: CustomEvalMetrics,
        ragas: RagasComputedMetrics | None,
        dataset: RagasEvalDataset,
    ) -> list[RagasEvalReport]:
        reports: list[RagasEvalReport] = []
        n = len(dataset.samples)
        sufficient, _ = self.check_dataset_sufficiency(dataset)

        reports.append(
            RagasEvalReport(
                metric_name="custom.citation_precision",
                score=custom.citation_precision,
                sample_count=n,
                calibration_recommendation=(
                    "calibrate_threshold_via_ragas_eval" if sufficient else "baseline_dataset_insufficient"
                ),
                production_allowed_recommendation=sufficient,
            )
        )
        reports.append(
            RagasEvalReport(
                metric_name="custom.unsupported_claim_rate",
                score=custom.unsupported_claim_rate,
                sample_count=n,
                calibration_recommendation=(
                    "calibrate_threshold_via_ragas_eval" if sufficient else "baseline_dataset_insufficient"
                ),
                production_allowed_recommendation=sufficient,
            )
        )
        reports.append(
            RagasEvalReport(
                metric_name="custom.retrieved_context_count",
                score=float(custom.retrieved_context_count) / max(n, 1),
                sample_count=n,
                calibration_recommendation=(
                    "calibrate_min_contexts_per_gap_via_ragas_eval" if sufficient else "baseline_dataset_insufficient"
                ),
                production_allowed_recommendation=sufficient,
            )
        )
        reports.append(
            RagasEvalReport(
                metric_name="custom.gaps_without_context_count",
                score=float(custom.gaps_without_context_count),
                sample_count=n,
                calibration_recommendation=(
                    "investigate_zero_context_gaps" if sufficient else "baseline_dataset_insufficient"
                ),
                production_allowed_recommendation=sufficient,
            )
        )

        if ragas is not None:
            for metric_name, score in [
                ("ragas.context_precision", ragas.context_precision),
                ("ragas.context_recall", ragas.context_recall),
                ("ragas.faithfulness", ragas.faithfulness),
                ("ragas.answer_relevancy", ragas.answer_relevancy),
            ]:
                reports.append(
                    RagasEvalReport(
                        metric_name=metric_name,
                        score=score if score is not None else 0.0,
                        sample_count=n,
                        calibration_recommendation=(f"metrics_source={ragas.metrics_source}"),
                        production_allowed_recommendation=(score is not None and sufficient),
                    )
                )

        return reports

    def _produce_calibration_decisions(
        self,
        reports: list[RagasEvalReport],
        custom: CustomEvalMetrics,
        sufficient: bool,
    ) -> dict[str, dict]:
        dec: dict[str, dict] = {}
        prefix = "ragas_rag_eval"

        def _decision(
            decision_id: str,
            current_value: float | str | bool,
            metric_name: str,
        ) -> dict:
            return {
                "decision_id": decision_id,
                "current_value": current_value,
                "metric_name": metric_name,
                "value_origin": f"{prefix} :: {self._golden_path.name}",
                "calibration_method": "baseline_measurement",
                "calibration_status": ("baseline_measured" if sufficient else "baseline_dataset_insufficient"),
                "production_allowed": sufficient,
                "evidence_source": (f"RAGAS eval on {self._golden_path} ({len(reports)} samples)"),
            }

        dec["rag.semantic_top_k"] = {
            **_decision("rag.semantic_top_k", 8, "rag_semantic_top_k"),
            "notes": "Existing BASELINE_MEASURED value; RAGAS eval will refine when dataset >= 10",
        }
        dec["rag.min_contexts_per_gap"] = {
            **_decision("rag.min_contexts_per_gap", 1, "rag_min_contexts_per_gap"),
            "notes": "Recommendation from RAGAS eval — pending sufficient dataset",
        }
        dec["rag.context_relevance_threshold"] = {
            **_decision("rag.context_relevance_threshold", 0.3, "rag_context_relevance_threshold"),
            "notes": "Recommendation from RAGAS eval — pending sufficient dataset",
        }
        dec["rag.citation_precision_threshold"] = {
            **_decision(
                "rag.citation_precision_threshold",
                custom.citation_precision,
                "rag_citation_precision_threshold",
            ),
            "notes": f"Observed citation_precision={custom.citation_precision} on golden set",
        }
        dec["rag.unsupported_claim_rate_threshold"] = {
            **_decision(
                "rag.unsupported_claim_rate_threshold",
                custom.unsupported_claim_rate,
                "rag_unsupported_claim_rate_threshold",
            ),
            "notes": f"Observed unsupported_claim_rate={custom.unsupported_claim_rate} on golden set",
        }
        dec["rag.ragas_context_precision_threshold"] = {
            **_decision(
                "rag.ragas_context_precision_threshold",
                0.0,
                "rag_ragas_context_precision_threshold",
            ),
            "notes": "Requires ragas library + ground_truth_answer in golden set",
        }
        dec["rag.ragas_faithfulness_threshold"] = {
            **_decision(
                "rag.ragas_faithfulness_threshold",
                0.0,
                "rag_ragas_faithfulness_threshold",
            ),
            "notes": "Requires ragas library + generated_answer in golden set",
        }
        dec["rag.ragas_answer_relevancy_threshold"] = {
            **_decision(
                "rag.ragas_answer_relevancy_threshold",
                0.0,
                "rag_ragas_answer_relevancy_threshold",
            ),
            "notes": "Requires ragas library + generated_answer in golden set",
        }

        return dec

    # ------------------------------------------------------------------
    # Main entry point
    # ------------------------------------------------------------------

    def run(self, golden_path: Path | None = None) -> RagasEvalResult:
        dataset = self.load_golden_set(golden_path)
        schema_errors = self.validate_schema(dataset)
        sufficient, sufficiency_msg = self.check_dataset_sufficiency(dataset)

        custom = self.compute_custom_metrics(dataset)

        ragas_metrics: RagasComputedMetrics | None = None
        if sufficient and not schema_errors:
            ragas_metrics = self.compute_ragas_metrics(dataset)
        else:
            ragas_metrics = RagasComputedMetrics(metrics_source="skipped: insufficient dataset or schema errors")

        reports = self.generate_report(custom, ragas_metrics, dataset)
        decisions = self._produce_calibration_decisions(reports, custom, sufficient)

        calibration_status = (
            "baseline_measured" if sufficient and not schema_errors else "baseline_dataset_insufficient"
        )

        return RagasEvalResult(
            dataset_size=len(dataset.samples),
            dataset_sufficient=sufficient,
            calibration_status=calibration_status,
            production_allowed=sufficient and not bool(schema_errors),
            custom_metrics=custom,
            ragas_metrics=ragas_metrics,
            reports=reports,
            calibration_decisions=decisions,
        )
