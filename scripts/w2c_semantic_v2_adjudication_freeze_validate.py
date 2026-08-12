#!/usr/bin/env python3
from __future__ import annotations
import hashlib,json
from pathlib import Path
M=Path('registry/w2c_semantic_v2_adjudication_freeze_manifest.json');V='W2C-ADJF-v1.0'
def blob(path):
 data=Path(path).read_bytes();return hashlib.sha1(f'blob {len(data)}\0'.encode()+data).hexdigest()
def main():
 m=json.loads(M.read_text());assert m['version']==V and m['performance_blind'] is True and m['real_queue_read_before_freeze'] is False
 parts=[V]
 for x in m['frozen_blobs']:
  a=blob(x['path']);assert a==x['git_blob_sha1'],(x['path'],a,x['git_blob_sha1']);parts.append(a)
 x=m['frozen_input'];a=blob(x['path']);assert a==x['git_blob_sha1'];parts.append(a)
 h=hashlib.sha256('|'.join(parts).encode()).hexdigest();assert h==m['freeze_bundle_id_sha256'],(h,m['freeze_bundle_id_sha256'])
 print(json.dumps({'status':'PASS_W2C_ADJUDICATION_BYTE_FREEZE','version':V,'bundle':h,'real_queue_read':False},indent=2))
if __name__=='__main__':main()
