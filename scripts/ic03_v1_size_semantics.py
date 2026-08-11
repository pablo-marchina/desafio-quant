#!/usr/bin/env python3
from __future__ import annotations
import argparse,csv,gzip,json,os,time,urllib.request,hashlib,concurrent.futures
from decimal import Decimal,getcontext
from pathlib import Path
from web3 import Web3

getcontext().prec=50
V1="0x4bfb41d5b3570defd03c39a9a4d8de6bd8b8982e"
ABI_URL="https://raw.githubusercontent.com/Polymarket/ctf-exchange/ed5c7708b7be3aa98bf5f0c6602b57cc498e2ef4/artifacts/CTFExchange.json"
RPC_DEFAULT=["https://polygon.drpc.org","https://tenderly.rpc.polygon.community","https://polygon.publicnode.com","https://polygon.api.onfinality.io/public","https://1rpc.io/matic"]
SCALE=Decimal(10**6)

def post(url,payload,timeout=12):
 req=urllib.request.Request(url,data=json.dumps(payload,separators=(",",":")).encode(),headers={"Content-Type":"application/json","User-Agent":"ARGOS-IC03-SIZE/1.0"})
 with urllib.request.urlopen(req,timeout=timeout) as r:return json.loads(r.read())

def fetch_url(url):
 req=urllib.request.Request(url,headers={"User-Agent":"ARGOS-IC03-SIZE/1.0"})
 with urllib.request.urlopen(req,timeout=30) as r:return r.read()

def sha_bytes(b):return hashlib.sha256(b).hexdigest()

def load_rows(path):
 with gzip.open(path,"rt",encoding="utf-8") as f:return list(csv.DictReader(f))

def rpc_get(url,tx):
 x=post(url,{"jsonrpc":"2.0","id":1,"method":"eth_getTransactionByHash","params":[tx]})
 if x.get("error"):raise RuntimeError(x["error"])
 return x.get("result")

def health(urls,probe):
 ok=[]
 for u in urls:
  try:
   if rpc_get(u,probe):ok.append(u)
  except Exception:pass
 if not ok:raise RuntimeError("no healthy RPC for tx input retrieval")
 return ok

def fetch_txs(urls,hashes):
 out={}
 def one(i_h):
  i,h=i_h
  for a in range(6):
   u=urls[(i+a)%len(urls)]
   try:
    r=rpc_get(u,h)
    if r:return h,r
   except Exception:time.sleep(.1*(a+1))
  return h,None
 with concurrent.futures.ThreadPoolExecutor(max_workers=min(48,len(hashes))) as ex:
  for h,r in ex.map(one,enumerate(hashes)):out[h]=r
 return out

def asdict(x):
 if isinstance(x,dict):return x
 if hasattr(x,"items"):return dict(x.items())
 return x

def field(order,name,index):
 o=asdict(order)
 if isinstance(o,dict):
  if name in o:return int(o[name])
  # web3 may use positional string keys only in unusual ABI returns
 if isinstance(o,(list,tuple)):return int(o[index])
 raise KeyError(name)

def main():
 ap=argparse.ArgumentParser();ap.add_argument("--signed-tape",required=True);ap.add_argument("--out",required=True);a=ap.parse_args()
 out=Path(a.out);out.mkdir(parents=True,exist_ok=True)
 rows=load_rows(Path(a.signed_tape))
 mm=[r for r in rows if r["exchange_version"]=="V1" and r["api_side"]=="BUY" and r["size_match"].lower()!="true"]
 if len(mm)!=569:raise RuntimeError(f"expected frozen 569 V1 BUY size mismatches, got {len(mm)}")
 abi_raw=fetch_url(ABI_URL);(out/"CTFExchange_v1_pinned.json").write_bytes(abi_raw);art=json.loads(abi_raw);abi=art["abi"]
 w3=Web3();contract=w3.eth.contract(address=Web3.to_checksum_address(V1),abi=abi)
 urls=[u.strip() for u in os.getenv("POLYGON_RPC_ENDPOINTS",",".join(RPC_DEFAULT)).split(",") if u.strip()]
 urls=health(urls,mm[0]["tx_hash"]);print("healthy",urls,flush=True)
 txs=fetch_txs(urls,[r["tx_hash"] for r in mm]);missing=[h for h,v in txs.items() if not v]
 if missing:raise RuntimeError(f"missing tx inputs {len(missing)}")
 audit=[]
 for r in mm:
  tx=txs[r["tx_hash"]]
  fn,p=contract.decode_function_input(tx["input"])
  if fn.fn_name!="matchOrders":raise RuntimeError(f"unexpected function {fn.fn_name}")
  taker=p.get("takerOrder") or p.get("_takerOrder")
  fill=int(p.get("takerFillAmount") if "takerFillAmount" in p else p.get("_takerFillAmount"))
  maker_amt=field(taker,"makerAmount",2);taker_amt=field(taker,"takerAmount",3);side=field(taker,"side",6);token=field(taker,"tokenId",4)
  min_take=(fill*taker_amt)//maker_amt
  api=Decimal(r["api_size"]);gross=Decimal(r["onchain_token_amount"]);pre=Decimal(min_take)/SCALE
  collateral=Decimal(r["onchain_collateral_amount"]);actual_price=Decimal(r["api_price"])
  limit_price=(Decimal(maker_amt)/Decimal(taker_amt)) if taker_amt else Decimal("NaN")
  audit.append({"tx_hash":r["tx_hash"],"event_key":r["event_key"],"api_size":str(api),"onchain_gross_token_amount":str(gross),"taker_fill_amount":str(Decimal(fill)/SCALE),"order_maker_amount":str(Decimal(maker_amt)/SCALE),"order_taker_amount":str(Decimal(taker_amt)/SCALE),"pre_surplus_min_taking":str(pre),"api_minus_pre_surplus":str(api-pre),"gross_minus_pre_surplus":str(gross-pre),"api_equals_pre_surplus":str(abs(api-pre)<=Decimal("0.000001")),"limit_price":str(limit_price),"execution_price":str(actual_price),"price_improvement":str(limit_price-actual_price),"side_enum":side,"token_match":str(str(token)==r["asset"]),"tx_to":tx.get("to","")})
 fields=list(audit[0]);
 with open(out/"ic03_v1_size_semantics.csv","w",newline="",encoding="utf-8") as f:w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(audit)
 eq=sum(x["api_equals_pre_surplus"]=="True" for x in audit)
 diffs=[abs(Decimal(x["api_minus_pre_surplus"])) for x in audit]
 imp=[Decimal(x["price_improvement"]) for x in audit]
 summary={"rows":len(audit),"api_equals_pre_surplus":eq,"api_not_equal_pre_surplus":len(audit)-eq,"max_abs_api_minus_pre_surplus":str(max(diffs)),"positive_price_improvement_rows":sum(x>0 for x in imp),"zero_or_negative_price_improvement_rows":sum(x<=0 for x in imp),"pinned_v1_abi_sha256":sha_bytes(abi_raw),"v1_exchange":V1,"official_repo_commit":"ed5c7708b7be3aa98bf5f0c6602b57cc498e2ef4","healthy_rpcs":urls}
 (out/"ic03_v1_size_summary.json").write_text(json.dumps(summary,indent=2,sort_keys=True),encoding="utf-8")
 print(json.dumps(summary,indent=2),flush=True)

if __name__=="__main__":main()
