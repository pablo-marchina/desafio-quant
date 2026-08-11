#!/usr/bin/env python3
from __future__ import annotations
import argparse,csv,gzip,hashlib,json,os,sys,time,urllib.request
from collections import Counter,defaultdict
from datetime import datetime,timezone
from decimal import Decimal,getcontext
from pathlib import Path
getcontext().prec=50

V1="0x4bfb41d5b3570defd03c39a9a4d8de6bd8b8982e"
V2="0xe111180000d2663c0091e4f400237545b87b996b"
CUT=int(datetime(2026,4,28,11,tzinfo=timezone.utc).timestamp())
SIG1="OrderFilled(bytes32,address,address,uint256,uint256,uint256,uint256,uint256)"
SIG2="OrderFilled(bytes32,address,address,uint8,uint256,uint256,uint256,uint256,bytes32,bytes32)"
RPC_DEFAULT=["https://polygon.drpc.org","https://polygon.publicnode.com","https://tenderly.rpc.polygon.community"]
SCALE=Decimal(10**6); TOL=Decimal("0.000001")

def sha(p):
 h=hashlib.sha256()
 with open(p,"rb") as f:
  for b in iter(lambda:f.read(1<<20),b""): h.update(b)
 return h.hexdigest()

def post(url,payload,timeout=45):
 req=urllib.request.Request(url,data=json.dumps(payload,separators=(",",":")).encode(),headers={"Content-Type":"application/json","User-Agent":"ARGOS-IC03/1.0"})
 with urllib.request.urlopen(req,timeout=timeout) as r:return json.loads(r.read())

class Rpc:
 def __init__(self,urls):self.u=urls;self.i=1;self.ok=Counter();self.fail=Counter()
 def call(self,m,p):
  err=None
  for a in range(8):
   u=self.u[a%len(self.u)];i=self.i;self.i+=1
   try:
    x=post(u,{"jsonrpc":"2.0","id":i,"method":m,"params":p})
    if x.get("error"):raise RuntimeError(x["error"])
    self.ok[u]+=1;return x.get("result")
   except Exception as e:self.fail[u]+=1;err=e;time.sleep(min(.5*2**a,8))
  raise RuntimeError(f"{m}: {err}")
 def receipts(self,hs,n=40):
  out={}
  for s in range(0,len(hs),n):
   ch=hs[s:s+n];done=False
   for a in range(8):
    u=self.u[(s//n+a)%len(self.u)];ids={}
    q=[]
    for h in ch:
     i=self.i;self.i+=1;ids[i]=h;q.append({"jsonrpc":"2.0","id":i,"method":"eth_getTransactionReceipt","params":[h]})
    try:
     x=post(u,q)
     if not isinstance(x,list):raise RuntimeError("non-list batch")
     seen=set()
     for z in x:
      h=ids.get(z.get("id"))
      if h:seen.add(h);out[h]=None if z.get("error") else z.get("result")
     for h in ch:
      if h not in seen:out[h]=None
     self.ok[u]+=1;done=True;break
    except Exception:self.fail[u]+=1;time.sleep(min(.5*2**a,8))
   if not done:
    for h in ch:
     try:out[h]=self.call("eth_getTransactionReceipt",[h])
     except Exception:out[h]=None
   if min(s+n,len(hs))%1000<n or s+n>=len(hs):print("receipts",min(s+n,len(hs)),"/",len(hs),flush=True)
  for h in [h for h,v in out.items() if v is None]:
   try:out[h]=self.call("eth_getTransactionReceipt",[h])
   except Exception:pass
  return out

def addr(t):return "0x"+t.lower().removeprefix("0x")[-40:]
def words(d):
 x=d.removeprefix("0x")
 if len(x)%64:raise ValueError("bad abi data")
 return [x[i:i+64] for i in range(0,len(x),64)]

def verify_ic02(d):
 p=d/"ic02_raw_manifest.csv";bad=[];n=0
 for r in csv.DictReader(open(p,encoding="utf-8")):
  f=d/r["path"];n+=1
  if not f.exists() or sha(f)!=r["sha256"]:bad.append(r["path"])
 if bad:raise RuntimeError(f"IC02 hash failures {bad[:5]}")
 return n,sha(p)

def load_events(p):
 e={}
 for r in csv.DictReader(open(p,encoding="utf-8")):
  r=dict(r);r["cut"]=int(datetime.fromisoformat(r["safe_cutoff_utc"].replace("Z","+00:00")).timestamp());e[r["market_id"]]=r
 if len(e)!=117:raise RuntimeError(f"expected 117 events got {len(e)}")
 return e

def load_trades(d,e):
 out=[];neg=[]
 for mid,v in e.items():
  g=json.load(open(d/"raw/gamma"/f"{mid}.json",encoding="utf-8"))
  if g.get("negRisk") is not False:neg.append(mid)
  with gzip.open(d/"raw/trades"/f"{mid}.jsonl.gz","rt",encoding="utf-8") as f:
   for line in f:
    t=json.loads(line)
    if int(t["timestamp"])<=v["cut"]:
     out.append({"market_id":mid,"event_key":v["event_key"],"ticker":v["ticker"],"company_event_date":v["company_event_date"],"safe_cutoff_utc":v["safe_cutoff_utc"],"timestamp":int(t["timestamp"]),"tx_hash":t["transactionHash"].lower(),"proxy_wallet":t["proxyWallet"].lower(),"asset":str(t["asset"]),"condition_id":t["conditionId"].lower(),"outcome":t.get("outcome",""),"api_side":t["side"].upper(),"api_size":str(t["size"]),"api_price":str(t["price"])})
 if neg:raise RuntimeError(f"negRisk unexpected {neg[:5]}")
 hs=[x["tx_hash"] for x in out]
 if len(hs)!=len(set(hs)):raise RuntimeError("duplicate tx hashes in IC02 pre-cutoff tape")
 return out

def decode(log,t1,t2):
 a=log["address"].lower();ts=[x.lower() for x in log["topics"]]
 if len(ts)<4:return None
 w=words(log["data"]);base={"exchange_address":a,"order_hash":ts[1],"maker":addr(ts[2]),"taker":addr(ts[3]),"log_index":int(log.get("logIndex","0x0"),16)}
 if a==V1 and ts[0]==t1:
  if len(w)!=5:return None
  return base|{"version":"V1","ma":int(w[0],16),"ta":int(w[1],16),"making":int(w[2],16),"taking":int(w[3],16),"side_num":None}
 if a==V2 and ts[0]==t2:
  if len(w)!=7:return None
  return base|{"version":"V2","token":int(w[1],16),"making":int(w[2],16),"taking":int(w[3],16),"side_num":int(w[0],16)}
 return None

def econ(x,asset):
 if x["version"]=="V1":
  if x["ma"]==0 and x["ta"]==asset:s="BUY";c=x["making"];q=x["taking"]
  elif x["ta"]==0 and x["ma"]==asset:s="SELL";q=x["making"];c=x["taking"]
  else:return None
 else:
  if x["token"]!=asset:return None
  if x["side_num"]==0:s="BUY";c=x["making"];q=x["taking"]
  elif x["side_num"]==1:s="SELL";q=x["making"];c=x["taking"]
  else:return None
 qd=Decimal(q)/SCALE;cd=Decimal(c)/SCALE
 return x|{"onchain_side":s,"token_amount":qd,"collateral_amount":cd,"onchain_price":cd/qd if qd else Decimal("NaN")}

def reconcile(r,rec,t1,t2):
 z=r|{"block_number":"","exchange_version":"","exchange_address":"","order_hash":"","log_index":"","candidate_count":0,"onchain_side":"","side_match":False,"onchain_token_amount":"","onchain_collateral_amount":"","onchain_price":"","size_abs_diff":"","price_abs_diff":"","size_match":False,"price_match":False,"era_match":False,"status":""}
 if not rec:z["status"]="MISSING_RECEIPT";return z
 if rec.get("status") not in ("0x1","0x01",1,"1"):z["status"]="FAILED_TX";return z
 asset=int(r["asset"]);cand=[]
 for l in rec.get("logs",[]):
  try:x=decode(l,t1,t2);x=econ(x,asset) if x else None
  except Exception:x=None
  if x and x["maker"]==r["proxy_wallet"] and x["taker"]==x["exchange_address"]:cand.append(x)
 z["block_number"]=int(rec["blockNumber"],16);z["candidate_count"]=len(cand)
 if not cand:z["status"]="NO_STRICT_ORDER_FILLED";return z
 apiq=Decimal(r["api_size"]);apip=Decimal(r["api_price"])
 cand.sort(key=lambda x:(abs(x["token_amount"]-apiq),abs(x["onchain_price"]-apip),x["log_index"]))
 x=cand[0];sd=abs(x["token_amount"]-apiq);pd=abs(x["onchain_price"]-apip)
 z|={"exchange_version":x["version"],"exchange_address":x["exchange_address"],"order_hash":x["order_hash"],"log_index":x["log_index"],"onchain_side":x["onchain_side"],"side_match":x["onchain_side"]==r["api_side"],"onchain_token_amount":format(x["token_amount"],"f"),"onchain_collateral_amount":format(x["collateral_amount"],"f"),"onchain_price":format(x["onchain_price"],"f"),"size_abs_diff":format(sd,"f"),"price_abs_diff":format(pd,"f"),"size_match":sd<=TOL,"price_match":pd<=TOL,"era_match":x["version"]==("V1" if r["timestamp"]<CUT else "V2")}
 z["status"]="PASS" if z["side_match"] and len(cand)==1 and z["era_match"] else ("SIDE_MISMATCH" if not z["side_match"] else "STRUCTURAL_REVIEW")
 return z

def write_csv(p,rows,fields=None):
 p.parent.mkdir(parents=True,exist_ok=True);fields=fields or (list(rows[0]) if rows else [])
 with open(p,"w",newline="",encoding="utf-8") as f:w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(rows)

def main():
 a=argparse.ArgumentParser();a.add_argument("--ic02-dir",required=True);a.add_argument("--input",required=True);a.add_argument("--output-dir",required=True);x=a.parse_args()
 d=Path(x.ic02_dir);o=Path(x.output_dir);o.mkdir(parents=True,exist_ok=True);(o/"raw").mkdir(exist_ok=True)
 nraw,msha=verify_ic02(d);ev=load_events(Path(x.input));tr=load_trades(d,ev)
 urls=[u.strip() for u in os.getenv("POLYGON_RPC_ENDPOINTS",",".join(RPC_DEFAULT)).split(",") if u.strip()];rpc=Rpc(urls)
 if rpc.call("eth_chainId",[]).lower()!="0x89":raise RuntimeError("RPC is not Polygon chain 137")
 def topic(sig):
  t=rpc.call("web3_sha3",["0x"+sig.encode().hex()])
  if not isinstance(t,str) or len(t)!=66:raise RuntimeError("bad web3_sha3")
  return t.lower()
 t1,t2=topic(SIG1),topic(SIG2)
 print("pre-cutoff trades",len(tr),flush=True);recs=rpc.receipts([r["tx_hash"] for r in tr])
 rp=o/"raw/ic03_receipts.jsonl.gz"
 with gzip.open(rp,"wt",encoding="utf-8") as f:
  for h in sorted(recs):f.write(json.dumps({"tx_hash":h,"receipt":recs[h]},sort_keys=True)+"\n")
 rr=[reconcile(r,recs.get(r["tx_hash"]),t1,t2) for r in tr]
 fields=["market_id","event_key","ticker","company_event_date","safe_cutoff_utc","timestamp","tx_hash","block_number","exchange_version","exchange_address","proxy_wallet","asset","condition_id","outcome","api_side","onchain_side","side_match","api_size","onchain_token_amount","size_abs_diff","size_match","api_price","onchain_price","price_abs_diff","price_match","onchain_collateral_amount","order_hash","log_index","candidate_count","era_match","status"]
 write_csv(o/"ic03_signed_tape.csv",rr,fields)
 with open(o/"ic03_signed_tape.csv","rb") as src,gzip.open(o/"ic03_signed_tape.csv.gz","wb") as dst:
  for b in iter(lambda:src.read(1<<20),b""):dst.write(b)
 write_csv(o/"ic03_unresolved.csv",[r for r in rr if r["status"]!="PASS"],fields)
 by=defaultdict(list)
 for r in rr:by[r["event_key"]].append(r)
 es=[]
 for v in ev.values():
  rs=by[v["event_key"]];es.append({"market_id":v["market_id"],"event_key":v["event_key"],"pre_cutoff_trades":len(rs),"pass":sum(r["status"]=="PASS" for r in rs),"side_mismatches":sum(r["status"]=="SIDE_MISMATCH" for r in rs),"structural_review":sum(r["status"]=="STRUCTURAL_REVIEW" for r in rs),"missing_or_unmatched":sum(r["status"] in ("MISSING_RECEIPT","FAILED_TX","NO_STRICT_ORDER_FILLED") for r in rs),"v1":sum(r["exchange_version"]=="V1" for r in rs),"v2":sum(r["exchange_version"]=="V2" for r in rs),"status":"NO_PRE_CUTOFF_TAPE" if not rs else ("PASS" if all(r["status"]=="PASS" for r in rs) else "REVIEW")})
 write_csv(o/"ic03_event_summary.csv",es)
 write_csv(o/"ic03_contract_map.csv",[{"version":"V1","chain_id":137,"exchange_address":V1,"order_filled_signature":SIG1,"order_filled_topic":t1,"direction_rule":"BUY iff makerAssetId=0; SELL iff takerAssetId=0","official_repo_commit":"ed5c7708b7be3aa98bf5f0c6602b57cc498e2ef4"},{"version":"V2","chain_id":137,"exchange_address":V2,"order_filled_signature":SIG2,"order_filled_topic":t2,"direction_rule":"Side enum 0=BUY 1=SELL","official_repo_commit":"ccc0596074f4dfd62c944fbca4de252893b82b4b"}])
 c=Counter(r["status"] for r in rr);ver=Counter(r["exchange_version"] for r in rr)
 decision="PASS_SIGNED_DIRECTION_FULL_RECONCILIATION" if c==Counter({"PASS":len(rr)}) else ("CONDITIONAL_SIGNED_DIRECTION_REVIEW" if all(r["side_match"] for r in rr if r["onchain_side"]) and not any(r["status"]=="SIDE_MISMATCH" for r in rr) else "INCOMPLETE_DIRECTION_RECONCILIATION")
 s={"decision":decision,"generated_utc":datetime.now(timezone.utc).isoformat(),"events":117,"pre_cutoff_trades":len(rr),"ic02_raw_files_verified":nraw,"ic02_manifest_sha256":msha,"status_counts":dict(c),"exchange_version_rows":dict(ver),"side_matches":sum(r["side_match"] for r in rr),"side_mismatches":sum(r["status"]=="SIDE_MISMATCH" for r in rr),"size_matches":sum(r["size_match"] for r in rr),"price_matches":sum(r["price_match"] for r in rr),"era_mismatches":sum(bool(r["exchange_version"]) and not r["era_match"] for r in rr),"v1_topic":t1,"v2_topic":t2,"receipts_sha256":sha(rp),"signed_tape_sha256":sha(o/"ic03_signed_tape.csv.gz"),"rpc_successes":dict(rpc.ok),"rpc_failures":dict(rpc.fail)}
 (o/"ic03_summary.json").write_text(json.dumps(s,indent=2,sort_keys=True),encoding="utf-8")
 (o/"ic03_report.md").write_text(f"""# ARGOS — IC-03 On-chain Direction Reconciliation

Decision: **{decision}**

This is a data-semantics gate for the later superset implementation audit. It uses only IC-02 pre-cutoff trades and Polygon receipts; no event outcomes or equity returns are consulted.

- IC-02 raw files hash-verified: {nraw}
- pre-cutoff trades: {len(rr)}
- strict passes: {c.get('PASS',0)}
- side matches: {s['side_matches']}/{len(rr)}
- side mismatches: {s['side_mismatches']}
- structural-review rows: {c.get('STRUCTURAL_REVIEW',0)}
- missing/unmatched rows: {c.get('MISSING_RECEIPT',0)+c.get('FAILED_TX',0)+c.get('NO_STRICT_ORDER_FILLED',0)}
- size matches <=1e-6: {s['size_matches']}/{len(rr)}
- price matches <=1e-6: {s['price_matches']}/{len(rr)}
- era mismatches: {s['era_mismatches']}
- V1 rows: {ver.get('V1',0)}
- V2 rows: {ver.get('V2',0)}

Only a passed semantic gate can make signed-flow data eligible for the later implementation audit. This result does not authorize any feature or predictive claim.
""",encoding="utf-8")
 print(json.dumps(s,indent=2),flush=True)
 if decision=="INCOMPLETE_DIRECTION_RECONCILIATION":sys.exit(2)

if __name__=="__main__":main()
