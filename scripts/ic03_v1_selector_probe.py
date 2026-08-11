#!/usr/bin/env python3
from __future__ import annotations
import csv,gzip,json,os,urllib.request,concurrent.futures
from collections import Counter

RPC=["https://polygon.drpc.org","https://tenderly.rpc.polygon.community"]

def post(u,p):
 req=urllib.request.Request(u,data=json.dumps(p).encode(),headers={"Content-Type":"application/json"})
 with urllib.request.urlopen(req,timeout=10) as r:return json.loads(r.read())

def get(u,h):
 x=post(u,{"jsonrpc":"2.0","id":1,"method":"eth_getTransactionByHash","params":[h]});return x.get("result")

def main():
 with gzip.open("data/ic03_signed_tape.csv.gz","rt",encoding="utf-8") as f:rows=list(csv.DictReader(f))
 mm=[r for r in rows if r["exchange_version"]=="V1" and r["api_side"]=="BUY" and r["size_match"].lower()!="true"]
 def one(x):
  i,r=x
  for a in range(2):
   try:
    t=get(RPC[(i+a)%2],r["tx_hash"])
    if t:return {"tx_hash":r["tx_hash"],"event_key":r["event_key"],"to":(t.get("to") or "").lower(),"from":(t.get("from") or "").lower(),"selector":(t.get("input") or "")[:10],"input_len":len(t.get("input") or "")}
   except Exception:pass
  return {"tx_hash":r["tx_hash"],"event_key":r["event_key"],"to":"","from":"","selector":"","input_len":0}
 with concurrent.futures.ThreadPoolExecutor(max_workers=32) as ex:out=list(ex.map(one,enumerate(mm)))
 c=Counter((r["to"],r["selector"]) for r in out)
 print(json.dumps([{"to":k[0],"selector":k[1],"count":v} for k,v in c.most_common()],indent=2))
 print(json.dumps(out[:5],indent=2))
 with open("registry/ic03_v1_selector_probe.csv","w",newline="",encoding="utf-8") as f:w=csv.DictWriter(f,fieldnames=list(out[0]));w.writeheader();w.writerows(out)

if __name__=="__main__":main()
