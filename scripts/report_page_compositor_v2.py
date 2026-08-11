#!/usr/bin/env python3
"""Apply adversarial-scoring authoring overlays to frozen FFF-v1.0 SVG pages.

The compositor does not alter numerical results. It only makes already-permitted
claims more explicit where ARSR-v1.0 identified rubric-visibility risk.
"""
from __future__ import annotations

import hashlib
import json
from html import escape
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "report" / "figures"
OUT = ROOT / "report" / "pages_v2"
REG = ROOT / "registry"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rect(x, y, w, h, fill, stroke="none", sw=0, r=12, opacity=1):
    return f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{r}" fill="{fill}" stroke="{stroke}" stroke-width="{sw}" opacity="{opacity}"/>'


def text(x, y, value, size, fill, weight=400, anchor="start"):
    return f'<text x="{x}" y="{y}" font-family="Inter,Segoe UI,Arial,sans-serif" font-size="{size}" font-weight="{weight}" fill="{fill}" text-anchor="{anchor}">{escape(value)}</text>'


def inject(svg: str, additions: list[str]) -> str:
    marker = "</svg>"
    if marker not in svg:
        raise RuntimeError("Invalid SVG: missing closing tag")
    return svg.replace(marker, "\n" + "\n".join(additions) + "\n" + marker)


def page1(svg: str, p: dict[str, str]) -> str:
    add = [
        rect(100, 200, 1420, 58, p["surface_2"], p["grid"], 1, 14),
        text(125, 237, "HIPÓTESE • movimentos anormais só importam se melhorarem M2 fora da amostra.", 18, p["sensor_cyan"], 700),
        text(1490, 237, "falsificável antes dos outcomes", 15, p["muted"], 400, "end"),
        # Repair the only visual clipping found in the first render.
        rect(1095, 760, 425, 48, p["ink"], "none", 0, 0),
        text(1120, 790, "Muitos olhos. Risco só com evidência incremental.", 17, p["gate_amber"], 700),
        text(1450, 158, "múltiplos sensores", 13, p["muted"], 600, "middle"),
        text(1450, 176, "não insiders", 13, p["muted"], 400, "middle"),
    ]
    return inject(svg, add)


def page2(svg: str, p: dict[str, str]) -> str:
    add = [
        rect(100, 638, 1340, 46, p["surface_2"], p["grid"], 1, 12),
        text(125, 668, "6 mecanismos • estado condicional | velocidade | fluxo assinado | concentração | persistência direcional | salto/regime", 18, p["paper"], 600),
    ]
    return inject(svg, add)


def page3(svg: str, p: dict[str, str]) -> str:
    add = [
        rect(930, 187, 480, 38, p["surface_2"], p["sensor_cyan"], 1, 19),
        text(1170, 212, "H1 SUPORTADA • prob. PIT preditiva vs baselines públicos testados", 14, p["sensor_cyan"], 700, "middle"),
    ]
    return inject(svg, add)


def page4(svg: str, p: dict[str, str]) -> str:
    return svg


def page5(svg: str, p: dict[str, str]) -> str:
    add = [
        rect(102, 646, 716, 78, p["surface"], "none", 0, 8),
        text(120, 673, "Casos concretos • dados/CI reproduzíveis • auditoria outcome-blind de 69 técnicas", 16, p["paper"], 600),
        text(120, 700, "preregistro + execução/falsificação determinística", 16, p["paper"], 600),
        text(120, 721, "11 entradas • human-in-the-loop • outcome firewall", 14, p["muted"], 400),
    ]
    return inject(svg, add)


def main() -> None:
    identity = json.loads((REG / "argos_visual_identity_freeze.json").read_text(encoding="utf-8"))
    review = json.loads((REG / "adversarial_report_scoring_review_v1.json").read_text(encoding="utf-8"))
    assert identity["status"] == "PASS_VISUAL_IDENTITY_FREEZE"
    assert review["status"] == "PASS_WITH_FOUR_AUTHORING_FIXES_REQUIRED_BEFORE_FINAL"
    p = identity["palette"]
    OUT.mkdir(parents=True, exist_ok=True)

    specs = [
        ("fig01_strategy_pipeline.svg", page1),
        ("fig02_model_reduction.svg", page2),
        ("fig03_h2_results.svg", page3),
        ("fig04_economic_backtest.svg", page4),
        ("fig05_genai_future.svg", page5),
    ]
    outputs: dict[str, str] = {}
    for name, fn in specs:
        source = SRC / name
        if not source.exists():
            raise FileNotFoundError(source)
        rendered = fn(source.read_text(encoding="utf-8"), p)
        target = OUT / name
        target.write_text(rendered, encoding="utf-8")
        outputs[name] = sha256(target)

    manifest = {
        "artifact": "ARGOS_REPORT_PAGE_COMPOSITOR_V2",
        "version": "RPC-v2.0",
        "status": "PASS_ADVERSARIAL_AUTHORING_FIXES_MATERIALIZED",
        "scientific_reopen": False,
        "source_factory_manifest": "report/figures/manifest.json",
        "review_source": "registry/adversarial_report_scoring_review_v1.json",
        "review_sha256": sha256(REG / "adversarial_report_scoring_review_v1.json"),
        "identity_sha256": sha256(REG / "argos_visual_identity_freeze.json"),
        "outputs": outputs,
        "fixes": [
            "Page 1 explicit falsifiable hypothesis",
            "Page 1 ARGOS multiple-sensor/non-insider name explanation",
            "Page 1 clipped tagline repaired",
            "Page 2 six economic mechanisms named",
            "Page 3 H1 supported qualitative banner",
            "Page 5 three concrete GenAI contribution labels"
        ],
        "claim_policy": "All overlays are restatements of already-permitted SF-v3.0/FST/W1 claims; no new metric or result is introduced."
    }
    (OUT / "manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(manifest, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
