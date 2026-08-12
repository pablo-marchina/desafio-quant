#!/usr/bin/env python3
import hashlib, json
from pathlib import Path
M=Path('registry/w2c_semantic_v2_adjudication_v1_1_freeze_manifest.json')
def sha1_blob(path):
    b=Path(path).read_bytes()
    return hashlib.sha1(('blob %d\0'%len(b)).encode()+b).hexdigest()
def main():
    m=json.loads(M.read_text())
    assert m['version']=='W2C-ADJF-v1.1'
    parts=['W2C-ADJF-v1.1']
    for x in m['frozen_blobs']:
        actual=sha1_blob(x['path']); assert actual==x['git_blob_sha1']; parts.append(actual)
    x=m['frozen_input']; actual=sha1_blob(x['path']); assert actual==x['git_blob_sha1']; parts.append(actual)
    bundle=hashlib.sha256('|'.join(parts).encode()).hexdigest()
    assert bundle==m['freeze_bundle_id_sha256']
    print(json.dumps({'status':'PASS_W2C_ADJUDICATION_V1_1_BYTE_FREEZE','bundle':bundle,'titles_read':False},indent=2))
if __name__=='__main__': main()
