#!/usr/bin/env python3
from pathlib import Path
import hashlib,json,subprocess,sys,tarfile,io
ROOT=Path(__file__).resolve().parents[1]
M=ROOT/'registry/w2a_real_execution_freeze_v1.json'
manifest=json.loads(M.read_text())
assert manifest['artifact']=='W2A_REAL_EXECUTION_BYTE_FREEZE'
assert manifest['version']=='W2A-REF-v1.0'
assert manifest['performance_outputs_read_before_freeze'] is False
assert manifest['gate0']['status']=='PASS_GATE0_RECOVERED_ORIGINAL_ART025_AND_DAT007'
assert manifest['w2a_accounting_protocol_git_blob']=='639f900eb876d6e46ecbeb10c1b3b3e6c3621a28'
checks=[]
for item in manifest['frozen_files']:
 p=ROOT/item['path']
 assert p.exists(), item['path']
 sha=hashlib.sha256(p.read_bytes()).hexdigest()
 blob=subprocess.check_output(['git','hash-object',str(p)],text=True).strip()
 assert sha==item['sha256'],(item['path'],'sha256',sha,item['sha256'])
 assert blob==item['git_blob_sha'],(item['path'],'blob',blob,item['git_blob_sha'])
 checks.append(item['path'])

# Validate deterministic transport archive contents against the recovered input manifest.
archive=ROOT/'data/w2a/w2a_real_inputs_v1.tar.gz'
input_manifest=json.loads((ROOT/'data/w2a/w2a_recovered_input_manifest.json').read_text())
with tarfile.open(archive,'r:gz') as tf:
    names=sorted(m.name for m in tf.getmembers() if m.isfile())
    assert names==sorted(input_manifest['files']), (names,sorted(input_manifest['files']))
    for name in names:
        data=tf.extractfile(name).read()
        meta=input_manifest['files'][name]
        assert len(data)==meta['bytes'],(name,'bytes')
        assert hashlib.sha256(data).hexdigest()==meta['sha256'],(name,'sha256')

protocol=ROOT/'registry/w2a_portfolio_accounting_protocol_draft.json'
assert subprocess.check_output(['git','hash-object',str(protocol)],text=True).strip()==manifest['w2a_accounting_protocol_git_blob']
print(json.dumps({'status':'PASS_W2A_REAL_EXECUTION_BYTE_FREEZE','version':manifest['version'],'files_checked':len(checks),'performance_outputs_read_before_freeze':False},indent=2))
