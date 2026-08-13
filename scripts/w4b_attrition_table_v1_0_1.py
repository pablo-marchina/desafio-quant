#!/usr/bin/env python3
from __future__ import annotations

import csv
import gzip
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REG = ROOT / 'registry'
ORIGINAL = ROOT / 'scripts' / 'w4b_attrition_table_v1.py'

spec = importlib.util.spec_from_file_location('w4b_attrition_frozen_v1', ORIGINAL)
module = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(module)


def regpath(name: str | Path) -> Path:
    p = Path(name)
    if p.is_absolute():
        return p
    if p.parts and p.parts[0] == 'registry':
        return ROOT / p
    return REG / p


def j(name):
    return json.loads(regpath(name).read_text())


def gz(name):
    with gzip.open(regpath(name), 'rt', encoding='utf-8', newline='') as f:
        return list(csv.DictReader(f))


module.j = j
module.gz = gz

if __name__ == '__main__':
    module.main()
