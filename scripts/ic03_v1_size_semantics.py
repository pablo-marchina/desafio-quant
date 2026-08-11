#!/usr/bin/env python3
from __future__ import annotations
import argparse,csv,gzip,json,os,time,urllib.request,hashlib,concurrent.futures
from collections import Counter
from decimal import Decimal,getcontext
from pathlib import Path
from web3 import Web3

getcontext().prec=50
FEE_MODULE="0xe3f18acc55091e2c48d883fc8c8413319d4ab7b0"
FEE_SOURCE_COMMIT="f5b26a1ca0f56190df9ae5354beead35630f5176"
FEE_SOURCE_URL=f"https://raw.githubusercontent.com/Polymarket/exchange-fee-module/{FEE_SOURCE_COMMIT}/src/FeeModule.sol"
STRUCTS_SOURCE_URL=f"https://raw.githubusercontent.com/Polymarket/exchange-fee-module/{FEE_SOURCE_COMMIT}/src/libraries/Structs.sol"
RPC_DEFAULT=["https://polygon.drpc.org","https://tenderly.rpc.polygon.community","https://polygon.publicnode.com","https://polygon.api.onfinality.io/public","https://1rpc.io/matic"]
SCALE=Decimal(10**6); TOL=Decimal("0.000001")
ORDER_COMPONENTS=[
 {"name":"salt","type":"uint256"},{"name":"maker","type":"address"},{"name":"signer","type":"address"},{"name":"taker","type":"address"},
 {"name":"tokenId","type":"uint256"},{"name":"makerAmount","type":"uint256"},{"name":"takerAmount","type":"uint256"},{"name":"expiration","type":"uint256"},
 {"name":"nonce","type":"uint256"},{"name":"feeRateBps","type":"uint256"},{"name":"side","type":"uint8"},{"name":"signatureType","type":"uint8"},{"name":"signature","type":"bytes"}
]
MATCH_ABI={"type":"function","name":"matchOrders","stateMutability":"nonpayable","inputs":[
 {"name":"takerOrder","type":"tuple","components":ORDER_COMPONENTS},
 {"name":"makerOrders","type":"tuple[]","components":ORDER_COMPONENTS},
 {"name":"takerFillAmount","type":"uint256"},
 {"name":"takerReceiveAmount","type":"uint256"},
 {"name":"makerFillAmounts","type":"uint256[]"},
 {"name":"takerFeeAmount","type":"uint256"},
 {"name":"makerFeeAmounts","type":"uint256[]"}
],"outputs":[]}
CANONICAL_SIGNATURE="matchOrders((uint256,address,address,address,uint256,uint256,uint256,uint256,uint256,uint256,uint8,uint8,bytes),(uint256,address,address,address,uint256,uint256,uint256,uint256,uint256,uint256,uint8,uint8,bytes)[],uint256,uint256,uint256[],uint256,uint256[])"
EXPECTED_SELECTOR="0x2287e350"

def post(url,payload,timeout=12):
 req=urllib.request.Request(url,data=json.dumps(payload,separators=(",",":")).encode(),headers={"Content-Type":"application/json","User-Agent":"ARGOS-IC03-SIZE/3.0"})
 with urllib.request.urlopen(req,timeout=timeout) as r:return json.loads(r.read())
def fetch_url(url):
 req=urllib.request.Request(url,headers={"User-Agent":"ARGOS-IC03-SIZE/3.0"})
 with urllib.request.urlopen(req,timeout=30) as r:return r.read()
def sha_bytes(b):return hashlib.sha256(b).hexdigest()
def rpc_get(url,h):
 x=post(url,{"jsonrpc":"2.0","id":1,"method":"eth_getTransactionByHash","params":[h]})
 if x.get("error"):raise RuntimeError(x["error"])
 return x.get("result")
def health(urls,probe):
 ok=[]
 for u in urls:
  try:
   if rpc_get(u,probe):ok.append(u)
  except Exception:pass
 if not ok:raise RuntimeError("no healthy RPC")
 return ok
def fetch_txs(urls,hs):
 out={}
 def one(pair):
  i,h=pair
  for a in range(8):
   try:
    x=rpc_get(urls[(i+a)%len(urls)],h)
    if x:return h,x
   except Exception:time.sleep(.1*(a+1))
  return h,None
 with concurrent.futures.ThreadPoolExecutor(max_workers=min(48,len(hs))) as ex:
  for h,x in ex.map(one,enumerate(hs)):out[h]=x
 return out
def unit(x):return Decimal(int(x))/SCALE

def main():
 ap=argparse.ArgumentParser();ap.add_argument("--signed-tape",required=True);ap.add_argument("--out",required=True);a=ap.parse_args()
 out=Path(a.out);out.mkdir(parents=True,exist_ok=True)
 with gzip.open(a.signed_tape,"rt",encoding="utf-8") as f:rows=list(csv.DictReader(f))
 mm=[r for r in rows if r["exchange_version"]=="V1" and r["api_side"]=="BUY" and r["size_match"].lower()!="true"]
 if len(mm)!=569:raise RuntimeError(f"expected frozen 569 mismatches, got {len(mm)}")
 fee_source=fetch_url(FEE_SOURCE_URL);structs_source=fetch_url(STRUCTS_SOURCE_URL)
 (out/"FeeModule_f5b26.sol").write_bytes(fee_source);(out/"Structs_f5b26.sol").write_bytes(structs_source)
 selector="0x"+Web3.keccak(text=CANONICAL_SIGNATURE)[:4].hex()
 if selector.lower()!=EXPECTED_SELECTOR:raise RuntimeError(f"manual ABI selector {selector} != deployed {EXPECTED_SELECTOR}")
 contract=Web3().eth.contract(address=Web3.to_checksum_address(FEE_MODULE),abi=[MATCH_ABI])
 urls=[u.strip() for u in os.getenv("POLYGON_RPC_ENDPOINTS",",".join(RPC_DEFAULT)).split(",") if u.strip()];urls=health(urls,mm[0]["tx_hash"]);print("selector",selector,"healthy",urls,flush=True)
 txs=fetch_txs(urls,[r["tx_hash"] for r in mm]);missing=[h for h,x in txs.items() if x is None]
 if missing:raise RuntimeError(f"missing {len(missing)} txs")
 audit=[]
 for r in mm:
  tx=txs[r["tx_hash"]]
  if (tx.get("to") or "").lower()!=FEE_MODULE:raise RuntimeError("unexpected outer contract")
  if (tx.get("input") or "")[:10].lower()!=EXPECTED_SELECTOR:raise RuntimeError("unexpected outer selector")
  fn,p=contract.decode_function_input(tx["input"])
  if fn.fn_name!="matchOrders":raise RuntimeError(f"unexpected function {fn.fn_name}")
  receive=unit(p["takerReceiveAmount"]); fee=unit(p["takerFeeAmount"]); fill=unit(p["takerFillAmount"])
  api=Decimal(r["api_size"]);gross=Decimal(r["onchain_token_amount"]);coll=Decimal(r["onchain_collateral_amount"]);price=Decimal(r["api_price"]);net=receive-fee;taker=p["takerOrder"]
  audit.append({"tx_hash":r["tx_hash"],"event_key":r["event_key"],"api_size":str(api),"onchain_gross_token_amount":str(gross),"onchain_collateral_amount":str(coll),"api_price":str(price),"fee_module_taker_fill_amount":str(fill),"fee_module_taker_receive_amount":str(receive),"fee_module_taker_fee_amount":str(fee),"fee_module_net_receive_amount":str(net),"receive_minus_gross":str(receive-gross),"api_minus_net_receive":str(api-net),"gross_minus_api_minus_fee":str((gross-api)-fee),"receive_matches_gross":str(abs(receive-gross)<=TOL),"api_matches_net_receive":str(abs(api-net)<=TOL),"gross_minus_api_matches_fee":str(abs((gross-api)-fee)<=TOL),"collateral_matches_gross_x_price":str(abs(coll-gross*price)<=TOL),"fee_rate_bps":str(int(taker["feeRateBps"])),"order_side":str(int(taker["side"])),"token_id":str(int(taker["tokenId"])),"order_maker":taker["maker"].lower(),"outer_selector":tx["input"][:10]})
 with open(out/"ic03_v1_size_semantics.csv","w",newline="",encoding="utf-8") as f:w=csv.DictWriter(f,fieldnames=list(audit[0]));w.writeheader();w.writerows(audit)
 summary={"rows":569,"fee_module_address":FEE_MODULE,"official_source_commit":FEE_SOURCE_COMMIT,"fee_module_source_sha256":sha_bytes(fee_source),"structs_source_sha256":sha_bytes(structs_source),"canonical_signature":CANONICAL_SIGNATURE,"computed_selector":selector,"selector_counts":dict(Counter(x["outer_selector"] for x in audit)),"receive_matches_onchain_gross":sum(x["receive_matches_gross"]=="True" for x in audit),"api_matches_net_receive":sum(x["api_matches_net_receive"]=="True" for x in audit),"gross_minus_api_matches_operator_fee":sum(x["gross_minus_api_matches_fee"]=="True" for x in audit),"collateral_matches_gross_x_price":sum(x["collateral_matches_gross_x_price"]=="True" for x in audit),"max_abs_receive_minus_gross":str(max(abs(Decimal(x["receive_minus_gross"])) for x in audit)),"max_abs_api_minus_net_receive":str(max(abs(Decimal(x["api_minus_net_receive"])) for x in audit)),"max_abs_gross_minus_api_minus_fee":str(max(abs(Decimal(x["gross_minus_api_minus_fee"])) for x in audit)),"fee_rate_bps_counts":dict(Counter(x["fee_rate_bps"] for x in audit)),"healthy_rpcs":urls}
 summary["decision"]="PASS_V1_SIZE_NET_OF_OPERATOR_FEE" if summary["receive_matches_onchain_gross"]==569 and summary["api_matches_net_receive"]==569 and summary["gross_minus_api_matches_operator_fee"]==569 else "REVIEW_V1_SIZE_SEMANTICS"
 (out/"ic03_v1_size_summary.json").write_text(json.dumps(summary,indent=2,sort_keys=True),encoding="utf-8")
 print(json.dumps(summary,indent=2),flush=True)
 if summary["decision"]!="PASS_V1_SIZE_NET_OF_OPERATOR_FEE":raise SystemExit(2)
if __name__=="__main__":main()
