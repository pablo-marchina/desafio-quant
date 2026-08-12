#!/usr/bin/env python3
"""W2C-SV-v1.0 deterministic performance-blind semantic validation.

Reads only the frozen W2C discovery candidate queue and semantic protocol.
Never reads model/economic performance, IAS scores, F1-F9 outcomes, or linked-
asset realized returns.
"""
from __future__ import annotations
import csv, gzip, hashlib, io, json, re
from collections import defaultdict
from pathlib import Path

PROTOCOL = Path("registry/w2c_semantic_validation_protocol_v1_0.json")
INPUT = Path("registry/w2c_discovery_validation_queue.csv.gz")
OUT_EVENTS = Path("registry/w2c_semantic_validation_events.csv.gz")
OUT_CLUSTERS = Path("registry/w2c_semantic_validation_clusters.csv.gz")
OUT_REVIEW = Path("registry/w2c_semantic_review_queue.csv.gz")
OUT_SUMMARY = Path("registry/w2c_semantic_validation_summary.json")
EXPECTED = "W2C-SV-v1.0"

RX = {
    "EARNINGS_EPS": [re.compile(r"\b(earnings|eps|earnings per share)\b", re.I)],
    "FDA_ADVISORY_COMMITTEE": [
        re.compile(r"\b(fda|food and drug administration|drug|biologic)\b", re.I),
        re.compile(r"\b(advisory committee|adcom|advisory panel|panel vote)\b", re.I),
    ],
    "FDA_FINAL_PDUFA_DECISION": [
        re.compile(r"\b(fda|food and drug administration|pdufa)\b", re.I),
        re.compile(r"\b(approval|approve|decision|action date|complete response|crl|authorize|authorization)\b", re.I),
    ],
    "MA_PRE_ANNOUNCEMENT_OR_RUMOR": [
        re.compile(r"\b(merger|acquisition|acquire|takeover|buyout|bid)\b", re.I),
        re.compile(r"\b(rumou?r|announce|announcement|offer|bid|acquire)\b", re.I),
    ],
    "MA_PENDING_COMPLETION": [
        re.compile(r"\b(merger|acquisition|deal|takeover|buyout|transaction)\b", re.I),
        re.compile(r"\b(close|closing|complete|completion|shareholder vote|tender offer|outside date|terminate|termination)\b", re.I),
    ],
    "MA_REGULATORY_CLEARANCE": [
        re.compile(r"\b(merger|acquisition|deal|transaction)\b", re.I),
        re.compile(r"\b(ftc|doj|cma|european commission|antitrust|regulatory|competition)\b", re.I),
        re.compile(r"\b(approve|approval|clear|clearance|block|challenge|second request|phase 2)\b", re.I),
    ],
    "ANTITRUST_ENFORCEMENT_SINGLE_NAME": [
        re.compile(r"\b(antitrust|ftc|doj|competition regulator|competition authority|monopoly)\b", re.I),
        re.compile(r"\b(lawsuit|sue|trial|case|ruling|fine|settlement|investigation|enforcement|injunction)\b", re.I),
    ],
    "FOMC_DECISION": [
        re.compile(r"\b(fomc|federal reserve|fed)\b", re.I),
        re.compile(r"\b(rate|target range|decision|cut|hike|hold|basis point)\b", re.I),
    ],
    "MACRO_STATISTICAL_RELEASE": [
        re.compile(r"\b(cpi|consumer price index|ppi|producer price index|nonfarm payrolls?|payrolls?|jobs report|employment situation|gdp|gross domestic product|retail sales|unemployment rate)\b", re.I),
    ],
    "CORPORATE_LITIGATION_BINARY": [
        re.compile(r"\b(court|lawsuit|verdict|injunction|settlement|ruling|trial|appeal)\b", re.I),
    ],
}

MNA = re.compile(r"\b(merger|acquisition|deal|transaction|takeover|buyout)\b", re.I)
REG = re.compile(r"\b(ftc|doj|cma|european commission|antitrust|regulatory clearance|competition authority)\b", re.I)
ADVISORY = re.compile(r"\b(advisory committee|adcom|advisory panel|panel vote)\b", re.I)
FINAL_FDA = re.compile(r"\b(pdufa|final fda|fda approval|complete response|crl|action date)\b", re.I)
MACRO = re.compile(r"\b(cpi|consumer price index|ppi|payroll|jobs report|employment situation|gdp|retail sales|unemployment rate)\b", re.I)
FEDPOL = re.compile(r"\b(fomc|federal reserve|fed)\b.*\b(rate|target range|cut|hike|hold|decision)\b", re.I)
LIT = re.compile(r"\b(court|lawsuit|verdict|injunction|settlement|ruling|trial|appeal)\b", re.I)


def strict_matches(text: str) -> set[str]:
    hits = {fam for fam, pats in RX.items() if all(p.search(text) for p in pats)}
    # Frozen exclusions.
    if "EARNINGS_EPS" in hits and re.search(r"\b(fda|pdufa|fomc|cpi|merger|acquisition|antitrust|court|lawsuit)\b", text, re.I):
        hits.remove("EARNINGS_EPS")
    if "FDA_FINAL_PDUFA_DECISION" in hits and ADVISORY.search(text) and not FINAL_FDA.search(text):
        hits.remove("FDA_FINAL_PDUFA_DECISION")
    if "MA_PRE_ANNOUNCEMENT_OR_RUMOR" in hits and re.search(r"\b(close|closing|completion|shareholder vote|tender offer|ftc|doj|cma|antitrust|regulatory clearance|competition authority)\b", text, re.I):
        hits.remove("MA_PRE_ANNOUNCEMENT_OR_RUMOR")
    if "MA_PENDING_COMPLETION" in hits and REG.search(text):
        hits.remove("MA_PENDING_COMPLETION")
    if "ANTITRUST_ENFORCEMENT_SINGLE_NAME" in hits and MNA.search(text):
        hits.remove("ANTITRUST_ENFORCEMENT_SINGLE_NAME")
    if "FOMC_DECISION" in hits and MACRO.search(text):
        hits.remove("FOMC_DECISION")
    if "MACRO_STATISTICAL_RELEASE" in hits and FEDPOL.search(text):
        hits.remove("MACRO_STATISTICAL_RELEASE")
    if "CORPORATE_LITIGATION_BINARY" in hits and re.search(r"\b(antitrust|ftc|doj|merger|acquisition|pdufa|fda approval)\b", text, re.I):
        hits.remove("CORPORATE_LITIGATION_BINARY")
    return hits

DOMAIN = {
    "EARNINGS_EPS":"earnings",
    "FDA_ADVISORY_COMMITTEE":"fda", "FDA_FINAL_PDUFA_DECISION":"fda",
    "MA_PRE_ANNOUNCEMENT_OR_RUMOR":"mna", "MA_PENDING_COMPLETION":"mna", "MA_REGULATORY_CLEARANCE":"mna",
    "ANTITRUST_ENFORCEMENT_SINGLE_NAME":"antitrust",
    "FOMC_DECISION":"macro", "MACRO_STATISTICAL_RELEASE":"macro",
    "CORPORATE_LITIGATION_BINARY":"litigation",
}
PRECEDENCE = {
    "mna": ["MA_REGULATORY_CLEARANCE", "MA_PENDING_COMPLETION", "MA_PRE_ANNOUNCEMENT_OR_RUMOR"],
    "fda": ["FDA_FINAL_PDUFA_DECISION", "FDA_ADVISORY_COMMITTEE"],
    "macro": ["FOMC_DECISION", "MACRO_STATISTICAL_RELEASE"],
}


def resolve(hits: set[str]) -> tuple[str, str]:
    if not hits:
        return "INVALID_NO_STRICT_FAMILY", ""
    if len(hits) == 1:
        return "VALID_UNIQUE_FAMILY", next(iter(hits))
    domains = {DOMAIN[h] for h in hits}
    if len(domains) == 1 and next(iter(domains)) in PRECEDENCE:
        order = PRECEDENCE[next(iter(domains))]
        for fam in order:
            if fam in hits:
                return "REASSIGNED_BY_FROZEN_PRECEDENCE", fam
    # Antitrust/litigation shared vocabulary: strict antitrust wins only when litigation is the only other hit.
    if hits == {"ANTITRUST_ENFORCEMENT_SINGLE_NAME", "CORPORATE_LITIGATION_BINARY"}:
        return "REASSIGNED_BY_FROZEN_PRECEDENCE", "ANTITRUST_ENFORCEMENT_SINGLE_NAME"
    return "AMBIGUOUS_MULTI_FAMILY", ""


def norm_subject(title: str) -> str:
    s = title.lower()
    s = re.sub(r"https?://\S+", " ", s)
    s = re.sub(r"[$€£]?\d+(?:[.,]\d+)?%?", " <num> ", s)
    s = re.sub(r"\b(yes|no|will|would|before|after|above|below|at least|more than|less than|between|by)\b", " ", s)
    s = re.sub(r"\b(probability|chance|odds|market)\b", " ", s)
    s = re.sub(r"[^a-z0-9<>]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def cluster_id(family: str, end_utc: str, title: str) -> str:
    day = (end_utc or "")[:10] or "NO_DATE"
    basis = f"{family}|{day}|{norm_subject(title)}"
    return hashlib.sha256(basis.encode()).hexdigest()[:24]


def gz_read(path: Path) -> list[dict]:
    with gzip.open(path, "rt", encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def gz_write(path: Path, rows: list[dict], fields: list[str]) -> None:
    sio = io.StringIO(newline="")
    w = csv.DictWriter(sio, fieldnames=fields, extrasaction="ignore")
    w.writeheader(); w.writerows(rows)
    data = sio.getvalue().encode()
    with path.open("wb") as fh:
        with gzip.GzipFile(filename="", mode="wb", fileobj=fh, mtime=0) as gz:
            gz.write(data)


def main() -> None:
    protocol = json.loads(PROTOCOL.read_text(encoding="utf-8"))
    assert protocol["version"] == EXPECTED
    assert protocol["performance_blind"] is True
    rows = gz_read(INPUT)
    by_event: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        eid = str(r.get("event_id") or "")
        if eid:
            by_event[eid].append(r)

    events: list[dict] = []
    for eid in sorted(by_event, key=lambda x: (len(x), x)):
        rs = by_event[eid]
        r0 = rs[0]
        nominees = sorted({r.get("family", "") for r in rs if r.get("family")})
        text = " \n ".join(str(r0.get(k) or "") for k in ("title","slug","resolution_source","tags","queries_matched"))
        hits = strict_matches(text)
        status, fam = resolve(hits)
        cid = cluster_id(fam, str(r0.get("end_utc") or ""), str(r0.get("title") or "")) if fam else ""
        events.append({
            "event_id": eid,
            "title": r0.get("title", ""),
            "slug": r0.get("slug", ""),
            "start_utc": r0.get("start_utc", ""),
            "end_utc": r0.get("end_utc", ""),
            "resolution_source": r0.get("resolution_source", ""),
            "tags": r0.get("tags", ""),
            "series_ids": r0.get("series_ids", ""),
            "nominated_families": "|".join(nominees),
            "strict_matches": "|".join(sorted(hits)),
            "semantic_status": status,
            "resolved_family": fam,
            "independence_cluster_id": cid,
            "cluster_representative": "false",
            "review_selected": "false",
            "review_reason": ""
        })

    members: dict[tuple[str,str], list[dict]] = defaultdict(list)
    for e in events:
        if e["resolved_family"] and e["semantic_status"] in {"VALID_UNIQUE_FAMILY","REASSIGNED_BY_FROZEN_PRECEDENCE"}:
            members[(e["resolved_family"], e["independence_cluster_id"])].append(e)

    clusters: list[dict] = []
    valid_cluster_rows: dict[str, list[dict]] = defaultdict(list)
    for (fam,cid), ms in sorted(members.items()):
        rep = min(ms, key=lambda e: hashlib.sha256(e["event_id"].encode()).hexdigest())
        rep["cluster_representative"] = "true"
        for e in ms:
            if e is not rep:
                e["semantic_status"] = "DUPLICATE_INDEPENDENCE_CLUSTER"
        c = {
            "family": fam,
            "independence_cluster_id": cid,
            "representative_event_id": rep["event_id"],
            "member_count": len(ms),
            "member_event_ids": "|".join(sorted(e["event_id"] for e in ms)),
            "title": rep["title"],
            "end_utc": rep["end_utc"],
            "review_selected": "false"
        }
        clusters.append(c); valid_cluster_rows[fam].append(c)

    target = int(protocol["deterministic_review_queue"]["target_valid_clusters_per_family"])
    selected_keys: set[tuple[str,str]] = set()
    for fam, cs in valid_cluster_rows.items():
        ordered = sorted(cs, key=lambda c: hashlib.sha256(f"{fam}|{c['independence_cluster_id']}".encode()).hexdigest())
        for c in ordered[:target]:
            c["review_selected"] = "true"
            selected_keys.add((fam,c["independence_cluster_id"]))
    for e in events:
        if (e["resolved_family"], e["independence_cluster_id"]) in selected_keys and e["cluster_representative"] == "true":
            e["review_selected"] = "true"; e["review_reason"] = "DETERMINISTIC_VALID_CLUSTER_SAMPLE"
        elif e["semantic_status"] == "AMBIGUOUS_MULTI_FAMILY":
            e["review_selected"] = "true"; e["review_reason"] = "AMBIGUOUS_REQUIRES_REVIEW"

    review = [e for e in events if e["review_selected"] == "true"]
    event_fields = ["event_id","title","slug","start_utc","end_utc","resolution_source","tags","series_ids","nominated_families","strict_matches","semantic_status","resolved_family","independence_cluster_id","cluster_representative","review_selected","review_reason"]
    cluster_fields = ["family","independence_cluster_id","representative_event_id","member_count","member_event_ids","title","end_utc","review_selected"]
    gz_write(OUT_EVENTS, events, event_fields); gz_write(OUT_CLUSTERS, clusters, cluster_fields); gz_write(OUT_REVIEW, review, event_fields)

    by_status = defaultdict(int); by_family = defaultdict(lambda: defaultdict(int))
    for e in events:
        by_status[e["semantic_status"]] += 1
        if e["resolved_family"]:
            by_family[e["resolved_family"]]["resolved_events"] += 1
            if e["cluster_representative"] == "true": by_family[e["resolved_family"]]["independent_clusters"] += 1
            if e["review_selected"] == "true": by_family[e["resolved_family"]]["review_selected"] += 1
    summary = {
        "artifact":"W2C_SEMANTIC_VALIDATION_RUN",
        "version":"W2C-SV-RUN-v1.0",
        "protocol_version":EXPECTED,
        "performance_blind":True,
        "science_reopened":False,
        "input_candidate_rows":len(rows),
        "unique_event_ids":len(events),
        "semantic_status_counts":dict(sorted(by_status.items())),
        "family_counts":{k:dict(v) for k,v in sorted(by_family.items())},
        "review_queue_rows":len(review),
        "ias_scores_computed":False,
        "feasibility_gates_scored":False,
        "linked_asset_realized_returns_read":False,
        "w3_family_selected":False,
        "interpretation":"Deterministic semantic validation only. Review-selected rows are a performance-blind evidence queue; no IAS/F1-F9/W3 conclusion is authorized."
    }
    OUT_SUMMARY.write_text(json.dumps(summary, indent=2, ensure_ascii=False)+"\n", encoding="utf-8")
    print(json.dumps(summary, indent=2))

if __name__ == "__main__":
    main()
