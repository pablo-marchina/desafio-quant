#!/usr/bin/env python3
from __future__ import annotations

import csv
import gzip
import hashlib
import html
import io
import json
import re
import time
import urllib.error
import urllib.request
from collections import Counter
from datetime import date, datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REG = ROOT / "registry"
SPEC = REG / "w4c_r1_fda_manual_adjudication_spec_v1.json"
QUEUE = REG / "w4c_r1_fda_review_queue_v1.json"
W4B = REG / "w4b_official_event_truth_summary_v1.json"
R1 = REG / "w4c_r1_official_truth_extension_summary_v1.json"
OUT_RECORDS = REG / "w4c_r1_fda_truth_extension_records_v1.csv.gz"
OUT_SOURCES = REG / "w4c_r1_fda_truth_extension_source_manifest_v1.csv.gz"
OUT_SUMMARY = REG / "w4c_r1_fda_truth_extension_summary_v1.json"
UA = "desafio-quant-w4c-r1-fda/1.0 primary-evidence-capture"


def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def norm_text(s: str) -> str:
    s = html.unescape(s)
    s = re.sub(r"<script\b[^>]*>.*?</script>", " ", s, flags=re.I | re.S)
    s = re.sub(r"<style\b[^>]*>.*?</style>", " ", s, flags=re.I | re.S)
    s = re.sub(r"<[^>]+>", " ", s)
    s = re.sub(r"\s+", " ", s).strip().lower()
    return s


def fetch(url: str) -> tuple[bytes, int, str]:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": UA,
            "Accept": "text/html,application/xhtml+xml;q=0.9,*/*;q=0.1",
            "Accept-Encoding": "identity",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=40) as r:
            return r.read(), int(r.status), str(r.headers.get("Content-Type", ""))
    except urllib.error.HTTPError as e:
        return e.read(), int(e.code), str(e.headers.get("Content-Type", ""))
    except Exception:
        return b"", 0, ""


def official_id(family: str, d: str, subject: str) -> str:
    h = hashlib.sha256(f"{family}|{d}|{subject}".encode("utf-8")).hexdigest()[:20]
    return "W4OT1-" + h


def excerpt_hash(text: str, anchor: str) -> str:
    i = text.find(anchor.lower())
    if i < 0:
        return ""
    a = max(0, i - 500)
    b = min(len(text), i + len(anchor) + 500)
    return hashlib.sha256(text[a:b].encode("utf-8")).hexdigest()


def write_gzip_csv(path: Path, rows: list[dict], fields: list[str]) -> None:
    raw = io.StringIO(newline="")
    w = csv.DictWriter(raw, fieldnames=fields, lineterminator="\n")
    w.writeheader()
    for r in rows:
        w.writerow({k: r.get(k, "") for k in fields})
    data = raw.getvalue().encode("utf-8")
    with path.open("wb") as fh:
        with gzip.GzipFile(filename=path.stem, mode="wb", fileobj=fh, mtime=0) as gz:
            gz.write(data)


def main() -> None:
    spec = json.loads(SPEC.read_text(encoding="utf-8"))
    queue = json.loads(QUEUE.read_text(encoding="utf-8"))
    w4b = json.loads(W4B.read_text(encoding="utf-8"))
    r1 = json.loads(R1.read_text(encoding="utf-8"))

    assert spec["gate_decision"] == "PASS_W4C_R1_FDA_MANUAL_ADJUDICATION_SPEC_FROZEN"
    assert queue["gate_decision"] == "PASS_W4C_R1_FDA_QUEUE_FROZEN"
    assert queue["groups"] == 22 and len(queue["rows"]) == 22
    assert w4b["verified_unique_official_events"] == 344
    assert "FDA_FINAL_PDUFA_DECISION" not in w4b["verified_family_counts"]
    assert r1["marginal_new_unique_official_events_vs_w4b"] == 6
    assert r1["immutable_w4b_unique_official_events"] == 344

    qmap = {r["exact_group_id"]: r for r in queue["rows"]}
    cmap = {r["exact_group_id"]: r for r in spec["candidate_verified_groups"]}
    assert len(qmap) == 22 and len(cmap) == spec["candidate_count"] == 7
    assert set(cmap).issubset(qmap)

    retrieved_at = datetime.now(timezone.utc).isoformat()
    cache: dict[str, dict] = {}
    source_rows: list[dict] = []
    records: list[dict] = []

    for gid, q in sorted(qmap.items()):
        base = {
            "exact_group_id": gid,
            "resolved_family": q["resolved_family"],
            "pretruth_event_reference_date": q["pretruth_event_reference_date"],
            "pretruth_subject_key": q["pretruth_subject_key"],
            "venues": q["venues"],
            "review_mode": spec["review_mode"],
        }
        if gid not in cmap:
            records.append({
                **base,
                "r1_verification_state": "UNRESOLVED_R1_OFFICIAL_TRUTH",
                "official_event_id": "",
                "official_event_reference_date": "",
                "official_event_timestamp_utc_if_published": "",
                "official_subject_key": "",
                "source_authority": "FDA",
                "source_url": "",
                "retrieved_at_utc": "",
                "source_body_sha256_or_document_hash_when_retrievable": "",
                "evidence_excerpt_hash_or_structured_field_reference": "",
                "verification_reason": spec["remaining_groups_policy"]["reason"],
                "reference_date_delta_days": "",
                "match_rule_used": "FDA fail-closed common match rule",
                "alias_to_existing_w4b_official_event": False,
            })
            continue

        c = cmap[gid]
        url = c["source_url"]
        if url not in cache:
            body, status, ctype = fetch(url)
            text = norm_text(body.decode("utf-8", errors="replace"))
            cache[url] = {"body": body, "status": status, "ctype": ctype, "text": text}
            source_rows.append({
                "source_authority": "FDA",
                "source_url": url,
                "retrieved_at_utc": retrieved_at,
                "http_status": status,
                "content_type": ctype,
                "response_bytes": len(body),
                "source_body_sha256_or_document_hash": sha256_bytes(body) if body else "",
                "purpose": "W4C_R1_FDA_PRIMARY_OCCURRENCE_EVIDENCE",
            })
            time.sleep(1.0)
        x = cache[url]
        required = [norm_text(t) for t in c["required_all_text_tokens"]]
        matched = x["status"] == 200 and all(t in x["text"] for t in required)
        if not matched:
            missing = [t for t in required if t not in x["text"]]
            records.append({
                **base,
                "r1_verification_state": "UNRESOLVED_R1_OFFICIAL_TRUTH",
                "official_event_id": "",
                "official_event_reference_date": "",
                "official_event_timestamp_utc_if_published": "",
                "official_subject_key": "",
                "source_authority": "FDA",
                "source_url": url,
                "retrieved_at_utc": retrieved_at,
                "source_body_sha256_or_document_hash_when_retrievable": sha256_bytes(x["body"]) if x["body"] else "",
                "evidence_excerpt_hash_or_structured_field_reference": "",
                "verification_reason": f"Fail closed: primary FDA evidence capture did not satisfy frozen body gate (http={x['status']}; missing_token_count={len(missing)})",
                "reference_date_delta_days": "",
                "match_rule_used": c["match_rule_used"],
                "alias_to_existing_w4b_official_event": False,
            })
            continue

        od = c["official_event_reference_date"]
        delta = (date.fromisoformat(od) - date.fromisoformat(q["pretruth_event_reference_date"])).days
        oid = official_id(q["resolved_family"], od, c["official_subject_key"])
        records.append({
            **base,
            "r1_verification_state": "VERIFIED_R1_OFFICIAL_TRUTH",
            "official_event_id": oid,
            "official_event_reference_date": od,
            "official_event_timestamp_utc_if_published": "",
            "official_subject_key": c["official_subject_key"],
            "source_authority": "FDA",
            "source_url": url,
            "retrieved_at_utc": retrieved_at,
            "source_body_sha256_or_document_hash_when_retrievable": sha256_bytes(x["body"]),
            "evidence_excerpt_hash_or_structured_field_reference": excerpt_hash(x["text"], required[0]),
            "verification_reason": "Primary FDA body supports one uniquely identified product/action occurrence under the frozen FDA rule; regulatory direction was not used for route selection.",
            "reference_date_delta_days": delta,
            "match_rule_used": c["match_rule_used"],
            "alias_to_existing_w4b_official_event": False,
        })

    assert len(records) == 22 and len({r["exact_group_id"] for r in records}) == 22
    states = Counter(r["r1_verification_state"] for r in records)
    verified = [r for r in records if r["r1_verification_state"] == "VERIFIED_R1_OFFICIAL_TRUTH"]
    unique_ids = {r["official_event_id"] for r in verified}
    assert len(unique_ids) == len(verified)

    fields = [
        "exact_group_id","resolved_family","pretruth_event_reference_date","pretruth_subject_key","venues",
        "r1_verification_state","official_event_id","official_event_reference_date",
        "official_event_timestamp_utc_if_published","official_subject_key","source_authority","source_url",
        "retrieved_at_utc","source_body_sha256_or_document_hash_when_retrievable",
        "evidence_excerpt_hash_or_structured_field_reference","verification_reason","review_mode",
        "reference_date_delta_days","match_rule_used","alias_to_existing_w4b_official_event"
    ]
    write_gzip_csv(OUT_RECORDS, records, fields)
    source_fields = ["source_authority","source_url","retrieved_at_utc","http_status","content_type","response_bytes","source_body_sha256_or_document_hash","purpose"]
    write_gzip_csv(OUT_SOURCES, source_rows, source_fields)

    fda_gain = len(unique_ids)
    cumulative_gain = int(r1["marginal_new_unique_official_events_vs_w4b"]) + fda_gain
    summary = {
        "artifact": "W4C_R1_FDA_TRUTH_EXTENSION_SUMMARY",
        "version": "W4C-R1-FDA-RESULT-v1.0",
        "date_utc": retrieved_at,
        "science_reopened": False,
        "queue_groups": 22,
        "decision_rows_accounted": 22,
        "verification_state_counts": dict(sorted(states.items())),
        "verified_exact_groups": len(verified),
        "verified_unique_official_events": len(unique_ids),
        "marginal_new_unique_official_events_vs_immutable_w4b": fda_gain,
        "prior_r1_v1_marginal_new_unique_events": int(r1["marginal_new_unique_official_events_vs_w4b"]),
        "cumulative_r1_marginal_new_unique_events": cumulative_gain,
        "immutable_w4b_unique_official_events": 344,
        "cumulative_w4b_plus_r1_truth_unique_events": 344 + cumulative_gain,
        "cumulative_count_is_n_final_backtestable": False,
        "source_manifest_rows": len(source_rows),
        "all_verified_rows_have_fda_body_hash": all(bool(r["source_body_sha256_or_document_hash_when_retrievable"]) for r in verified),
        "all_verified_rows_have_excerpt_hash": all(bool(r["evidence_excerpt_hash_or_structured_field_reference"]) for r in verified),
        "manual_or_model_review_disclosed": True,
        "performance_blind": True,
        "linked_asset_realized_returns_read": False,
        "prediction_market_performance_read": False,
        "prediction_market_settlement_results_read": False,
        "ARGOS_PnL_read": False,
        "family_reclassification_used": False,
        "matching_rule_changed_after_r1_v1": False,
        "w4b_artifacts_modified": False,
        "n_final_backtestable_authorized": False,
        "outcome_reveal_authorized": False,
        "gate_decision": "PASS_W4C_R1_FDA_TRUTH_EXTENSION_MATERIALIZED"
    }
    OUT_SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
