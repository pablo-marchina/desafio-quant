#!/usr/bin/env python3
from __future__ import annotations
import hashlib,json,subprocess
from pathlib import Path
R=Path('.')
def blob(p):return subprocess.check_output(['git','rev-parse',f'HEAD:{p}'],text=True).strip()
def main():
 m=json.loads((R/'registry/w2b_ias_protocol_freeze_v1_0.json').read_text());lines=[]
 for p,sha in sorted(m['frozen_objects'].items()):
  got=blob(p)
  if got!=sha:raise SystemExit(f'frozen blob mismatch {p}: {got} != {sha}')
  lines.append(f'{p}:{got}\n')
 d=hashlib.sha256(''.join(lines).encode()).hexdigest()
 if d!=m['bundle_sha256']:raise SystemExit(f'frozen bundle mismatch {d}')
 print(json.dumps({'artifact':'W2B_IAS_FROZEN_BUNDLE_INTEGRITY','status':'PASS','bundle_sha256':d,'objects':len(lines)},indent=2))
if __name__=='__main__':main()
