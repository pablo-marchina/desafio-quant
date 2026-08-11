#!/usr/bin/env python3
from __future__ import annotations
import ic03_onchain_direction_audit as base
from ic03_onchain_direction_audit_fast import parallel_receipts


def receipts96(self, hs):
    return parallel_receipts(self, hs, workers=96)

base.Rpc.receipts = receipts96

if __name__ == "__main__":
    base.main()
