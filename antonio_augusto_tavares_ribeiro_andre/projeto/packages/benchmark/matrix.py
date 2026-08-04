"""GPU Graduation Engine — matriz de benchmark + ROI (F6.9–F6.11).

Quantifica o ganho de **graduar a inferência** da API externa (pay-per-token, infra compartilhada)
para a stack NVIDIA otimizada — **NIM = TensorRT-LLM + Triton empacotados**. A matriz
(`data/benchmark/matrix.json`) guarda, por célula (tier de workload), o throughput/latência/custo do
lado **baseline** (API externa) e do lado **otimizado** (NIM). `roi_for` casa uma recomendação de
graduação (NIM/TensorRT-LLM/Triton) à célula e deriva o `ROIEstimate` (F0.5) que o nó
`gpu_benchmark` anexa às recs; o downstream (persist → API → UI / briefing) já consome.

**Provenância honesta (princípio de evidência rastreável):** cada lado carrega `source` e
`is_live_run`. As células versionadas no repo são **ilustrativas** (rótulo explícito) até serem
substituídas por medição real — `scripts/bench_nim.py` mede o **NIM hospedado** (build.nvidia.com,
créditos grátis) e grava o lado otimizado com `is_live_run=true`. Nada aparece como medido enquanto
não for; sem matriz, o nó é no-op e a rec degrada graciosa (sem ROI), como o resto da espinha verde.
"""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from packages.schemas.recommendation import ROIEstimate

#: Família de inferência (graduação API→stack) que recebe ROI — espelha o gap de Technical
#: Optimization que as regras F4.1 disparam. Outras techs (NeMo, Riva, etc.) não levam ROI.
INFERENCE_TECHS: frozenset[str] = frozenset({"NIM", "TensorRT-LLM", "Triton"})

#: Matriz versionada no repo. `packages/benchmark/matrix.py` → parents[2] = raiz do repo.
DEFAULT_MATRIX_PATH = Path(__file__).resolve().parents[2] / "data" / "benchmark" / "matrix.json"

#: Tier usado quando o perfil não indica volume (não temos tráfego real por startup, F6.11).
DEFAULT_TIER = "medium"


class BenchSide(BaseModel):
    """Um lado da comparação numa célula: baseline (API) ou otimizado (NIM)."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(description="Rótulo do lado (ex.: 'API externa' / 'NIM').")
    throughput_tok_s: float = Field(gt=0, description="Tokens/s de saída sob carga.")
    p95_ms: float = Field(gt=0, description="Latência p95 por requisição (ms).")
    cost_per_1m_usd: float = Field(ge=0, description="Custo por 1M tokens de saída (US$).")
    source: str = Field(description="Origem do número (referência citada ou medição).")
    is_live_run: bool = Field(default=False, description="True se medido ao vivo.")


class BenchCell(BaseModel):
    """Uma célula da matriz: um tier de workload com baseline × otimizado."""

    model_config = ConfigDict(extra="forbid")

    tier: str = Field(description="Tier de workload (ex.: small/medium/large).")
    model_class: str = Field(description="Classe de modelo da célula (ex.: '8B (Llama-3.1-8B)').")
    baseline: BenchSide
    optimized: BenchSide


class BenchMatrix(BaseModel):
    """Matriz de benchmark pré-computada (F6.9): conjunto de células por tier."""

    model_config = ConfigDict(extra="forbid")

    schema_version: int = 1
    notes: str = ""
    cells: list[BenchCell] = Field(default_factory=list)

    def cell(self, tier: str) -> BenchCell | None:
        """Célula do tier pedido; `None` se não existir (o caller cai no primeiro disponível)."""
        for c in self.cells:
            if c.tier == tier:
                return c
        return None


def _pct_delta(optimized: float, baseline: float) -> float:
    """Variação percentual otimizado vs baseline (negativo = melhora). Arredonda a 1 casa."""
    return round((optimized - baseline) / baseline * 100.0, 1) if baseline else 0.0


def roi_from_cell(cell: BenchCell) -> ROIEstimate:
    """Deriva o `ROIEstimate` (F0.5) de uma célula: speedup de throughput, delta de p95 e de custo.

    Convenção de sinal do contrato: delta **negativo = melhora** (menos latência / menos custo). O
    `is_live_run` é verdadeiro se **qualquer** lado foi medido ao vivo; o `benchmark_source` carrega
    o tier/classe + a origem do lado otimizado (a UI/briefing distinguem matriz de medição).
    """
    b, o = cell.baseline, cell.optimized
    return ROIEstimate(
        throughput_speedup=round(o.throughput_tok_s / b.throughput_tok_s, 2),
        latency_p95_delta_pct=_pct_delta(o.p95_ms, b.p95_ms),
        cost_delta_pct=_pct_delta(o.cost_per_1m_usd, b.cost_per_1m_usd),
        baseline=b.name,
        optimized=o.name,
        benchmark_source=f"{cell.tier}/{cell.model_class} — {o.source}",
        is_live_run=b.is_live_run or o.is_live_run,
    )


def load_matrix(path: str | Path | None = None) -> BenchMatrix | None:
    """Carrega a matriz do disco; `None` se não existir ou estiver inválida (degrada limpo).

    Sem leitura cacheada de propósito: o `scripts/bench_nim.py` reescreve o arquivo entre runs e o
    nó roda em processo fresco — ler a cada chamada evita estado velho sem custo relevante.
    """
    p = Path(path) if path is not None else DEFAULT_MATRIX_PATH
    if not p.exists():
        return None
    try:
        return BenchMatrix.model_validate_json(p.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001 — matriz ausente/corrompida → sem ROI (degrada gracioso)
        return None


def roi_for(
    tech: str, *, tier: str = DEFAULT_TIER, matrix: BenchMatrix | None = None
) -> ROIEstimate | None:
    """ROI de uma recomendação: `None` fora da família de inferência ou sem matriz/célula.

    Só techs de graduação (`INFERENCE_TECHS`) levam ROI — uma recomendação de NeMo/Riva não tem
    "graduação de inferência" a quantificar. `matrix` injetável (testes); por default lê do disco.
    """
    if tech not in INFERENCE_TECHS:
        return None
    mat = matrix if matrix is not None else load_matrix()
    if mat is None:
        return None
    cell = mat.cell(tier) or (mat.cells[0] if mat.cells else None)
    if cell is None:
        return None
    return roi_from_cell(cell)


__all__ = [
    "INFERENCE_TECHS",
    "DEFAULT_MATRIX_PATH",
    "DEFAULT_TIER",
    "BenchSide",
    "BenchCell",
    "BenchMatrix",
    "roi_from_cell",
    "load_matrix",
    "roi_for",
]
