#!/usr/bin/env python3
"""Add the last mandatory GenAI disclosure to the visually approved page set.

This overlay only adds the explicitly documented tool name and team-vs-AI
responsibility split required by the challenge directions. No scientific or
quantitative content changes.
"""
from __future__ import annotations

import hashlib
import json
from html import escape
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "report" / "pages_final"
OUT = ROOT / "report" / "pages_submission"
REG = ROOT / "registry"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rect(x, y, w, h, fill, stroke="none", sw=0, r=18):
    return f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{r}" fill="{fill}" stroke="{stroke}" stroke-width="{sw}"/>'


def text(x, y, value, size, fill, weight=400, anchor="start"):
    return f'<text x="{x}" y="{y}" font-family="Inter,Segoe UI,Arial,sans-serif" font-size="{size}" font-weight="{weight}" fill="{fill}" text-anchor="{anchor}">{escape(value)}</text>'


def inject(svg: str, additions: list[str]) -> str:
    return svg.replace("</svg>", "\n" + "\n".join(additions) + "\n</svg>")


def main() -> None:
    identity = json.loads((REG / "argos_visual_identity_freeze.json").read_text(encoding="utf-8"))
    disclosure = json.loads((REG / "genai_report_disclosure.json").read_text(encoding="utf-8"))
    assert disclosure["status"] == "REPORT_SAFE"
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
        src = SRC / name
        if not src.exists():
            raise FileNotFoundError(src)
        svg = src.read_text(encoding="utf-8")
        if name.startswith("fig05"):
            additions = [
                rect(80, 188, 300, 34, p["surface_2"], p["sensor_cyan"], 1, 17),
                text(230, 211, disclosure["report_safe_short_copy"]["tool"], 14, p["sensor_cyan"], 700, "middle"),
                rect(395, 188, 465, 34, p["surface_2"], p["grid"], 1, 17),
                text(627.5, 211, "Equipe decide • IA apoia sob verificação", 14, p["paper"], 600, "middle"),
            ]
            svg = inject(svg, additions)
        target = OUT / name
        target.write_text(svg, encoding="utf-8")
        outputs[name] = sha256(target)

    manifest = {
        "artifact": "ARGOS_SUBMISSION_PAGE_SET",
        "version": "SPS-v1.0",
        "status": "PASS_SUBMISSION_PAGES_READY_FOR_PDF_BUILD",
        "scientific_reopen": False,
        "source": "report/pages_final",
        "mandatory_genai_disclosure": disclosure["report_safe_short_copy"],
        "outputs": outputs,
        "disclosure_sha256": sha256(REG / "genai_report_disclosure.json")
    }
    (OUT / "manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(manifest, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
