#!/usr/bin/env python3
from __future__ import annotations
import hashlib, json, subprocess
from pathlib import Path
M=Path('registry/w2c_pit_platform_freeze_manifest_v1_0.json')
V='W2C-PIT-AF-v1.0'
def blob(path): return subprocess.check_output(['git','hash-object',path],text=True).strip()
def main():
    m=json.loads(M.read_text())
    assert m['version']==V and m['performance_blind'] is True and m['real_pit_network_access_before_freeze'] is False
    parts=[V]
    for x in m['frozen_blobs']:
        a=blob(x['path']); assert a==x['git_blob_sha1'],(x['path'],a,x['git_blob_sha1']); parts.append(a)
    x=m['frozen_input']; assert blob(x['path'])==x['git_blob_sha1']
    h=hashlib.sha256('|'.join(parts).encode()).hexdigest(); assert h==m['freeze_bundle_id_sha256'],(h,m['freeze_bundle_id_sha256'])
    print(json.dumps({'status':'PASS_W2C_PIT_A_BYTE_FREEZE','version':V,'bundle':h,'network_accessed':False},indent=2))
if __name__=='__main__': main()
