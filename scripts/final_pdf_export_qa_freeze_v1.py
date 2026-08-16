#!/usr/bin/env python3
"""Final PDF export QA + freeze for ARGOS final submission.

This script intentionally builds from the already-versioned 5 SVG pages in
report/pages_submission. It does not read market outcomes, settlement, equity
returns, benchmark returns, or ARGOS PnL.
"""
from __future__ import annotations

import hashlib
import json
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PAGES_DIR = ROOT / "report" / "pages_submission"
OUT_DIR = ROOT / "dist" / "final_submission"
REG_DIR = ROOT / "registry"
PDF_OUT = OUT_DIR / "ARGOS_final_submission.pdf"
FREEZE_OUT = REG_DIR / "final_pdf_submission_freeze_v1.json"
TEXT_OUT = OUT_DIR / "ARGOS_final_submission_text.txt"

PAGES = [
    "fig01_strategy_pipeline.svg",
    "fig02_model_reduction.svg",
    "fig03_h2_results.svg",
    "fig04_economic_backtest.svg",
    "fig05_genai_future.svg",
]

ANONYMITY_FORBIDDEN = [
    r"\bPablo\b", r"\bMarchina\b", r"\bInteli\b", r"\buniversidade\b",
    r"\buniversity\b", r"\bfaculdade\b", r"\bGitHub\b", r"github\.com",
    r"desafio-quant", r"pablo-marchina",
]

CLAIM_FORBIDDEN = [
    r"alpha\s+validad[oa]", r"validated\s+alpha", r"deployable",
    r"pront[oa]\s+para\s+deploy", r"estrat[eé]gia\s+final\s+validada",
    r"backtest\s+financeiro\s+ampliado\s+executad[oa]",
    r"PnL\s+ampliado\s+executad[oa]", r"private\s+information",
]

REQUIRED_TEXT_HINTS = [
    "ARGOS", "C0_NO_TRADE", "1.355", "109", "GenAI"
]


def run(cmd: list[str], cwd: Path = ROOT) -> str:
    proc = subprocess.run(cmd, cwd=str(cwd), check=True, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    return proc.stdout


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def page_count(pdf: Path) -> int:
    out = run(["pdfinfo", str(pdf)])
    m = re.search(r"^Pages:\s+(\d+)", out, re.MULTILINE)
    if not m:
        raise RuntimeError("Could not parse page count from pdfinfo")
    return int(m.group(1))


def page_sizes(pdf: Path) -> list[str]:
    out = run(["pdfinfo", "-box", str(pdf)])
    return [line.strip() for line in out.splitlines() if line.startswith("Page") and "size:" in line]


def find_matches(patterns: list[str], text: str) -> list[str]:
    found = []
    for pat in patterns:
        if re.search(pat, text, flags=re.IGNORECASE):
            found.append(pat)
    return found


def find_forbidden_claim_matches(text: str) -> list[str]:
    """Find unsafe claims while allowing explicit disclaimers.

    The final deck intentionally says "não insiders" / "not insiders" to avoid
    any claim of private information. That is a safe disclaimer, not an unsafe
    insider-information claim.
    """
    found = find_matches(CLAIM_FORBIDDEN, text)
    insider_occurs = re.search(r"\binsiders?\b", text, flags=re.IGNORECASE)
    safe_no_insider = re.search(r"\b(não|nao|not)\s+insiders?\b", text, flags=re.IGNORECASE)
    if insider_occurs and not safe_no_insider:
        found.append(r"\binsiders?\b_without_safe_disclaimer")
    return found


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    REG_DIR.mkdir(parents=True, exist_ok=True)

    missing = [p for p in PAGES if not (PAGES_DIR / p).exists()]
    if missing:
        raise SystemExit(f"Missing SVG pages: {missing}")

    page_pdfs = []
    page_hashes = {}
    for i, name in enumerate(PAGES, start=1):
        svg = PAGES_DIR / name
        page_hashes[name] = sha256_file(svg)
        out_pdf = OUT_DIR / f"page_{i:02d}.pdf"
        run(["rsvg-convert", "-f", "pdf", "-o", str(out_pdf), str(svg)])
        page_pdfs.append(out_pdf)

    run(["pdfunite", *[str(p) for p in page_pdfs], str(PDF_OUT)])
    run(["pdftotext", str(PDF_OUT), str(TEXT_OUT)])
    text = TEXT_OUT.read_text(encoding="utf-8", errors="replace")

    pages = page_count(PDF_OUT)
    sizes = page_sizes(PDF_OUT)
    pdf_sha = sha256_file(PDF_OUT)
    anon_hits = find_matches(ANONYMITY_FORBIDDEN, text)
    claim_hits = find_forbidden_claim_matches(text)
    required_missing = [hint for hint in REQUIRED_TEXT_HINTS if hint.lower() not in text.lower()]

    qa_status = "PASS_FINAL_PDF_QA"
    failures = []
    if pages != 5:
        failures.append(f"PDF_PAGE_COUNT_{pages}_NOT_5")
    if anon_hits:
        failures.append("ANONYMITY_FORBIDDEN_TERMS_FOUND")
    if claim_hits:
        failures.append("FORBIDDEN_CLAIMS_FOUND")
    if required_missing:
        failures.append("REQUIRED_TEXT_HINTS_MISSING")
    if failures:
        qa_status = "FAIL_FINAL_PDF_QA"

    freeze = {
        "artifact": "FINAL_PDF_SUBMISSION_FREEZE",
        "version": "FINAL-PDF-SUBMISSION-FREEZE-v1.0",
        "date_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "status": qa_status,
        "pdf": {
            "path": str(PDF_OUT.relative_to(ROOT)),
            "sha256": pdf_sha,
            "pages": pages,
            "format": "16:9 widescreen from 1600x900 SVG pages",
            "source_pages_dir": str(PAGES_DIR.relative_to(ROOT)),
            "source_page_hashes": page_hashes,
            "page_size_lines_from_pdfinfo": sizes,
        },
        "qa": {
            "failures": failures,
            "anonymity_forbidden_matches": anon_hits,
            "claim_forbidden_matches": claim_hits,
            "required_text_hints_missing": required_missing,
            "checks": {
                "exactly_5_pages": pages == 5,
                "anonymous_text_scan_passed": not anon_hits,
                "forbidden_claim_scan_passed": not claim_hits,
                "required_core_terms_present": not required_missing,
                "page_4_closeout_policy": "uses PIT coverage closeout: official-domain 1355, final PIT coverage 109, no expanded PnL claim",
            },
        },
        "scientific_firewall": {
            "prediction_market_settlement_read": False,
            "earnings_numeric_outcomes_read": False,
            "realized_returns_read": False,
            "benchmark_return_read": False,
            "argos_pnl_read": False,
            "expanded_price_return_backtest_executed": False,
        },
        "submission_warning": "Official filename may need to be renamed to the challenge submission key before upload.",
    }
    FREEZE_OUT.write_text(json.dumps(freeze, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    print(json.dumps(freeze, ensure_ascii=False, indent=2, sort_keys=True))
    if failures:
        raise SystemExit("FAIL_FINAL_PDF_QA: " + ",".join(failures))


if __name__ == "__main__":
    main()
