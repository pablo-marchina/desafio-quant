"""CLI for the startup enrichment pipeline."""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from datetime import UTC, datetime, timedelta
from typing import Any
from time import perf_counter

from . import config
from .cache import load as cache_load, save as cache_save
from .graph import enrichment_graph
from .nodes.update_supabase import load_candidates


def _merge_summary(aggregate: dict[str, Any], item: dict[str, Any]) -> None:
    for key, value in item.items():
        if key == "errors_by_source":
            continue
        if isinstance(value, (int, bool)):
            aggregate[key] = int(aggregate.get(key, 0)) + int(value)
    errors = Counter(aggregate.get("errors_by_source", {}))
    errors.update(item.get("errors_by_source", {}))
    aggregate["errors_by_source"] = dict(errors)
    review_reasons = Counter(aggregate.get("review_reasons", {}))
    reason = item.get("review_reason")
    if reason:
        review_reasons[str(reason)] += 1
    aggregate["review_reasons"] = dict(review_reasons)


def _candidate_label(candidate: dict[str, Any]) -> str:
    return str(candidate.get("company_name") or candidate.get("nome") or candidate.get("normalized_name") or candidate.get("id") or "candidato_sem_nome")


def _candidate_key(candidate: dict[str, Any]) -> str:
    return str(candidate.get("id") or candidate.get("raw_company_id") or candidate.get("normalized_name") or _candidate_label(candidate))


def _print_progress(message: str) -> None:
    print(message, file=sys.stderr, flush=True)


def _format_table(rows: list[dict[str, Any]]) -> str:
    headers = ["company_name", "status", "classification", "confidence", "validated_url", "website_candidate", "attempts", "reason"]
    widths = {header: len(header) for header in headers}
    normalized_rows = []
    for row in rows:
        normalized = {
            "company_name": str(row.get("company_name") or ""),
            "status": str(row.get("status") or ""),
            "classification": str(row.get("classification") or ""),
            "confidence": str(row.get("confidence") or ""),
            "validated_url": str(row.get("validated_url") or ""),
            "website_candidate": str(row.get("website_candidate") or ""),
            "attempts": str(row.get("attempts") or ""),
            "reason": str(row.get("reason") or ""),
        }
        normalized_rows.append(normalized)
        for header in headers:
            widths[header] = max(widths[header], len(normalized[header]))
    lines = []
    lines.append(" | ".join(header.ljust(widths[header]) for header in headers))
    lines.append("-|-".join("-" * widths[header] for header in headers))
    for row in normalized_rows:
        lines.append(" | ".join(row[header].ljust(widths[header]) for header in headers))
    return "\n".join(lines)


def _load_checkpoint(reset: bool = False) -> dict[str, Any]:
    if reset or not config.CHECKPOINT_PATH.exists():
        return {"processed": {}, "failed": {}, "last_saved_at": None}
    try:
        return json.loads(config.CHECKPOINT_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {"processed": {}, "failed": {}, "last_saved_at": None}


def _save_checkpoint(checkpoint: dict[str, Any]) -> None:
    config.CHECKPOINT_PATH.parent.mkdir(parents=True, exist_ok=True)
    checkpoint["last_saved_at"] = datetime.now(UTC).isoformat()
    config.CHECKPOINT_PATH.write_text(json.dumps(checkpoint, ensure_ascii=False, indent=2), encoding="utf-8")


def _initial_state(candidate: dict[str, Any], dry_run: bool, *, mode: str, skip_github: bool, skip_gupy: bool, skip_description: bool) -> dict[str, Any]:
    persisted_validated_url = str(candidate.get("website_url") or candidate.get("website") or candidate.get("validated_url") or "").strip() or None
    return {
        "candidate": candidate,
        "errors": {},
        "dry_run": dry_run,
        "mode": mode,
        "run_identity_phase": mode in {"identity-only", "full"},
        "run_deep_enrichment": mode in {"deep", "full"},
        "run_deep_only": mode == "deep",
        "skip_github": skip_github,
        "skip_gupy": skip_gupy,
        "skip_description": skip_description,
        "evidence_urls": [],
        "source_candidates": [],
        "candidate_urls_queue": [],
        "candidate_attempts": [],
        "validated_sources": [],
        "rejected_sources": [],
        "validated_source": {},
        "validated_url": persisted_validated_url,
        "discard_reason": None,
        "is_active": bool(candidate.get("is_active", True)),
        "identity_evidence": {},
        "web_context": {},
        "raw_texts": {},
        "tech_signals": {},
        "ai_signals": [],
        "open_jobs_signals": [],
        "github_profile": {},
        "github_candidatos_testados": [],
        "github_tentativas": 0,
        "github_repo_validado": None,
        "github_validacao_status": "pendente",
        "github_validacao_evidencia": None,
        "github_validacao_criterios": [],
        "github_stack_evidence": [],
        "dados_insuficientes": [],
        "gupy_profile": {},
        "timings": {},
        "skipped_sources": [],
        "cache_hit": False,
        "cache_source": None,
    }


def _is_recent(candidate: dict[str, Any]) -> bool:
    raw = candidate.get("last_enriched_at")
    if not raw:
        return False
    try:
        dt = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
    except ValueError:
        return False
    return datetime.now(UTC) - dt < timedelta(hours=config.RECENT_ENRICHMENT_MAX_HOURS)


def run(
    limit: int | None = None,
    company_id: str | None = None,
    status: str | None = None,
    dry_run: bool = False,
    reset_checkpoint: bool = False,
    mode: str = "full",
    max_seconds_per_company: float | None = None,
    skip_github: bool = False,
    skip_gupy: bool = False,
    skip_description: bool = False,
    no_cache: bool = False,
) -> dict[str, Any]:
    effective_status = "APPROVED" if mode == "deep" and status is None else status
    candidates = load_candidates(limit=limit, company_id=company_id, status=effective_status)
    checkpoint = _load_checkpoint(reset=reset_checkpoint)
    processed = checkpoint.setdefault("processed", {})
    failed = checkpoint.setdefault("failed", {})
    aggregate: dict[str, Any] = {
        "total": 0,
        "APPROVED": 0,
        "REVIEW": 0,
        "REJECTED": 0,
        "DISCARDED": 0,
        "AI_NATIVE": 0,
        "AI_ENABLED": 0,
        "NON_AI": 0,
        "MATCH": 0,
        "POSSIBLE_MATCH": 0,
        "WRONG_COMPANY": 0,
        "INSUFFICIENT_EVIDENCE": 0,
        "enriched": 0,
        "needs_review": 0,
        "insufficient_evidence": 0,
        "error": 0,
        "confidence_H": 0,
        "confidence_M": 0,
        "confidence_L": 0,
        "updated": 0,
        "dry_run": dry_run,
        "errors_by_source": {},
        "checkpoint_path": str(config.CHECKPOINT_PATH),
        "skipped_by_checkpoint": 0,
    }

    _print_progress(f"[enrichment] candidatos carregados: {len(candidates)}")
    if reset_checkpoint:
        _print_progress("[enrichment] checkpoint reiniciado")

    processed_since_checkpoint = 0
    dry_run_rows: list[dict[str, Any]] = []
    claimed_urls: set[str] = set()
    for index, candidate in enumerate(candidates, start=1):
        if _is_recent(candidate) and not company_id:
            aggregate["skipped_by_checkpoint"] += 1
            _print_progress(f"[enrichment] [{index}/{len(candidates)}] pulando recente: {_candidate_label(candidate)}")
            continue
        key = _candidate_key(candidate)
        label = _candidate_label(candidate)
        if key in processed and not company_id and not dry_run:
            aggregate["skipped_by_checkpoint"] += 1
            _print_progress(f"[enrichment] [{index}/{len(candidates)}] pulando checkpoint: {label}")
            continue
        _print_progress(f"[enrichment] [{index}/{len(candidates)}] iniciando: {label}")
        result: dict[str, Any] = {}
        started = perf_counter()
        try:
            cached = None if no_cache or dry_run or mode == "identity-only" else cache_load("company", key)
            if cached:
                result.update(cached)
                result["cache_hit"] = True
                result["cache_source"] = "local"
            else:
                initial_state = _initial_state(candidate, dry_run, mode=mode, skip_github=skip_github, skip_gupy=skip_gupy, skip_description=skip_description)
                initial_state["claimed_urls"] = sorted(claimed_urls)
                for step in enrichment_graph.stream(initial_state):
                    if isinstance(step, dict):
                        for _, update in step.items():
                            if isinstance(update, dict):
                                result.update(update)
                                if "log_summary" in update and isinstance(update["log_summary"], dict):
                                    result["log_summary"] = update["log_summary"]
                                if "log_result" in update and isinstance(update["log_result"], dict):
                                    nested = update["log_result"]
                                    result.update(nested)
                                    if isinstance(nested.get("log_summary"), dict):
                                        result["log_summary"] = nested["log_summary"]
                if not no_cache and not dry_run and mode != "identity-only":
                    cache_save("company", key, result)
            if mode == "identity-only":
                result["cache_hit"] = False
                result["cache_source"] = None
        except Exception as error:
            failed[key] = {"company_name": label, "error": str(error), "failed_at": datetime.now(UTC).isoformat()}
            if not dry_run:
                _save_checkpoint(checkpoint)
            raise
        _merge_summary(aggregate, result.get("log_summary", {}))
        status_name = str(
            result.get("classification", {}).get("validation_status")
            or result.get("ai_classification", {}).get("classification", {}).get("validation_status")
            or result.get("final_status")
            or "REVIEW"
        )
        identity_classification = str(result.get("identity_validation", {}).get("classification") or "INSUFFICIENT_EVIDENCE")
        confidence = result.get("identity_confidence_score") or result.get("identity_validation", {}).get("confidence") or 0
        validated_url = str(result.get("validated_url") or result.get("best_url_confirmed") or "")
        website_candidate = str(result.get("website_candidate") or "")
        reason = str(result.get("final_reason") or result.get("classification", {}).get("rejection_reason") or "no reliable company-specific source found")
        elapsed = round(perf_counter() - started, 2)
        candidate_urls = result.get("candidate_urls_evaluated") or []
        if validated_url:
            claimed_urls.add(validated_url)
        _print_progress(
            f"[enrichment] [{index}/{len(candidates)}] {label} | {status_name} | {identity_classification} | {confidence} | {validated_url or '-'} | {website_candidate or '-'} | {reason} | {elapsed}s"
        )
        for attempt in candidate_urls:
            if not isinstance(attempt, dict):
                continue
            _print_progress(
                f"[enrichment] [{index}/{len(candidates)}] url_index={attempt.get('url_index')} url={attempt.get('url')} classification={attempt.get('classification')} confidence={attempt.get('confidence')} decision={attempt.get('decision')}"
            )
        payload_preview = result.get("update_payload_preview") or {}
        if payload_preview:
            _print_progress(
                "[enrichment] "
                f"[{index}/{len(candidates)}] payload "
                f"candidate_id={payload_preview.get('candidate_id')} "
                f"validated_url={payload_preview.get('validated_url') or '-'} "
                f"website_candidate={payload_preview.get('website_candidate') or '-'} "
                f"website_confidence={payload_preview.get('website_confidence')} "
                f"identity_confidence_score={payload_preview.get('identity_confidence_score')} "
                f"validated_urls_count={payload_preview.get('validated_urls_count', 0)} "
                f"candidate_urls_count={payload_preview.get('candidate_urls_count', 0)} "
                f"rejected_urls_count={payload_preview.get('rejected_urls_count', 0)}"
            )
        if dry_run:
            dry_run_rows.append({
                "company_name": label,
                "status": status_name,
                "classification": identity_classification,
                "confidence": confidence,
                "validated_url": validated_url,
                "website_candidate": website_candidate,
                "attempts": len(candidate_urls),
                "reason": reason,
            })
        if not dry_run:
            processed[key] = {
                "company_name": label,
                "validation_status": status_name,
                "processed_at": datetime.now(UTC).isoformat(),
            }
            failed.pop(key, None)
            processed_since_checkpoint += 1
            if processed_since_checkpoint >= config.CHECKPOINT_EVERY:
                _save_checkpoint(checkpoint)
                processed_since_checkpoint = 0
        _print_progress(f"[enrichment] [{index}/{len(candidates)}] concluido: {label} ({status_name})")

    if not dry_run:
        _save_checkpoint(checkpoint)
        _print_progress(f"[enrichment] checkpoint salvo ({len(processed)} processados)")
    else:
        _print_progress("[enrichment] dry-run: checkpoint nao foi alterado")
        if dry_run_rows:
            print(_format_table([
                {
                    "company_name": row["company_name"],
                    "status": row["status"],
                    "classification": row["classification"],
                    "confidence": row["confidence"],
                    "validated_url": row["validated_url"],
                    "website_candidate": row["website_candidate"],
                    "attempts": row["attempts"],
                    "reason": row["reason"],
                }
                for row in dry_run_rows
            ]))
    if aggregate.get("review_reasons"):
        aggregate["review_reason_counts"] = aggregate.pop("review_reasons")
    return aggregate


def main() -> None:
    parser = argparse.ArgumentParser(description="Enrich validated startup candidates with identity validation and technical signals.")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--company-id")
    parser.add_argument("--status", choices=["APPROVED", "REVIEW", "REJECTED", "DISCARDED"])
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--reset-checkpoint", action="store_true")
    parser.add_argument("--mode", choices=["identity-only", "deep", "full"], default="full")
    parser.add_argument("--max-seconds-per-company", type=float, default=None)
    parser.add_argument("--skip-github", action="store_true")
    parser.add_argument("--skip-gupy", action="store_true")
    parser.add_argument("--skip-description", action="store_true")
    parser.add_argument("--no-cache", action="store_true")
    args = parser.parse_args()
    print(
        json.dumps(
            run(
                limit=args.limit,
                company_id=args.company_id,
                status=args.status,
                dry_run=args.dry_run,
                reset_checkpoint=args.reset_checkpoint,
                mode=args.mode,
                max_seconds_per_company=args.max_seconds_per_company,
                skip_github=args.skip_github,
                skip_gupy=args.skip_gupy,
                skip_description=args.skip_description,
                no_cache=args.no_cache,
            ),
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
