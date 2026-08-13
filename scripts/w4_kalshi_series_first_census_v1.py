#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import time
from collections import Counter, defaultdict
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
REG = ROOT / 'registry'
P = json.loads((REG / 'w4_backtest_expansion_research_protocol_v1.json').read_text())
FAMS = P['frozen_family_dictionary']
BASE = 'https://external-api.kalshi.com/trade-api/v2'
UA = 'ARGOS-W4-series-first/1.1'


class APIError(RuntimeError):
    def __init__(self, url: str, status: int | None, detail: str):
        super().__init__(f'{url}: HTTP {status}: {detail}' if status else f'{url}: {detail}')
        self.url = url
        self.status = status
        self.detail = detail


def get_json(url: str, retries: int = 4):
    """GET JSON with bounded retries for transient failures, never hiding 4xx contract errors."""
    last = None
    for i in range(retries):
        try:
            req = Request(url, headers={'User-Agent': UA, 'Accept': 'application/json'})
            with urlopen(req, timeout=45) as r:
                return json.loads(r.read().decode())
        except HTTPError as e:
            body = ''
            try:
                body = e.read().decode(errors='replace')[:1000]
            except Exception:
                pass
            if 400 <= e.code < 500 and e.code != 429:
                raise APIError(url, e.code, body or str(e)) from e
            last = APIError(url, e.code, body or str(e))
        except (URLError, TimeoutError, OSError, json.JSONDecodeError) as e:
            last = APIError(url, None, str(e))
        if i + 1 < retries:
            time.sleep(1.2 * (i + 1))
    raise last or APIError(url, None, 'unknown request failure')


def norm(s):
    return re.sub(r'\s+', ' ', re.sub(r'[^a-z0-9%+.-]+', ' ', (s or '').lower())).strip()


def classify(text):
    t = norm(text)
    out = []
    for fam, kws in FAMS.items():
        if any(norm(k) in t for k in kws):
            out.append(fam)
    return out


def is_mve_market(m):
    """Exclude multivariate/combo markets locally so API filter exclusivity cannot bias discovery."""
    return bool(m.get('mve_collection_ticker') or m.get('mve_selected_legs'))


def paged_markets(path, base_query, max_pages):
    cursor = ''
    page = 0
    markets = []
    while page < max_pages:
        q = dict(base_query)
        if cursor:
            q['cursor'] = cursor
        obj = get_json(BASE + path + '?' + urlencode(q))
        batch = obj.get('markets', [])
        markets.extend(batch)
        page += 1
        cursor = obj.get('cursor') or ''
        if not cursor or not batch:
            break
    return markets, page, bool(cursor)


def historical_markets(series_ticker, max_pages=500):
    # Kalshi documents filters on /historical/markets as mutually exclusive.
    # Therefore use series_ticker alone and remove MVE markets locally.
    return paged_markets(
        '/historical/markets',
        {'limit': 1000, 'series_ticker': series_ticker},
        max_pages,
    )


def live_settled_markets(series_ticker, max_pages=100):
    # Do not combine mve_filter with series filtering. MVE exclusion is local and auditable.
    return paged_markets(
        '/markets',
        {'limit': 1000, 'series_ticker': series_ticker, 'status': 'settled'},
        max_pages,
    )


def safe_route_fetch(route, series_ticker):
    fn = historical_markets if route == 'historical' else live_settled_markets
    try:
        markets, pages, truncated = fn(series_ticker)
        return {
            'ok': True,
            'markets': markets,
            'pages': pages,
            'truncated': truncated,
            'error': None,
        }
    except Exception as e:
        return {
            'ok': False,
            'markets': [],
            'pages': 0,
            'truncated': False,
            'error': str(e),
        }


def main():
    series_obj = get_json(BASE + '/series')
    series = series_obj.get('series', [])

    try:
        historical_cutoff = get_json(BASE + '/historical/cutoff')
        cutoff_error = None
    except Exception as e:
        historical_cutoff = None
        cutoff_error = str(e)

    selected = []
    for s in series:
        text = ' '.join([
            str(s.get('title') or ''),
            str(s.get('category') or ''),
            ' '.join(s.get('tags') or []),
        ])
        hits = classify(text)
        for fam in hits:
            selected.append({
                'family': fam,
                'series_ticker': s.get('ticker'),
                'series_title': s.get('title') or '',
                'frequency': s.get('frequency') or '',
                'category': s.get('category') or '',
            })

    series_hits = defaultdict(list)
    for r in selected:
        if r['series_ticker']:
            series_hits[r['series_ticker']].append(r['family'])

    event_sets = defaultdict(set)
    market_counts = Counter()
    telemetry = []
    route_errors = []
    complete = partial = failed = 0
    mve_filtered_total = 0

    for st, fams in sorted(series_hits.items()):
        hist = safe_route_fetch('historical', st)
        live = safe_route_fetch('live', st)

        if hist['ok'] and live['ok']:
            route_status = 'COMPLETE_BOTH_ROUTES'
            complete += 1
        elif hist['ok'] or live['ok']:
            route_status = 'PARTIAL_ONE_ROUTE'
            partial += 1
        else:
            route_status = 'FAILED_BOTH_ROUTES'
            failed += 1

        for route_name, route in [('historical', hist), ('live', live)]:
            if not route['ok']:
                route_errors.append({
                    'series_ticker': st,
                    'route': route_name,
                    'error': route['error'],
                })

        raw = hist['markets'] + live['markets']
        non_mve = [m for m in raw if not is_mve_market(m)]
        mve_filtered = len(raw) - len(non_mve)
        mve_filtered_total += mve_filtered
        mk = {m.get('ticker'): m for m in non_mve if m.get('ticker')}
        ev = {m.get('event_ticker') for m in mk.values() if m.get('event_ticker')}

        for fam in fams:
            event_sets[fam].update(ev)
            market_counts[fam] += len(mk)

        telemetry.append({
            'series_ticker': st,
            'families': sorted(set(fams)),
            'route_status': route_status,
            'historical_ok': hist['ok'],
            'live_ok': live['ok'],
            'historical_pages': hist['pages'],
            'live_pages': live['pages'],
            'historical_truncated': hist['truncated'],
            'live_truncated': live['truncated'],
            'historical_error': hist['error'],
            'live_error': live['error'],
            'raw_markets_before_local_mve_filter': len(raw),
            'mve_markets_filtered_locally': mve_filtered,
            'unique_markets': len(mk),
            'unique_events': len(ev),
        })

    accounted = complete + partial + failed
    out = {
        'artifact': 'W4_KALSHI_SERIES_FIRST_CAPACITY',
        'version': 'W4-KSF-v1.1',
        'performance_blind': True,
        'realized_linked_asset_returns_read': False,
        'frozen_family_dictionary_version': P['version'],
        'historical_cutoff': historical_cutoff,
        'historical_cutoff_error': cutoff_error,
        'series_total_returned': len(series),
        'classified_series_rows': len(selected),
        'classified_unique_series': len(series_hits),
        'accounted_unique_series': accounted,
        'complete_unique_series': complete,
        'partial_unique_series': partial,
        'failed_unique_series': failed,
        'route_error_count': len(route_errors),
        'route_errors': route_errors,
        'mve_markets_filtered_locally': mve_filtered_total,
        'family_capacity': {
            fam: {
                'unique_events': len(event_sets[fam]),
                'unique_markets': market_counts[fam],
            }
            for fam in sorted(event_sets)
        },
        'selected_series': selected,
        'telemetry': telemetry,
        'api_contract_note': 'Historical market filters are mutually exclusive; series_ticker is queried alone. Multivariate markets are excluded locally from returned records. Live and historical routes are merged because Kalshi partitions data at moving historical cutoffs.',
        'interpretation': 'Discovery capacity only. Series classification uses the already-frozen W4-BER-v1.0 dictionary. Event counts are not semantic-valid, PIT-certified, linked-asset-mapped or cross-venue-deduplicated backtest N.',
    }

    (REG / 'w4_kalshi_series_first_capacity_v1.json').write_text(
        json.dumps(out, indent=2, sort_keys=True) + '\n'
    )
    print(json.dumps({
        k: out[k]
        for k in [
            'series_total_returned',
            'classified_unique_series',
            'complete_unique_series',
            'partial_unique_series',
            'failed_unique_series',
            'route_error_count',
            'mve_markets_filtered_locally',
            'family_capacity',
        ]
    }, indent=2, sort_keys=True))


if __name__ == '__main__':
    main()
