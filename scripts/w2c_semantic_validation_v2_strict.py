#!/usr/bin/env python3
"""Precision amendment wrapper for W2C-SV-v2.0 before any v2 real execution.

It tightens ANTITRUST_ENFORCEMENT_SINGLE_NAME so generic DOJ/FTC investigations
cannot qualify without explicit antitrust/competition/monopoly language.
"""
from __future__ import annotations
import importlib.util,re
from pathlib import Path
BASE=Path('scripts/w2c_semantic_validation_v2_0.py')
spec=importlib.util.spec_from_file_location('sv2base',BASE);base=importlib.util.module_from_spec(spec);assert spec.loader;spec.loader.exec_module(base)
_orig=base.strict_matches
EXPLICIT_ANTITRUST=re.compile(r'\b(antitrust|competition authority|competition regulator|monopoly)\b',re.I)
def strict_matches(text):
    hits=_orig(text)
    if 'ANTITRUST_ENFORCEMENT_SINGLE_NAME' in hits and not EXPLICIT_ANTITRUST.search(text):
        hits.remove('ANTITRUST_ENFORCEMENT_SINGLE_NAME')
    return hits
base.strict_matches=strict_matches
classification_text=base.classification_text
resolve=base.resolve
cluster_id=base.cluster_id
norm_subject=base.norm_subject
RULES=base.RULES
PROTOCOL=base.PROTOCOL
INPUT=base.INPUT
VERSION=base.VERSION
def main(): base.main()
if __name__=='__main__':main()
