#!/usr/bin/env python3
"""Run the optional offline LLM judge adapter for Answer Quality cases."""

# ruff: noqa: E402

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

from pydantic import HttpUrl

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.briefing.action_brief import build_action_brief  # noqa: E402
from src.briefing.schemas import StartupActionBrief  # noqa: E402
from src.evaluation.answer_quality_eval import (  # noqa: E402
    evaluate_answer_quality,
    load_answer_quality_cases,
)
from src.evaluation.answer_quality_schemas import AnswerQualityEvalCase  # noqa: E402
from src.evaluation.llm_judge_adapter import (
    NullLLMJudgeProvider,
    run_llm_judge_for_cases,
)  # noqa: E402
from src.evaluation.llm_judge_schemas import (  # noqa: E402
    LLMJudgeInput,
    LLMJudgeProviderConfig,
    LLMJudgeRunReport,
)
from src.extraction.schemas import (
    ConfidenceLevel,
    Evidence,
    SourceType,
    StartupProfile,
)  # noqa: E402
from src.pipeline.run_pipeline import run_full_pipeline  # noqa: E402
from src.rag.embeddings import SentenceTransformerProvider  # noqa: E402
from src.rag.retrieval import build_default_index  # noqa: E402
from src.rag.schemas import PackingConfig, RerankingConfig  # noqa: E402
from src.rag.vector_store import InMemoryVectorStore  # noqa: E402

DEFAULT_CASES_PATH = PROJECT_ROOT / "examples" / "answer_quality" / "golden_answer_quality_cases.json"
DEFAULT_GOLDEN_DIR = PROJECT_ROOT / "examples" / "golden"
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "data" / "regression_reports"
DEFAULT_JSON_REPORT = DEFAULT_OUTPUT_DIR / "answer_quality_llm_judge_report.json"
DEFAULT_MD_REPORT = DEFAULT_OUTPUT_DIR / "answer_quality_llm_judge_report.md"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run optional/experimental Answer Quality LLM judge with a null provider.",
    )
    parser.add_argument("--cases-path", default=str(DEFAULT_CASES_PATH))
    parser.add_argument("--golden-dir", default=str(DEFAULT_GOLDEN_DIR))
    parser.add_argument("--output-json", default=str(DEFAULT_JSON_REPORT))
    parser.add_argument("--output-md", default=str(DEFAULT_MD_REPORT))
    parser.add_argument("--max-cases", type=int, default=None)
    parser.add_argument(
        "--provider",
        default="null",
        choices=["null"],
        help="Only the offline null provider is implemented in Epic 23.2.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    config = LLMJudgeProviderConfig(
        provider_name=args.provider,
        enabled=False,
        model_name="null-offline-deterministic",
        max_cases=args.max_cases,
        metadata={"experimental": "true", "ci_gate": "false"},
    )
    judge_inputs = build_judge_inputs(Path(args.cases_path), Path(args.golden_dir))
    report = run_llm_judge_for_cases(
        judge_inputs,
        NullLLMJudgeProvider(config),
        input_source=str(Path(args.cases_path)),
    )
    json_path = Path(args.output_json)
    md_path = Path(args.output_md)
    write_reports(report, json_path, md_path)
    print("Optional LLM judge completed with offline null provider.")
    print(f"JSON report: {json_path}")
    print(f"Markdown report: {md_path}")
    return 0


def build_judge_inputs(cases_path: Path, golden_dir: Path) -> list[LLMJudgeInput]:
    """Build judge inputs from answer quality golden cases."""
    judge_inputs: list[LLMJudgeInput] = []
    for case in load_answer_quality_cases(cases_path):
        brief = _build_brief(case, golden_dir)
        deterministic_result = evaluate_answer_quality(brief, case)
        judge_inputs.append(
            LLMJudgeInput(
                case_id=case.case_id,
                case_description=case.description,
                pipeline_case_id=case.pipeline_case_id,
                answer_text=_brief_answer_text(brief),
                startup_evidence=[item.model_dump(mode="json") for item in brief.evidence_used],
                rag_contexts=[item.model_dump(mode="json") for item in brief.packed_rag_contexts],
                diagnosed_gaps=brief.diagnosed_gaps,
                nvidia_technology_candidates=brief.nvidia_technology_candidates,
                recommendations=brief.recommendations,
                missing_evidence=brief.missing_evidence,
                uncertainties=[item.model_dump(mode="json") for item in brief.uncertainties],
                deterministic_metrics=deterministic_result.metrics.model_dump(mode="json"),
            )
        )
    return judge_inputs


def write_reports(report: LLMJudgeRunReport, json_path: Path, md_path: Path) -> None:
    """Write optional judge JSON and Markdown reports."""
    json_path.parent.mkdir(parents=True, exist_ok=True)
    md_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(report.model_dump_json(indent=2), encoding="utf-8")
    md_path.write_text(render_markdown_report(report), encoding="utf-8")


def render_markdown_report(report: LLMJudgeRunReport) -> str:
    """Render a compact human-readable optional judge report."""
    lines = [
        "# Optional Answer Quality LLM Judge Report",
        "",
        "This report is experimental, informational, and not a CI gate.",
        "",
        f"- Generated at: `{report.generated_at}`",
        f"- Provider: `{report.provider.provider_name}`",
        f"- Model: `{report.provider.model_name or 'not applicable'}`",
        f"- CI gate: `{str(report.is_ci_gate).lower()}`",
        f"- Total cases: `{report.total_cases}`",
        f"- Completed cases: `{report.completed_cases}`",
        f"- Error cases: `{report.error_cases}`",
        "",
        "## Summary",
        "",
        "| Metric | Value |",
        "|---|---:|",
    ]
    for key, value in report.summary.items():
        lines.append(f"| {key} | {value} |")
    lines.extend(["", "## Cases", ""])
    for result in report.results:
        lines.extend(
            [
                f"### {result.case_id}",
                "",
                f"- Status: `{result.status}`",
                f"- Mean confidence: `{result.score.judge_confidence}`",
                f"- Flags: `{', '.join(result.score.judge_flags)}`",
                f"- Rationale: {result.score.judge_rationale}",
                "",
            ]
        )
    return "\n".join(lines).rstrip() + "\n"


def _build_brief(case: AnswerQualityEvalCase, golden_dir: Path) -> StartupActionBrief:
    raw = json.loads((golden_dir / f"{case.pipeline_case_id}.json").read_text(encoding="utf-8"))
    profile_data = raw["profile"]
    profile = StartupProfile(
        startup_name=raw["case_id"],
        website=HttpUrl("https://example.com"),
        sector=profile_data.get("sector", "Technology"),
        description=profile_data.get("description", ""),
        product_summary=profile_data.get("product_summary", ""),
        ai_signals=profile_data.get("ai_signals", []),
        tech_stack_signals=profile_data.get("tech_stack", []),
        customers=profile_data.get("customers", []),
        funding_signals=profile_data.get("funding", []),
        sources=[],
        confidence_score=0.6,
    )
    evidence = [
        Evidence(
            claim=item["claim"],
            source_url=HttpUrl("https://example.com"),
            source_type=SourceType.OFFICIAL_SITE,
            quote_or_evidence=item["claim"],
            confidence=ConfidenceLevel(item["confidence"]),
            collected_at=datetime.now(UTC),
        )
        for item in raw.get("evidence", [])
    ]
    if case.use_rag:
        result = run_full_pipeline(
            startup_name=raw["case_id"],
            profile=profile,
            evidence_list=evidence,
            chunk_index=build_default_index(),
            embedding_model=SentenceTransformerProvider("all-MiniLM-L6-v2"),
            vector_store=InMemoryVectorStore(),
            reranking_config=RerankingConfig(),
            packing_config=PackingConfig(),
        )
    else:
        result = run_full_pipeline(
            startup_name=raw["case_id"],
            profile=profile,
            evidence_list=evidence,
        )
    return build_action_brief(result)


def _brief_answer_text(brief: StartupActionBrief) -> str:
    parts: list[str] = [
        brief.startup_name,
        brief.one_line_summary,
        brief.next_action_for_nvidia_team,
        brief.reasoning,
    ]
    for section in brief.sections:
        parts.extend([section.title, section.content])
        parts.extend(item.claim for item in section.items)
    return "\n".join(part for part in parts if part)


if __name__ == "__main__":
    raise SystemExit(main())
