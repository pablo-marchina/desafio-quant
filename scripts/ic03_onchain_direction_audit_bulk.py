#!/usr/bin/env python3
from __future__ import annotations
import concurrent.futures,itertools,time
import ic03_onchain_direction_audit as base


def _pass(self, hashes, workers, attempts, timeout, backoff):
    urls=list(self.u); seq=itertools.count(); out={}
    def one(h):
        seed=next(seq)
        for a in range(attempts):
            u=urls[(seed+a)%len(urls)]; rid=next(seq)+1
            try:
                x=base.post(u,{"jsonrpc":"2.0","id":rid,"method":"eth_getTransactionReceipt","params":[h]},timeout=timeout)
                if x.get("error"): raise RuntimeError(x["error"])
                r=x.get("result")
                if r is not None:
                    self.ok[u]+=1; return h,r
            except Exception:
                self.fail[u]+=1
            if backoff: time.sleep(backoff*(a+1))
        return h,None
    done=0
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as ex:
        fs=[ex.submit(one,h) for h in hashes]
        for f in concurrent.futures.as_completed(fs):
            h,r=f.result();out[h]=r;done+=1
            if done%1000==0 or done==len(hashes): print(f"receipt-pass workers={workers}: {done}/{len(hashes)}",flush=True)
    return out


def bulk_then_retry(self, hs):
    print("IC03 receipt pass 1: bulk",len(hs),flush=True)
    out=_pass(self,hs,workers=72,attempts=3,timeout=8,backoff=0.05)
    missing=[h for h,r in out.items() if r is None]
    print("pass1 missing",len(missing),flush=True)
    if missing:
        retry=_pass(self,missing,workers=24,attempts=8,timeout=15,backoff=0.25)
        out.update(retry)
    missing=[h for h,r in out.items() if r is None]
    print("final missing receipts",len(missing),flush=True)
    return out

base.Rpc.receipts=bulk_then_retry
if __name__=="__main__": base.main()
