#!/usr/bin/env python3
from __future__ import annotations

import json
from datetime import datetime, timezone

import w4c_r1_official_truth_extension_v1 as core


def sec_company_index_fail_closed(manifest: list[dict]) -> tuple[list[dict], str]:
    """Transport-only override: preserve SEC authority; fail closed on HTTP denial."""
    body, status, ct = core.http_get(core.SEC_TICKERS)
    retrieved = datetime.now(timezone.utc).isoformat()
    h = core.sha256_bytes(body) if body else ''
    manifest.append({
        'source_authority': 'SEC_EDGAR',
        'source_url': core.SEC_TICKERS,
        'retrieved_at_utc': retrieved,
        'http_status': status,
        'content_type': ct,
        'response_bytes': len(body),
        'source_body_sha256_or_document_hash': h,
        'purpose': 'SEC_COMPANY_IDENTITY_MAP_TRANSPORT_FAIL_CLOSED',
    })
    if status != 200:
        print(f'SEC_TICKER_MAP_HTTP_{status}_FAIL_CLOSED_NO_EARNINGS_VOTE', flush=True)
        return [], h

    obj = json.loads(body.decode())
    companies = []
    for _, x in obj.items():
        cik = str(x.get('cik_str') or '').zfill(10)
        ticker = str(x.get('ticker') or '').upper().strip()
        title = str(x.get('title') or '').strip()
        if not cik or not ticker or not title:
            continue
        nt = core.norm(title)
        stripped = ' '.join(
            t for t in nt.split()
            if t not in {'inc','corp','corporation','company','co','ltd','limited','plc','holdings','group','nv','sa','ag'}
        )
        companies.append({
            'cik10': cik,
            'ticker': ticker,
            'title': title,
            'norm_title': nt,
            'core_title': stripped,
        })
    return companies, h


if __name__ == '__main__':
    core.sec_company_index = sec_company_index_fail_closed
    core.main()
