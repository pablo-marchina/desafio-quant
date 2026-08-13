#!/usr/bin/env python3
"""Pre-execution implementation correction for W4B-XVD-v1.0.

The scientific protocol is unchanged. This wrapper fixes only the executor's
cross-venue presence guard so identical multi-venue sets are still eligible for
the already-frozen candidate rules.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE_SCRIPT = ROOT / 'scripts' / 'w4b_cross_venue_dedup_v1.py'
src = BASE_SCRIPT.read_text(encoding='utf-8')
old = """                if not (va-vb or vb-va):\n                    # Need at least one cross-venue comparison; same venue-set-only candidates add no cross-venue evidence.\n                    continue\n"""
new = """                if len(va | vb) < 2:\n                    # Candidate duplicate reconciliation is cross-venue only. Identical multi-venue sets remain eligible.\n                    continue\n"""
if src.count(old) != 1:
    raise SystemExit(f'controlled_cross_venue_guard_patch_failure:count={src.count(old)}')
src = src.replace(old, new, 1)
ns = {'__name__':'__main__','__file__':str(BASE_SCRIPT)}
exec(compile(src, str(BASE_SCRIPT)+'[v1.0.1-pre-execution-guard-erratum]', 'exec'), ns, ns)
