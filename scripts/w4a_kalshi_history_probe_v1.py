#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
REG = ROOT / 'registry'
BASE = 'https://external-api.kalshi.com/trade-api/v2'
UA = 'ARGOS-W4A-history-probe/1.0'
PROTO = json.loads((REG / 'w4a_kalshi_history_probe_protocol_v1.json').read_text())
RAW = json.loads((REG / 'w4_kalshi_series_first_capacity_v1.json').read_text())


def get_json(url: str, retries: int = 4):
    last = None
    for i in range(retries):
        try:
            with urlopen(Request(url, headers={'User-Agent': UA, 'Accept': 'application/json'}), timeout=45) as r:
                return json.loads(r.read().decode())
        except HTTPError as e:
            body = ''
            try:
                body = e.read().decode(errors='replace')[:500]
            except Exception:
                pass
            last = {'status': e.code, 'error': body or str(e), 'url': url}
            if 400 <= e.code < 500 and e.code != 429:
                return None, last
        except (URLError, TimeoutError, OSError, json.JSONDecodeError) as e:
            last = {'status': None, 'error': str(e), 'url': url}
        if i + 1 < retries:
            time.sleep(1.1 * (i + 1))
    return None, last or {'status': None, 'error': 'unknown', 'url': url}


def call(url: str):
    result = get_json(url)
    if isinstance(result, tuple):
        return result
    return result, None


def is_mve(m):
    return bool(m.get('mve_collection_ticker') or m.get('mve_selected_legs'))


def paged_markets(path: str, q: dict, max_pages: int = 20):
    cursor = ''
    rows = []
    pages = 0
    while pages < max_pages:
        qq = dict(q)
        if cursor:
            qq['cursor'] = cursor
        obj, err = call(BASE + path + '?' + urlencode(qq))
        if err:
            return rows, pages, False, err
        batch = obj.get('markets', [])
        rows.extend(batch)
        pages += 1
        cursor = obj.get('cursor') or ''
        if not cursor or not batch:
            return rows, pages, False, None
    return rows, pages, bool(cursor), None


def parse_ts(v):
    if not v:
        return None
    try:
        return int(datetime.fromisoformat(str(v).replace('Z', '+00:00')).timestamp())
    except Exception:
        return None


def market_end_ts(m):
    for k in ('close_time', 'latest_expiration_time', 'expected_expiration_time'):
        ts = parse_ts(m.get(k))
        if ts:
            return ts
    return None


def select_series():
    by_family = defaultdict(set)
    for r in RAW.get('selected_series', []):
        if r.get('family') and r.get('series_ticker'):
            by_family[r['family']].add(r['series_ticker'])
    chosen = defaultdict(set)
    n = int(PROTO['sampling']['series_per_family'])
    for fam in sorted(by_family):
        for st in sorted(by_family[fam])[:n]:
            chosen[st].add(fam)
    return {st: sorted(fams) for st, fams in sorted(chosen.items())}


def trade_probe(route: str, ticker: str, start_ts: int, end_ts: int):
    path = '/historical/trades' if route == 'historical' else '/markets/trades'
    q = {'ticker': ticker, 'min_ts': start_ts, 'max_ts': end_ts, 'limit': 1000}
    obj, err = call(BASE + path + '?' + urlencode(q))
    if err:
        return {'ok': False, 'error': err, 'rows': 0, 'truncated': False, 'first_ts': None, 'last_ts': None}
    rows = obj.get('trades', [])
    times = sorted(parse_ts(r.get('created_time')) for r in rows if parse_ts(r.get('created_time')) is not None)
    return {
        'ok': True,
        'error': None,
        'rows': len(rows),
        'truncated': bool(obj.get('cursor')),
        'first_ts': times[0] if times else None,
        'last_ts': times[-1] if times else None,
    }


def candle_probe(route: str, series_ticker: str, ticker: str, start_ts: int, end_ts: int):
    if route == 'historical':
        path = f'/historical/markets/{quote(ticker, safe="")}/candlesticks'
    else:
        path = f'/series/{quote(series_ticker, safe="")}/markets/{quote(ticker, safe="")}/candlesticks'
    q = {'start_ts': start_ts, 'end_ts': end_ts, 'period_interval': int(PROTO['window']['candle_period_minutes'])}
    obj, err = call(BASE + path + '?' + urlencode(q))
    if err:
        return {'ok': False, 'error': err, 'rows': 0, 'first_ts': None, 'last_ts': None}
    rows = obj.get('candlesticks', [])
    times = sorted(int(r['end_period_ts']) for r in rows if r.get('end_period_ts') is not None)
    return {
        'ok': True,
        'error': None,
        'rows': len(rows),
        'first_ts': times[0] if times else None,
        'last_ts': times[-1] if times else None,
    }


def main():
    chosen = select_series()
    attempts = 0
    successes = 0
    contract_400 = 0
    market_rows = []
    selection_errors = []
    lookback = int(PROTO['window']['lookback_days']) * 86400

    for st, fams in chosen.items():
        hist, _, _, herr = paged_markets('/historical/markets', {'limit': 1000, 'series_ticker': st})
        live, _, _, lerr = paged_markets('/markets', {'limit': 1000, 'series_ticker': st, 'status': 'settled'})
        if herr:
            selection_errors.append({'series_ticker': st, 'route': 'historical_market_list', 'error': herr})
        if lerr:
            selection_errors.append({'series_ticker': st, 'route': 'live_market_list', 'error': lerr})

        candidates = []
        hh = sorted((m for m in hist if m.get('ticker') and not is_mve(m)), key=lambda x: x['ticker'])
        ll = sorted((m for m in live if m.get('ticker') and not is_mve(m)), key=lambda x: x['ticker'])
        if hh:
            candidates.append(('historical', hh[0]))
        if ll:
            candidates.append(('live', ll[0]))

        for route, m in candidates:
            end_ts = market_end_ts(m)
            if not end_ts:
                market_rows.append({'series_ticker': st, 'families': fams, 'route': route, 'ticker': m.get('ticker'), 'status': 'NO_END_TS'})
                continue
            start_ts = end_ts - lookback
            t = trade_probe(route, m['ticker'], start_ts, end_ts)
            c = candle_probe(route, st, m['ticker'], start_ts, end_ts)
            for probe in (t, c):
                attempts += 1
                if probe['ok']:
                    successes += 1
                elif (probe.get('error') or {}).get('status') == 400:
                    contract_400 += 1
            market_rows.append({
                'series_ticker': st,
                'families': fams,
                'route': route,
                'ticker': m['ticker'],
                'market_open_time': m.get('open_time'),
                'market_close_time': m.get('close_time'),
                'window_start_ts': start_ts,
                'window_end_ts': end_ts,
                'trade_probe': t,
                'candle_probe': c,
            })

    success_rate = successes / attempts if attempts else 0.0
    min_rate = float(PROTO['technical_gate']['minimum_endpoint_success_rate'])
    max_400 = int(PROTO['technical_gate']['maximum_http_400_contract_errors'])
    decision = 'PASS_TECHNICAL_HISTORY_ENDPOINT_GATE' if attempts and success_rate >= min_rate and contract_400 <= max_400 else 'FAIL_TECHNICAL_HISTORY_ENDPOINT_GATE'

    out = {
        'artifact': 'W4A_KALSHI_HISTORY_PROBE_RESULT',
        'version': 'W4A-KHPR-v1.0',
        'date_utc': datetime.now(timezone.utc).isoformat(),
        'protocol_version': PROTO['version'],
        'performance_blind': True,
        'linked_asset_outcomes_read': False,
        'raw_semantic_counts_promoted': False,
        'selected_unique_series': len(chosen),
        'selected_series': [{'series_ticker': st, 'families': fams} for st, fams in chosen.items()],
        'market_probes': len(market_rows),
        'attempted_endpoint_requests': attempts,
        'successful_endpoint_requests': successes,
        'endpoint_success_rate': success_rate,
        'contract_400_count': contract_400,
        'selection_error_count': len(selection_errors),
        'selection_errors': selection_errors,
        'technical_gate_decision': decision,
        'market_results': market_rows,
        'interpretation': 'Technical pre-outcome API feasibility probe only. It does not establish semantic validity, full-population T-10d coverage, official event truth, linked-asset mapping or N_final_backtestable.'
    }
    (REG / 'w4a_kalshi_history_probe_result_v1.json').write_text(json.dumps(out, indent=2, sort_keys=True) + '\n')
    print(json.dumps({k: out[k] for k in ['selected_unique_series','market_probes','attempted_endpoint_requests','successful_endpoint_requests','endpoint_success_rate','contract_400_count','selection_error_count','technical_gate_decision']}, indent=2, sort_keys=True))
    if decision.startswith('FAIL'):
        raise SystemExit(2)


if __name__ == '__main__':
    main()
