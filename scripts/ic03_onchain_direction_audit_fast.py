#!/usr/bin/env python3
from __future__ import annotations
import concurrent.futures, itertools, time
import ic03_onchain_direction_audit as base


def parallel_receipts(self, hs, workers=48):
    urls = list(self.u)
    counter = itertools.count()

    def one(h):
        last = None
        for attempt in range(10):
            u = urls[(next(counter) + attempt) % len(urls)]
            i = next(counter) + 1
            try:
                x = base.post(
                    u,
                    {"jsonrpc": "2.0", "id": i, "method": "eth_getTransactionReceipt", "params": [h]},
                    timeout=20,
                )
                if x.get("error"):
                    raise RuntimeError(x["error"])
                r = x.get("result")
                if r is not None:
                    self.ok[u] += 1
                    return h, r
                last = RuntimeError("null receipt")
            except Exception as e:
                self.fail[u] += 1
                last = e
            time.sleep(min(0.15 * (2 ** attempt), 3.0))
        return h, None

    out = {}
    done = 0
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as ex:
        futs = [ex.submit(one, h) for h in hs]
        for fut in concurrent.futures.as_completed(futs):
            h, r = fut.result()
            out[h] = r
            done += 1
            if done % 1000 == 0 or done == len(hs):
                print("receipts", done, "/", len(hs), flush=True)
    return out


base.Rpc.receipts = parallel_receipts

if __name__ == "__main__":
    base.main()
