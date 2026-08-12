#!/usr/bin/env python3
from __future__ import annotations
import hashlib,json,subprocess
from pathlib import Path
M=Path('registry/w2c_semantic_v2_freeze_manifest.json');V='W2C-SVF-v2.0'
def blob(path):return subprocess.check_output(['git','hash-object',path],text=True).strip()
def main():
 m=json.loads(M.read_text());assert m['version']==V and m['performance_blind'] is True and m['real_v2_candidate_results_seen_before_freeze'] is False
 parts=[V]
 for x in m['frozen_blobs']:
  a=blob(x['path']);assert a==x['git_blob_sha1'],(x['path'],a,x['git_blob_sha1']);parts.append(a)
 x=m['frozen_input'];a=blob(x['path']);assert a==x['git_blob_sha1'];parts.append(a)
 h=hashlib.sha256('|'.join(parts).encode()).hexdigest();assert h==m['freeze_bundle_id_sha256'],(h,m['freeze_bundle_id_sha256'])
 print(json.dumps({'status':'PASS_W2C_SEMANTIC_V2_BYTE_FREEZE','version':V,'bundle':h,'candidate_data_read':False},indent=2))
if __name__=='__main__':main()
