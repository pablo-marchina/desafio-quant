#!/usr/bin/env python3
"""Final visual repair pass over RPC-v2 pages.

Only two render defects are repaired: page-1 tagline overflow/ghost text and the
page-2 challenger card touching the right canvas boundary. No content or result
changes are introduced.
"""
from __future__ import annotations

import hashlib
import json
from html import escape
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "report" / "pages_v2"
OUT = ROOT / "report" / "pages_final"
REG = ROOT / "registry"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rect(x, y, w, h, fill, stroke="none", sw=0, r=12):
    return f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{r}" fill="{fill}" stroke="{stroke}" stroke-width="{sw}"/>'


def text(x, y, value, size, fill, weight=400, anchor="start"):
    return f'<text x="{x}" y="{y}" font-family="Inter,Segoe UI,Arial,sans-serif" font-size="{size}" font-weight="{weight}" fill="{fill}" text-anchor="{anchor}">{escape(value)}</text>'


def inject(svg: str, additions: list[str]) -> str:
    return svg.replace("</svg>", "\n" + "\n".join(additions) + "\n</svg>")


def repair_page1(svg: str, p: dict[str, str]) -> str:
    # Mask the full old tagline footprint through the right edge, then redraw as
    # two short lines so no glyph can clip or ghost outside the intended area.
    return inject(svg, [
        rect(1080, 752, 520, 72, p["ink"], "none", 0, 0),
        text(1120, 782, "Muitos olhos.", 16, p["gate_amber"], 700),
        text(1120, 806, "Risco só com evidência incremental.", 16, p["gate_amber"], 700),
    ])


def repair_page2(svg: str, p: dict[str, str]) -> str:
    # Cover only the clipped challenger zone and redraw it with a safe right
    # margin. Existing five upstream stages remain byte-visible underneath.
    additions = [
        rect(1405, 305, 195, 225, p["ink"], "none", 0, 0),
        '<line x1="1372" y1="420" x2="1416" y2="420" stroke="#9FB0C3" stroke-width="3" marker-end="url(#arrow)"/>',
        rect(1430, 338, 145, 165, p["surface"], p["gate_amber"], 2, 16),
        text(1502.5, 402, "1", 58, p["gate_amber"], 700, "middle"),
        text(1502.5, 456, "Challenger", 20, p["paper"], 700, "middle"),
        text(1502.5, 486, "não linear", 17, p["muted"], 400, "middle"),
    ]
    return inject(svg, additions)


def main() -> None:
    identity = json.loads((REG / "argos_visual_identity_freeze.json").read_text(encoding="utf-8"))
    p = identity["palette"]
    OUT.mkdir(parents=True, exist_ok=True)

    names = [
        "fig01_strategy_pipeline.svg",
        "fig02_model_reduction.svg",
        "fig03_h2_results.svg",
        "fig04_economic_backtest.svg",
        "fig05_genai_future.svg",
    ]
    outputs: dict[str, str] = {}
    for name in names:
        source = SRC / name
        if not source.exists():
            raise FileNotFoundError(source)
        svg = source.read_text(encoding="utf-8")
        if name.startswith("fig01"):
            svg = repair_page1(svg, p)
        elif name.startswith("fig02"):
            svg = repair_page2(svg, p)
        target = OUT / name
        target.write_text(svg, encoding="utf-8")
        outputs[name] = sha256(target)

    manifest = {
        "artifact": "ARGOS_REPORT_FINAL_PAGE_SET",
        "version": "RPF-v1.0",
        "status": "PASS_FINAL_PAGE_SET_READY_FOR_PDF_QA",
        "scientific_reopen": False,
        "source": "report/pages_v2",
        "repairs": [
            "Page 1 full-width mask plus two-line tagline redraw",
            "Page 2 challenger card redrawn inside safe right margin"
        ],
        "outputs": outputs,
        "identity_sha256": sha256(REG / "argos_visual_identity_freeze.json")
    }
    (OUT / "manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(manifest, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
