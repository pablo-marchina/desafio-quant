#!/usr/bin/env python3
"""W2C-PIT-A-v1.0 public Polymarket historical-observability collector.

Reads only the frozen semantic review queue and public Polymarket APIs. It does
not fetch linked-asset returns, score F1-F9/IAS, or select W3 families.
"""
from __future__ import annotations
import csv, gzip, io, json, time, urllib.error, urllib.parse, urllib.request
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

PROTOCOL = Path('registry/w2c_pit_platform_protocol_v1_0.json')
INPUT = Path('registry/w2c_semantic_review_queue.csv.gz')
OUT_EVENTS = Path('registry/w2c_pit_platform_events.csv.gz')
OUT_SUMMARY = Path('registry/w2c_pit_platform_summary.json')
VERSION = 'W2C-PIT-A-v1.0'
UA = 'ARGOS-W2C-PIT-A/1.0 reproducible research'


def iso_from_epoch(x):
    if x in (None, ''): return ''
    try:
        return datetime.fromtimestamp(float(x), tz=timezone.utc).isoformat().replace('+00:00','Z')
    except Exception:
        return ''


def epoch_from_iso(s):
    if not s: return None
    try:
        return datetime.fromisoformat(str(s).replace('Z','+00:00')).timestamp()
    except Exception:
        return None


def parse_tokens(v):
    if v is None: return []
    if isinstance(v, list): return [str(x) for x in v if str(x)]
    s = str(v).strip()
    if not s: return []
    try:
        x = json.loads(s)
        if isinstance(x, list): return [str(z) for z in x if str(z)]
    except Exception:
        pass
    return [z.strip().strip('"\'') for z in s.strip('[]').split(',') if z.strip().strip('"\'')]


def request_json(url, attempts=5, timeout=25, sleep_base=0.8):
    errors = []
    for i in range(attempts):
        try:
            req = urllib.request.Request(url, headers={'User-Agent': UA, 'Accept': 'application/json'})
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                data = json.loads(resp.read().decode('utf-8'))
            time.sleep(0.05)
            return data, errors
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, json.JSONDecodeError) as e:
            errors.append(f'{type(e).__name__}:{getattr(e,"code","")}')
            retry = True
            if isinstance(e, urllib.error.HTTPError) and e.code not in (429,500,502,503,504):
                retry = False
            if not retry or i == attempts-1:
                return None, errors
            time.sleep(sleep_base*(2**i))
    return None, errors


def event_identifiers(gamma):
    markets = gamma.get('markets') or [] if isinstance(gamma, dict) else []
    conds, tokens, accepting = [], [], []
    enabled = 0
    for m in markets:
        cid = str(m.get('conditionId') or '')
        if cid: conds.append(cid)
        toks = parse_tokens(m.get('clobTokenIds'))
        tokens.extend(toks)
        if m.get('enableOrderBook') is True: enabled += 1
        a = epoch_from_iso(m.get('acceptingOrdersTimestamp'))
        if a is not None: accepting.append(a)
    return {
        'markets': markets,
        'condition_ids': sorted(set(conds)),
        'tokens': sorted(set(tokens)),
        'accepting_epochs': accepting,
        'enabled_count': enabled,
    }


def summarize_observability(accepting_epochs, trade_timestamps, price_timestamps, gamma_ok=True, network_errors=0, trade_truncated=False):
    trade_ts = [float(x) for x in trade_timestamps if x not in (None,'')]
    price_ts = [float(x) for x in price_timestamps if x not in (None,'')]
    accepting = [float(x) for x in accepting_epochs if x not in (None,'')]
    observed = bool(trade_ts or price_ts)
    all_evidence = trade_ts + price_ts + accepting
    if network_errors:
        status = 'NETWORK_UNRESOLVED'
    elif observed:
        status = 'PASS_PLATFORM_HISTORY_OBSERVED'
    elif accepting:
        status = 'METADATA_ONLY_UNRESOLVED'
    else:
        status = 'NO_PLATFORM_HISTORY_RECOVERED'
    return {
        'pit_a_status': status,
        'accepting_orders_timestamp_min': iso_from_epoch(min(accepting)) if accepting else '',
        'first_public_trade_observed_utc': iso_from_epoch(min(trade_ts)) if trade_ts else '',
        'first_public_price_observed_utc': iso_from_epoch(min(price_ts)) if price_ts else '',
        'platform_earliest_evidence_utc': iso_from_epoch(min(all_evidence)) if all_evidence else '',
        'platform_historical_observation_present': observed,
        'trade_history_truncated': bool(trade_truncated),
    }


def read_gz(path):
    with gzip.open(path,'rt',encoding='utf-8',newline='') as fh:
        return list(csv.DictReader(fh))


def write_gz(path, rows, fields):
    sio = io.StringIO(newline='')
    w = csv.DictWriter(sio, fieldnames=fields, extrasaction='ignore'); w.writeheader(); w.writerows(rows)
    with path.open('wb') as raw:
        with gzip.GzipFile(filename='', mode='wb', fileobj=raw, mtime=0) as gz:
            gz.write(sio.getvalue().encode())


def main():
    p = json.loads(PROTOCOL.read_text(encoding='utf-8'))
    assert p['version'] == VERSION and p['performance_blind'] is True
    rows = read_gz(INPUT)
    out = []
    for idx, r in enumerate(rows, 1):
        eid = str(r['event_id'])
        errs = []
        gamma_url = f'https://gamma-api.polymarket.com/events/{urllib.parse.quote(eid)}'
        gamma, e = request_json(gamma_url); errs.extend(e)
        ids = event_identifiers(gamma or {})

        trade_ts = []
        trade_rows = 0
        trade_truncated = False
        if gamma is not None:
            u = 'https://data-api.polymarket.com/trades?' + urllib.parse.urlencode({'eventId':eid,'limit':10000,'offset':0,'takerOnly':'false'})
            trades, e = request_json(u); errs.extend(e)
            if isinstance(trades, list):
                trade_rows = len(trades); trade_truncated = trade_rows >= 10000
                for t in trades:
                    ts = t.get('timestamp')
                    if ts is not None:
                        try: trade_ts.append(float(ts))
                        except Exception: pass

        price_ts = []
        tokens_with_history = 0
        for token in ids['tokens']:
            u = 'https://clob.polymarket.com/prices-history?' + urllib.parse.urlencode({'market':token,'interval':'max'})
            hist, e = request_json(u); errs.extend(e)
            points = (hist or {}).get('history') if isinstance(hist, dict) else None
            if isinstance(points, list) and points:
                local = []
                for z in points:
                    t = z.get('t')
                    if t is not None:
                        try: local.append(float(t))
                        except Exception: pass
                if local:
                    tokens_with_history += 1; price_ts.extend(local)

        obs = summarize_observability(ids['accepting_epochs'], trade_ts, price_ts, gamma is not None, len(errs), trade_truncated)
        out.append({
            'event_id':eid,
            'resolved_family':r.get('resolved_family',''),
            'independence_cluster_id':r.get('independence_cluster_id',''),
            'title':r.get('title',''),
            'semantic_end_utc':r.get('end_utc',''),
            'gamma_fetch_status':'PASS' if gamma is not None else 'FAIL',
            'nested_market_count':len(ids['markets']),
            'orderbook_enabled_market_count':ids['enabled_count'],
            'condition_ids':'|'.join(ids['condition_ids']),
            'clob_token_ids':'|'.join(ids['tokens']),
            'accepting_orders_timestamp_min':obs['accepting_orders_timestamp_min'],
            'public_trade_rows_observed':trade_rows,
            'trade_history_truncated':str(obs['trade_history_truncated']).lower(),
            'first_public_trade_observed_utc':obs['first_public_trade_observed_utc'],
            'tokens_with_price_history':tokens_with_history,
            'first_public_price_observed_utc':obs['first_public_price_observed_utc'],
            'platform_earliest_evidence_utc':obs['platform_earliest_evidence_utc'],
            'platform_historical_observation_present':str(obs['platform_historical_observation_present']).lower(),
            'pit_a_status':obs['pit_a_status'],
            'network_error_count':len(errs),
            'network_error_types':'|'.join(sorted(set(errs))),
        })
        if idx % 25 == 0:
            print(f'processed {idx}/{len(rows)}', flush=True)

    fields = ['event_id','resolved_family','independence_cluster_id','title','semantic_end_utc','gamma_fetch_status','nested_market_count','orderbook_enabled_market_count','condition_ids','clob_token_ids','accepting_orders_timestamp_min','public_trade_rows_observed','trade_history_truncated','first_public_trade_observed_utc','tokens_with_price_history','first_public_price_observed_utc','platform_earliest_evidence_utc','platform_historical_observation_present','pit_a_status','network_error_count','network_error_types']
    write_gz(OUT_EVENTS, out, fields)

    fam = defaultdict(lambda: defaultdict(int))
    for r in out:
        f = r['resolved_family']; fam[f]['selected_events'] += 1
        if r['gamma_fetch_status']=='PASS': fam[f]['gamma_coverage_count'] += 1
        if r['platform_historical_observation_present']=='true': fam[f]['platform_history_observed_count'] += 1
        if r['first_public_trade_observed_utc']: fam[f]['trade_observed_count'] += 1
        if r['first_public_price_observed_utc']: fam[f]['price_history_observed_count'] += 1
        if r['pit_a_status']=='NETWORK_UNRESOLVED': fam[f]['network_unresolved_count'] += 1
        if r['trade_history_truncated']=='true': fam[f]['trade_history_truncated_count'] += 1
    family_summary = {}
    for f,d in sorted(fam.items()):
        n=d['selected_events']; dd=dict(d)
        dd['gamma_coverage_rate']=dd.get('gamma_coverage_count',0)/n if n else None
        dd['platform_history_observed_rate']=dd.get('platform_history_observed_count',0)/n if n else None
        family_summary[f]=dd
    summary = {
        'artifact':'W2C_PIT_PLATFORM_EVIDENCE_RUN',
        'version':'W2C-PIT-A-RUN-v1.0',
        'protocol_version':VERSION,
        'performance_blind':True,
        'science_reopened':False,
        'input_rows':len(rows),
        'output_rows':len(out),
        'family_summary':family_summary,
        'f1_f9_scored':False,
        'ias_computed':False,
        'linked_asset_realized_returns_read':False,
        'w3_family_selected':False,
        'interpretation':'PIT-A is public Polymarket historical-observability evidence only. Official revelation/resolution/mapping evidence remains blocked pending PIT-B freeze.'
    }
    OUT_SUMMARY.write_text(json.dumps(summary, indent=2, ensure_ascii=False)+'\n', encoding='utf-8')
    print(json.dumps(summary,indent=2))

if __name__ == '__main__': main()
