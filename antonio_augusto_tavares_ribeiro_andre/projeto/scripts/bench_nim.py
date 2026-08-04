"""Mede o NIM hospedado (build.nvidia.com) e grava o lado otimizado da matriz (F6.8/F6.9).

O lado "otimizado" da matriz de benchmark e o **NIM** — TensorRT-LLM + Triton empacotados pela
NVIDIA. Em vez de exigir um self-host pesado (inviavel numa GPU de 4 GB), este script mede o **NIM
hospedado** no catalogo build.nvidia.com (creditos gratis, GPU de datacenter) — exatamente o alvo de
graduacao que o TAPI recomenda. Mede throughput (tokens/s) e latencia p50/p95 sobre N requisicoes e
grava a celula `optimized` do tier escolhido em `data/benchmark/matrix.json` com `is_live_run=true`.

Usa o **mesmo cliente do pipeline** (`packages.agents.llm.get_chat` → `ChatNVIDIA`): o NIM hospedado
responde via fluxo 202+poll que so o cliente langchain-nvidia trata (um POST cru trava). Reusar o
cliente e mais fiel e dispensa formato HTTP a mao.

Uso:
    python scripts/bench_nim.py --tier medium                 # Nano-8B (perfil fast = classe 8B)
    python scripts/bench_nim.py --tier large --profile reason # Super-49B
    python scripts/bench_nim.py --tier medium --cost-per-1m 0.18

Precisa de `NVIDIA_API_KEY` no ambiente/.env. O **custo** nao e medivel num endpoint hospedado
gratis: passe `--cost-per-1m` (estimativa de $/1M self-hosted) ou deixe o valor atual. So o que este
script roda recebe `is_live_run=true`.
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from langchain_core.messages import HumanMessage  # noqa: E402

from packages.agents.llm import get_chat, run_with_timeout  # noqa: E402
from packages.benchmark.matrix import DEFAULT_MATRIX_PATH, BenchMatrix  # noqa: E402
from packages.config import get_settings  # noqa: E402

DEFAULT_PROMPT = (
    "Explique, em um paragrafo tecnico, por que servir um LLM com TensorRT-LLM e Triton "
    "tende a aumentar o throughput e reduzir a latencia p95 frente a uma API generica."
)
PER_CALL_TIMEOUT = 180.0


def _percentile(values: list[float], pct: float) -> float:
    """Percentil simples (interpolacao por indice) sobre uma amostra pequena."""
    if not values:
        return 0.0
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    k = (len(ordered) - 1) * pct
    lo = int(k)
    hi = min(lo + 1, len(ordered) - 1)
    return ordered[lo] + (ordered[hi] - ordered[lo]) * (k - lo)


def _one_call(chat, prompt: str) -> tuple[float, int]:
    """Uma chamada `.invoke`: devolve (latencia_s, output_tokens). Teto de tempo p/ nao pendurar."""
    start = time.perf_counter()
    msg = run_with_timeout(
        lambda: chat.invoke([HumanMessage(content=prompt)]), seconds=PER_CALL_TIMEOUT
    )
    elapsed = time.perf_counter() - start
    usage = getattr(msg, "usage_metadata", None) or {}
    return elapsed, int(usage.get("output_tokens", 0) or 0)


def _parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Mede o NIM hospedado e grava a matriz (F6).")
    ap.add_argument("--tier", default="medium", help="Tier a atualizar (small/medium/large).")
    ap.add_argument(
        "--profile", default="fast", choices=["fast", "reason"], help="Nano ou Super."
    )
    ap.add_argument("--model", default=None, help="Modelo NIM explicito (sobrepoe o perfil).")
    ap.add_argument("--n", type=int, default=6, help="Requisicoes medidas (alem de 1 warmup).")
    ap.add_argument("--max-tokens", type=int, default=256, help="Tokens de saida por requisicao.")
    ap.add_argument("--cost-per-1m", type=float, default=None, help="$/1M tokens self-hosted.")
    ap.add_argument(
        "--matrix-path", default=str(DEFAULT_MATRIX_PATH), help="Caminho do matrix.json."
    )
    return ap.parse_args()


def _build_chat(args: argparse.Namespace, settings) -> tuple[object, str]:
    """Cliente de medicao + label do modelo. `--model` constroi direto; senao usa o perfil."""
    if args.model:
        from langchain_nvidia_ai_endpoints import ChatNVIDIA

        kwargs: dict = {"model": args.model, "temperature": 0.2, "max_tokens": args.max_tokens}
        if settings.nvidia_api_key:
            kwargs["api_key"] = settings.nvidia_api_key
        return ChatNVIDIA(**kwargs), args.model
    model = (
        settings.nemotron_model_fast
        if args.profile == "fast"
        else settings.nemotron_model_reason
    )
    return get_chat(args.profile, max_tokens=args.max_tokens, temperature=0.2), model


def main() -> int:
    args = _parse_args()
    settings = get_settings()
    if not settings.nvidia_api_key:
        print("ERRO: defina NVIDIA_API_KEY no ambiente/.env.", file=sys.stderr)
        return 2

    path = Path(args.matrix_path)
    if not path.exists():
        print(f"ERRO: matriz nao encontrada em {path}.", file=sys.stderr)
        return 2
    matrix = BenchMatrix.model_validate_json(path.read_text(encoding="utf-8"))
    cell = matrix.cell(args.tier)
    if cell is None:
        tiers = ", ".join(c.tier for c in matrix.cells) or "(nenhum)"
        print(f"ERRO: tier '{args.tier}' nao existe. Tiers: {tiers}.", file=sys.stderr)
        return 2

    chat, model = _build_chat(args, settings)
    print(f"Medindo NIM hospedado: model={model} tier={args.tier} n={args.n} (+1 warmup)...")
    try:
        _one_call(chat, DEFAULT_PROMPT)  # warmup (cold start fora da medicao)
        latencies: list[float] = []
        tok_per_s: list[float] = []
        for i in range(args.n):
            elapsed, otoks = _one_call(chat, DEFAULT_PROMPT)
            latencies.append(elapsed)
            if elapsed > 0 and otoks > 0:
                tok_per_s.append(otoks / elapsed)
            print(f"  [{i + 1}/{args.n}] {elapsed * 1000:.0f} ms, {otoks} tokens")
    except Exception as e:  # noqa: BLE001 — falha de rede/timeout vira erro legivel
        print(f"ERRO na medicao: {type(e).__name__}: {str(e)[:200]}", file=sys.stderr)
        return 1

    if not tok_per_s:
        print("ERRO: nenhuma medicao valida (0 tokens?).", file=sys.stderr)
        return 1

    p50_ms = _percentile(latencies, 0.50) * 1000
    p95_ms = _percentile(latencies, 0.95) * 1000
    throughput = round(statistics.mean(tok_per_s), 1)

    cell.optimized.throughput_tok_s = throughput
    cell.optimized.p95_ms = round(p95_ms, 1)
    cell.optimized.is_live_run = True
    cell.optimized.source = (
        f"medido ao vivo: NIM hospedado {model} (build.nvidia.com) em {date.today().isoformat()}"
    )
    if args.cost_per_1m is not None:
        cell.optimized.cost_per_1m_usd = args.cost_per_1m

    serialized = json.dumps(matrix.model_dump(), ensure_ascii=False, indent=2) + "\n"
    path.write_text(serialized, encoding="utf-8")

    cost_note = "fixado" if args.cost_per_1m is not None else "inalterado (use --cost-per-1m)"
    b = cell.baseline
    print(f"\nResultado (lado otimizado, tier {args.tier}):")
    print(f"  throughput : {throughput} tok/s")
    print(f"  latencia   : p50 {p50_ms:.0f} ms | p95 {p95_ms:.0f} ms")
    print(f"  custo/1M   : {cell.optimized.cost_per_1m_usd} US$ ({cost_note})")
    print(
        f"  baseline   : {b.name} ({b.throughput_tok_s} tok/s, p95 {b.p95_ms} ms, "
        f"{b.cost_per_1m_usd} US$/1M) — ajustavel a mao"
    )
    print(f"\nMatriz atualizada em {path}. Ligue o ROI com GPU_BENCHMARK_USE_MATRIX=true.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
