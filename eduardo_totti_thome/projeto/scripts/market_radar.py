"""Imprime o Radar de Mercado (camada macro / Entregável 6).

Uso:
    uv run python scripts/market_radar.py             # só o panorama (sem LLM)
    uv run python scripts/market_radar.py --briefing  # + leitura estratégica (1 chamada LLM)
"""

from __future__ import annotations

import sys

from db.market import market_briefing, market_radar


def main() -> int:
    r = market_radar()
    print(f"RADAR DE MERCADO - {r['total']} startups analisadas\n")

    print("Distribuicao de maturidade:")
    for nivel, n in r["distribuicao"].items():
        print(f"  {nivel:22} {n}")

    print("\nTecnologias NVIDIA mais demandadas:")
    for tech, n in r["top_tecnologias"]:
        print(f"  {tech:34} {n}")

    print("\nPrioridade de abordagem (mais madura primeiro):")
    for p in r["prioridade"]:
        nivel = p["level"] if p["level"] is not None else "-"
        print(f"  nivel {str(nivel):3}  {p['startup']}")

    if "--briefing" in sys.argv:
        print("\n" + "=" * 60 + "\nLEITURA ESTRATEGICA DE MERCADO\n" + "=" * 60)
        print(market_briefing(r))
    return 0


if __name__ == "__main__":
    sys.exit(main())
