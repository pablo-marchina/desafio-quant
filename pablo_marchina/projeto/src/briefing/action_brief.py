from typing import cast

from src.briefing.schemas import (
    BriefEvidenceItem,
    BriefSection,
    BriefUncertainty,
    BriefVerdict,
    StartupActionBrief,
)
from src.diagnosis.schemas import EvidenceTag
from src.extraction.schemas import ConfidenceLevel
from src.pipeline.run_pipeline import PipelineResult
from src.rag.context_packing import build_supporting_contexts
from src.rag.schemas import PackingResult
from src.recommendation.schemas import RecommendedNextAction


def _determine_verdict(
    confidence: ConfidenceLevel,
    motion: str,
    has_approach_now: bool,
    total_gaps: int,
    evidence_count: int,
) -> BriefVerdict:
    if motion == "not_recommended":
        return BriefVerdict.NOT_RECOMMENDED
    if confidence == ConfidenceLevel.LOW or evidence_count == 0:
        return BriefVerdict.NEEDS_VALIDATION
    if has_approach_now and confidence == ConfidenceLevel.HIGH:
        return BriefVerdict.HIGH_PRIORITY
    if total_gaps == 0 and confidence == ConfidenceLevel.HIGH:
        return BriefVerdict.PROMISING
    if motion in ("monitor_and_nurture", "lack_evidence_more_research"):
        return BriefVerdict.EARLY_STAGE
    if has_approach_now:
        return BriefVerdict.HIGH_PRIORITY
    return BriefVerdict.PROMISING


def _build_evidence_items(result: PipelineResult) -> list[BriefEvidenceItem]:
    items: list[BriefEvidenceItem] = []
    seen: set[str] = set()
    for ev in result.evidence_used:
        key = f"{ev.claim}:{str(ev.source_url)}"
        if key not in seen:
            seen.add(key)
            items.append(
                BriefEvidenceItem(
                    claim=ev.claim,
                    tag=ev.evidence_kind.value,
                    confidence=ev.confidence.value,
                    source_url=str(ev.source_url),
                    source_type=ev.source_type.value,
                )
            )
    return items


def _build_uncertainties(result: PipelineResult) -> list[BriefUncertainty]:
    uncertainties: list[BriefUncertainty] = []
    if result.gap_diagnosis:
        for gap in result.gap_diagnosis.diagnosed_gaps:
            if gap.evidence_tag in (EvidenceTag.INFERRED, EvidenceTag.HYPOTHESIS):
                uncertainties.append(
                    BriefUncertainty(
                        description=f"Gap '{gap.gap.value}' detected as {gap.evidence_tag.value}",
                        source="gap_diagnosis",
                        impact=("Recommendation reliability is reduced; collect direct evidence to confirm."),
                    )
                )
    return uncertainties


def _build_section(
    title: str,
    lines: list[str],
    items: list[BriefEvidenceItem] | None = None,
) -> BriefSection:
    return BriefSection(title=title, content="\n\n".join(lines) if lines else "", items=items or [])


def _gather_approach_now_count(
    recommendations: list[dict],
) -> int:
    count = 0
    for r in recommendations:
        if r.get("action") == RecommendedNextAction.APPROACH_NOW.value:
            count += 1
    return count


def build_action_brief(
    result: PipelineResult,
    packing_result: PackingResult | None = None,
) -> StartupActionBrief:
    profile = result.startup_profile
    classification = result.ai_native_classification

    # Auto-extract packing_result from pipeline RAG output if available
    if packing_result is None and result.rag_output is not None:
        packing_result = result.rag_output.packing_result

    recs = result.recommendation
    rec_dicts = [r.model_dump() for r in recs.recommendations] if recs else []
    diag = result.gap_diagnosis
    detected = [g for g in (diag.diagnosed_gaps if diag else []) if g.detected]
    total_gaps = len(detected)
    has_approach = _gather_approach_now_count(rec_dicts) > 0
    evidence_count = len(result.evidence_used)
    motion = result.recommended_motion
    cs = result.composite_score
    confidence = cs.confidence if cs else ConfidenceLevel.LOW

    evidence_items = _build_evidence_items(result)
    uncertainties = _build_uncertainties(result)
    missing_evidence_items = list(result.missing_evidence)
    if confidence == ConfidenceLevel.LOW and not missing_evidence_items:
        missing_evidence_items = [
            "validated_public_evidence",
            "technical_stack_evidence",
            "production_readiness_evidence",
        ]
    if motion == "monitor_and_nurture" and (missing_evidence_items or uncertainties or total_gaps > 0):
        motion = "lack_evidence_more_research"

    verdict = _determine_verdict(confidence, motion, has_approach, total_gaps, evidence_count)

    gap_lines: list[str] = []
    if result.gap_diagnosis:
        for g in result.gap_diagnosis.diagnosed_gaps:
            if g.detected:
                gap_lines.append(
                    f"- **{g.gap.value}** — {g.evidence_tag.value} (confidence: {g.confidence.value})\n  {g.reasoning}"
                )

    tech_lines: list[str] = []
    if diag:
        for tc in diag.nvidia_technology_candidates:
            tech_lines.append(
                f"- **{tc.technology_name}** addresses **{tc.addresses_gap.value}**\n  {tc.justification}"
            )

    exp_lines: list[str] = []
    if result.recommendation:
        for r in result.recommendation.recommendations:
            if r.suggested_experiment:
                exp_lines.append(
                    f"- **{r.suggested_experiment.title}**\n"
                    f"  Hypothesis: {r.suggested_experiment.hypothesis}\n"
                    f"  Metric: {r.suggested_experiment.success_metric}\n"
                    f"  Duration: {r.suggested_experiment.estimated_duration}\n"
                    f"  Next step: {r.suggested_experiment.next_step}"
                )

    rec_action_lines: list[str] = []
    if result.recommendation:
        for r in result.recommendation.recommendations:
            rec_action_lines.append(f"- [{r.action.value}] {r.diagnosed_gap.value}: {r.next_action_for_nvidia_team}")

    next_action = ""
    if result.recommendation and result.recommendation.top_recommendation:
        top = result.recommendation.top_recommendation
        next_action = top.next_action_for_nvidia_team
    elif motion == "not_recommended":
        next_action = "No action recommended at this time."
    elif confidence == ConfidenceLevel.LOW:
        next_action = "Manually validate startup before any outreach."
    else:
        next_action = f"Monitor startup — current motion: {motion}"

    sections: list[BriefSection] = [
        _build_section(
            "Executive Summary",
            [
                (
                    f"{profile.startup_name} ({profile.sector}) — {' '.join(classification.reasoning.split()[:20])}..."
                    if classification.reasoning
                    else f"{profile.startup_name} ({profile.sector})"
                ),
                f"Verdict: **{verdict.value}** | "
                f"Priority Score: {result.final_priority_score}/100 | "
                f"Motion: {motion} | "
                f"Confidence: {confidence.value}",
                f"Gaps detected: {total_gaps} | Evidence items: {evidence_count} | Next action: {next_action}",
            ],
        ),
        _build_section(
            "Why This Startup Matters",
            [
                f"Sector: **{profile.sector}**",
                f"Description: {profile.description}",
                f"Product: {profile.product_summary}",
                f"Classification: **{classification.classification.value}** "
                f"(confidence: {classification.confidence.value})",
            ],
        ),
        _build_section(
            "AI-Native Maturity",
            [
                f"Level: **{classification.classification.value}**",
                f"Confidence: {classification.confidence.value}",
                f"Reasoning: {classification.reasoning}",
            ],
        ),
        _build_section(
            "Scores Overview",
            [
                "| Dimension | Score | Confidence |",
                "|---|---|---|",
                f"| AI-Native Defensibility | {result.defensibility_score.total_score:.0f}/100"
                f" | {result.defensibility_score.confidence.value} |",
                f"| NVIDIA Inception Fit | {result.inception_fit_score.total_score:.0f}/100"
                f" | {result.inception_fit_score.confidence.value} |",
                f"| Production AI Readiness"
                f" | {result.production_readiness_score.production_readiness_score:.0f}/100"
                f" | {result.production_readiness_score.confidence.value} |",
                (
                    f"| Composite Score | {result.composite_score.composite_score:.0f}/100"
                    f" | {result.composite_score.confidence.value} |"
                    if result.composite_score
                    else "| Composite Score | N/A | N/A |"
                ),
            ],
        ),
    ]

    if gap_lines:
        sections.append(_build_section("Production AI Gaps", gap_lines))

    if tech_lines:
        sections.append(_build_section("NVIDIA Fit", tech_lines))

    sections.append(
        _build_section(
            "Recommended NVIDIA Technologies",
            tech_lines if tech_lines else ["No specific NVIDIA technologies recommended."],
        )
    )

    if exp_lines:
        sections.append(_build_section("Suggested Technical Experiment", exp_lines))

    sections.append(
        _build_section(
            "Recommended Motion",
            (
                [
                    f"Motion: **{motion}**",
                    f"Priority Score: {result.final_priority_score}/100",
                ]
                + rec_action_lines
                if rec_action_lines
                else [
                    f"Motion: **{motion}**",
                    f"Priority Score: {result.final_priority_score}/100",
                ]
            ),
        )
    )

    sections.append(
        _build_section(
            "Evidence",
            (
                [
                    f"Total evidence items: {len(evidence_items)}",
                ]
                + [f"- **[{e.tag}]** {e.claim} ({e.confidence}, {e.source_type})" for e in evidence_items]
                if evidence_items
                else ["No evidence collected."]
            ),
        )
    )

    packed_rag_contexts_list: list = []
    supporting_nvidia_context_list: list = []
    dropped_contexts_debug_list: list = []

    if packing_result and packing_result.packed:
        packed_rag_contexts_list = packing_result.packed
        supporting_nvidia_context_list = build_supporting_contexts(packing_result)
        dropped_contexts_debug_list = packing_result.dropped
        ctx_lines: list[str] = []
        for sc in supporting_nvidia_context_list:
            ctx_lines.append(f"- **{sc.technology}** for *{sc.gap_type}*:")
            for pc in sc.contexts:
                ctx_lines.append(
                    f"  - {pc.title}: {pc.content[:120]}... (score: {pc.relevance_score}, [source]({pc.url or '#'}))"
                )
        if ctx_lines:
            sections.append(_build_section("Supporting NVIDIA Context", ctx_lines))

    if missing_evidence_items:
        sections.append(
            _build_section(
                "Missing Evidence",
                [f"- {m}" for m in missing_evidence_items],
            )
        )

    if uncertainties:
        sections.append(
            _build_section(
                "Uncertainties / Limitations",
                [f"- **{u.description}**\n  Source: {u.source}\n  Impact: {u.impact}" for u in uncertainties],
            )
        )

    sections.append(
        _build_section(
            "Next Action",
            [f"**{next_action}**"],
        )
    )

    def make_dict(score_obj: object) -> dict:
        if hasattr(score_obj, "model_dump"):
            return cast(dict, score_obj.model_dump())  # type: ignore[union-attr]
        return {}

    gaps_objs = diag.diagnosed_gaps if diag else []
    gaps_list = [g.model_dump() for g in gaps_objs]
    tech_cands_objs = diag.nvidia_technology_candidates if diag else []
    tech_cands = [tc.model_dump() for tc in tech_cands_objs]

    return StartupActionBrief(
        startup_name=result.startup_name,
        website=str(profile.website),
        sector=profile.sector,
        one_line_summary=(
            f"{profile.startup_name} — {profile.description[:100]}"
            if len(profile.description) > 100
            else f"{profile.startup_name} — {profile.description}"
        ),
        verdict=verdict,
        final_priority_score=result.final_priority_score,
        recommended_motion=motion,
        confidence=confidence,
        sections=sections,
        ai_native_classification=make_dict(classification),
        defensibility_score=make_dict(result.defensibility_score),
        inception_fit_score=make_dict(result.inception_fit_score),
        production_readiness_score=make_dict(result.production_readiness_score),
        composite_score=make_dict(result.composite_score),
        diagnosed_gaps=gaps_list,
        nvidia_technology_candidates=tech_cands,
        recommendations=rec_dicts,
        evidence_used=evidence_items,
        missing_evidence=missing_evidence_items,
        uncertainties=uncertainties,
        next_action_for_nvidia_team=next_action,
        reasoning=result.reasoning,
        packed_rag_contexts=packed_rag_contexts_list,
        supporting_nvidia_context=supporting_nvidia_context_list,
        dropped_contexts_debug=dropped_contexts_debug_list,
    )
