"""Testes do GPU Graduation Engine — matriz de benchmark + ROI + nó (F6.9–F6.11)."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from packages.agents.nodes import gpu_benchmark
from packages.benchmark.matrix import (
    BenchCell,
    BenchMatrix,
    BenchSide,
    load_matrix,
    roi_for,
    roi_from_cell,
)
from packages.config import get_settings
from packages.schemas import Evidence, GraphState, Recommendation
from packages.schemas.enums import Complexity, Priority


def _cell(tier: str = "medium") -> BenchCell:
    return BenchCell(
        tier=tier,
        model_class="7-8B",
        baseline=BenchSide(
            name="API externa",
            throughput_tok_s=50.0,
            p95_ms=2500.0,
            cost_per_1m_usd=0.50,
            source="ilustrativo",
        ),
        optimized=BenchSide(
            name="NIM (TensorRT-LLM + Triton)",
            throughput_tok_s=150.0,
            p95_ms=1000.0,
            cost_per_1m_usd=0.20,
            source="ilustrativo",
        ),
    )


def _rec(tech: str) -> Recommendation:
    ev = [
        Evidence(
            url="https://x.test/a",
            snippet="trecho",
            fetched_at=datetime(2026, 1, 1, tzinfo=UTC),
        )
    ]
    return Recommendation(
        tech=tech,
        justificativa_tecnica="jt",
        justificativa_negocio="jn",
        prioridade=Priority.ALTA,
        complexidade=Complexity.MEDIA,
        proxima_acao="acao",
        evidencia_gap=ev,
        evidencia_nvidia=ev,
    )


def test_roi_from_cell_math() -> None:
    roi = roi_from_cell(_cell())
    assert roi.throughput_speedup == 3.0  # 150 / 50
    assert roi.latency_p95_delta_pct == -60.0  # (1000-2500)/2500
    assert roi.cost_delta_pct == -60.0  # (0.20-0.50)/0.50
    assert roi.baseline == "API externa"
    assert roi.optimized.startswith("NIM")
    assert roi.is_live_run is False


def test_roi_from_cell_live_flag_propagates() -> None:
    cell = _cell()
    cell.optimized.is_live_run = True
    assert roi_from_cell(cell).is_live_run is True


def test_roi_for_only_inference_techs() -> None:
    matrix = BenchMatrix(cells=[_cell()])
    assert roi_for("NIM", matrix=matrix) is not None
    assert roi_for("TensorRT-LLM", matrix=matrix) is not None
    # Tech fora da familia de inferencia nao recebe ROI.
    assert roi_for("NeMo Guardrails", matrix=matrix) is None


def test_roi_for_falls_back_to_first_cell_when_tier_absent() -> None:
    matrix = BenchMatrix(cells=[_cell("small")])
    roi = roi_for("NIM", tier="inexistente", matrix=matrix)
    assert roi is not None  # cai na primeira celula disponivel


def test_roi_for_no_matrix_returns_none() -> None:
    assert roi_for("NIM", matrix=BenchMatrix(cells=[])) is None


def test_shipped_matrix_loads_and_has_medium() -> None:
    matrix = load_matrix()
    assert matrix is not None
    assert matrix.cell("medium") is not None
    # A matriz versionada e ilustrativa (nao medida) ate o bench rodar.
    assert matrix.cell("medium").optimized.is_live_run is False


def test_node_noop_when_flag_off() -> None:
    get_settings.cache_clear()
    state = GraphState(run_id="r1", query="q", recommendations=[_rec("NIM")])
    assert gpu_benchmark(state) == {}  # flag off por padrao -> espinha verde


def test_node_attaches_roi_when_enabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GPU_BENCHMARK_USE_MATRIX", "true")
    get_settings.cache_clear()
    try:
        state = GraphState(run_id="r1", query="q", recommendations=[_rec("NIM"), _rec("NeMo")])
        out = gpu_benchmark(state)
        recs = out["recommendations"]
        nim = next(r for r in recs if r.tech == "NIM")
        nemo = next(r for r in recs if r.tech == "NeMo")
        assert nim.roi is not None
        assert nim.roi.throughput_speedup is not None
        # Evidencia dos dois lados preservada (model_copy nao apaga).
        assert nim.evidencia_gap and nim.evidencia_nvidia
        # Tech fora da familia de inferencia segue sem ROI.
        assert nemo.roi is None
        assert out["trace"]["gpu_benchmark"]["roi_attached"] == 1
    finally:
        get_settings.cache_clear()
