#!/usr/bin/env python3
"""Precision amendment wrapper for W2C-SV-v2.0 before any v2 real execution.

A1 generic DOJ/FTC != antitrust without explicit antitrust semantics.
A2 FDA inflected final-action verbs are recognized.
A3 title+slug '-'/'_' separators normalize to spaces.
A4 explicit cross-mechanism collisions are preserved as ambiguity instead of
being silently resolved by a hard-exclusion rule.
"""
from __future__ import annotations
import importlib.util,re
from pathlib import Path
BASE=Path('scripts/w2c_semantic_validation_v2_0.py')
spec=importlib.util.spec_from_file_location('sv2base',BASE);base=importlib.util.module_from_spec(spec);assert spec.loader;spec.loader.exec_module(base)
_orig=base.strict_matches
EXPLICIT_ANTITRUST=re.compile(r'\b(antitrust|competition authority|competition regulator|monopoly)\b',re.I)
FDA_ACTOR=re.compile(r'\b(fda|food and drug administration|pdufa)\b',re.I)
FDA_FINAL_ACTION=re.compile(r'\b(approve|approves|approval|approved|authorize|authorizes|authorization|emergency use authorization|eua|pdufa|action date|complete response|crl)\b',re.I)
FDA_ADVISORY=re.compile(r'\b(advisory committee|adcom|advisory panel|panel vote)\b',re.I)
EXPLICIT_EARNINGS=re.compile(r'\b(eps|earnings per share)\b|\b(beat|miss|report)\s+(?:quarterly\s+)?earnings\b',re.I)
def classification_text(row):
    raw=f"{row.get('title','')} {row.get('slug','')}".strip()
    return re.sub(r'[-_]+',' ',raw)
def strict_matches(text):
    hits=_orig(text)
    if 'ANTITRUST_ENFORCEMENT_SINGLE_NAME' in hits and not EXPLICIT_ANTITRUST.search(text):
        hits.remove('ANTITRUST_ENFORCEMENT_SINGLE_NAME')
    if FDA_ACTOR.search(text) and FDA_FINAL_ACTION.search(text):
        hits.add('FDA_FINAL_PDUFA_DECISION')
    if FDA_ADVISORY.search(text) and not FDA_FINAL_ACTION.search(text):
        hits.discard('FDA_FINAL_PDUFA_DECISION')
    # Preserve explicit cross-mechanism collision so resolver returns AMBIGUOUS.
    if EXPLICIT_EARNINGS.search(text) and any(h != 'EARNINGS_EPS' for h in hits):
        hits.add('EARNINGS_EPS')
    return hits
base.classification_text=classification_text
base.strict_matches=strict_matches
resolve=base.resolve
cluster_id=base.cluster_id
norm_subject=base.norm_subject
RULES=base.RULES
PROTOCOL=base.PROTOCOL
INPUT=base.INPUT
VERSION=base.VERSION
def main(): base.main()
if __name__=='__main__':main()
