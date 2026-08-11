#!/usr/bin/env python3
from __future__ import annotations
import concurrent.futures
import ic03_onchain_direction_audit as base
from ic03_onchain_direction_audit_bulk import _pass


def healthy_receipts(self, hs):
    probe=hs[0]
    def check(u):
        try:
            x=base.post(u,{"jsonrpc":"2.0","id":1,"method":"eth_getTransactionReceipt","params":[probe]},timeout=5)
            ok=bool(x.get("result")) and not x.get("error")
            return u,ok,None if ok else str(x.get("error") or "null")
        except Exception as e:
            return u,False,type(e).__name__
    with concurrent.futures.ThreadPoolExecutor(max_workers=len(self.u)) as ex:
        checks=list(ex.map(check,list(self.u)))
    healthy=[u for u,ok,_ in checks if ok]
    print("RPC health",checks,flush=True)
    if not healthy: raise RuntimeError("no public Polygon RPC returned historical probe receipt")
    self.u=healthy
    print("healthy RPCs",healthy,flush=True)
    out=_pass(self,hs,workers=min(96,max(24,len(healthy)*16)),attempts=3,timeout=7,backoff=0.05)
    missing=[h for h,r in out.items() if r is None]
    print("bulk missing",len(missing),flush=True)
    if missing:
        retry=_pass(self,missing,workers=min(32,max(8,len(healthy)*6)),attempts=8,timeout=12,backoff=0.2)
        out.update(retry)
    print("final missing",sum(r is None for r in out.values()),flush=True)
    return out

base.Rpc.receipts=healthy_receipts
if __name__=="__main__": base.main()
