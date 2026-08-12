#!/usr/bin/env python3
"""Synthetic adversarial validation for W2C-SV-v1.0."""
from __future__ import annotations
import importlib.util, json
from pathlib import Path

SCRIPT = Path("scripts/w2c_semantic_validation_v1_0.py")
PROTOCOL = Path("registry/w2c_semantic_validation_protocol_v1_0.json")
spec = importlib.util.spec_from_file_location("sv", SCRIPT)
sv = importlib.util.module_from_spec(spec); assert spec.loader; spec.loader.exec_module(sv)
p = json.loads(PROTOCOL.read_text(encoding="utf-8"))
assert p["version"] == "W2C-SV-v1.0" and p["performance_blind"] is True

cases = [
("Apple EPS earnings for Q2?", "EARNINGS_EPS"),
("FDA advisory committee panel vote on Drug X?", "FDA_ADVISORY_COMMITTEE"),
("Will FDA approve Drug X by its PDUFA action date?", "FDA_FINAL_PDUFA_DECISION"),
("Will Company A announce an acquisition of Company B?", "MA_PRE_ANNOUNCEMENT_OR_RUMOR"),
("Will the announced Company A Company B merger close by June?", "MA_PENDING_COMPLETION"),
("Will the FTC approve the Company A Company B merger?", "MA_REGULATORY_CLEARANCE"),
("Will DOJ file an antitrust lawsuit against Company A?", "ANTITRUST_ENFORCEMENT_SINGLE_NAME"),
("Will the FOMC cut the target rate by 25 basis points?", "FOMC_DECISION"),
("Will CPI be above 3.0% in the next Consumer Price Index release?", "MACRO_STATISTICAL_RELEASE"),
("Will the court issue an injunction against Company A?", "CORPORATE_LITIGATION_BINARY"),
]
passed = 0
for text, expected in cases:
    st, fam = sv.resolve(sv.strict_matches(text))
    assert fam == expected, (text, st, fam, expected)
    passed += 1

# Negative/edge attacks.
neg = [
"Will Apple stock rise 5% tomorrow?",
"Will Bitcoin hit 100k?",
"Will the President sign the bill?",
]
for text in neg:
    st, fam = sv.resolve(sv.strict_matches(text)); assert st == "INVALID_NO_STRICT_FAMILY" and not fam; passed += 1

# Precedence and exclusion attacks.
text = "Will the FTC grant regulatory clearance so the announced merger can close?"
st, fam = sv.resolve(sv.strict_matches(text)); assert fam == "MA_REGULATORY_CLEARANCE"; passed += 1
text = "Will the FDA advisory committee panel vote yes before the later final FDA approval?"
st, fam = sv.resolve(sv.strict_matches(text)); assert fam == "FDA_FINAL_PDUFA_DECISION"; passed += 1
# A composite CPI+FOMC question is intentionally rejected fail-closed rather than forced into either family.
text = "Will CPI rise and will the FOMC cut rates?"
st, fam = sv.resolve(sv.strict_matches(text)); assert st == "INVALID_NO_STRICT_FAMILY" and not fam; passed += 1
text = "Will DOJ block the merger in an antitrust lawsuit?"
hits = sv.strict_matches(text); assert "ANTITRUST_ENFORCEMENT_SINGLE_NAME" not in hits; passed += 1
text = "Will Company A announce earnings and acquire Company B?"
st, fam = sv.resolve(sv.strict_matches(text)); assert st == "AMBIGUOUS_MULTI_FAMILY" and not fam; passed += 1

# Independence clustering attacks: thresholds within same event/day collapse; dates remain distinct.
c1 = sv.cluster_id("MACRO_STATISTICAL_RELEASE", "2026-08-12T13:30:00Z", "Will CPI be above 3.0%?")
c2 = sv.cluster_id("MACRO_STATISTICAL_RELEASE", "2026-08-12T13:30:00Z", "Will CPI be above 4.0%?")
assert c1 == c2; passed += 1
c3 = sv.cluster_id("MACRO_STATISTICAL_RELEASE", "2026-09-11T13:30:00Z", "Will CPI be above 3.0%?")
assert c1 != c3; passed += 1
assert sv.cluster_id("FOMC_DECISION", "2026-09-16T18:00:00Z", "Will FOMC cut rates by 25 bps?") != sv.cluster_id("MACRO_STATISTICAL_RELEASE", "2026-09-16T18:00:00Z", "Will CPI be above 3%?"); passed += 1

# Firewall attack: protocol must explicitly ban all performance-bearing inputs.
for forbidden in ["ARGOS PnL","Brier","log loss","linked-asset realized returns"]:
    assert forbidden in p["forbidden_inputs"]; passed += 1
assert p["deterministic_review_queue"]["performance_based_sampling_forbidden"] is True; passed += 1
assert p["acceptance_for_downstream_pit"]["ambiguous_allowed"] is False; passed += 1
assert p["independence_cluster"]["multi_market_event_rule"].startswith("Multiple markets"); passed += 1

summary = {"artifact":"W2C_SEMANTIC_SYNTHETIC_VALIDATION","version":"W2C-SV-SYN-v1.0","passed":passed,"failed":0,"status":f"PASS_{passed}_OF_{passed}","real_candidate_data_read":False,"performance_data_read":False}
Path("registry/w2c_semantic_validation_synthetic_summary.json").write_text(json.dumps(summary,indent=2)+"\n",encoding="utf-8")
print(json.dumps(summary,indent=2))
