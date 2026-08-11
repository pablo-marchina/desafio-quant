#!/usr/bin/env python3
import argparse,csv,gzip,hashlib,json,os,re,time,urllib.parse,urllib.request
from collections import Counter
from datetime import datetime,timezone

GAMMA='https://gamma-api.polymarket.com/markets/{id}'
TRADES='https://data-api.polymarket.com/trades'
UA='ARGOS-IC02/1.0 research audit'
HEX40=re.compile(r'^0x[a-fA-F0-9]{40}$')
HEX64=re.compile(r'^0x[a-fA-F0-9]{64}$')
REQ_FIELDS=['proxyWallet','side','asset','conditionId','size','price','timestamp','outcome','outcomeIndex','transactionHash']
CUTOVER=1777374000  # 2026-04-28 11:00:00 UTC; official migration approximate cutover


def get_json(url,retries=5):
    last=None
    for i in range(retries):
        try:
            req=urllib.request.Request(url,headers={'User-Agent':UA,'Accept':'application/json'})
            with urllib.request.urlopen(req,timeout=45) as r:
                return json.load(r)
        except Exception as e:
            last=e; time.sleep(min(2**i,10))
    raise RuntimeError(f'GET failed {url}: {last}')


def sha256_file(path):
    h=hashlib.sha256()
    with open(path,'rb') as f:
        for b in iter(lambda:f.read(1024*1024),b''): h.update(b)
    return h.hexdigest()


def iso_to_ts(s): return int(datetime.fromisoformat(s.replace('Z','+00:00')).timestamp())

def parse_jsonish(v):
    if isinstance(v,list): return v
    if not v: return []
    try:
        x=json.loads(v); return x if isinstance(x,list) else []
    except Exception: return []


def trade_key(x):
    return tuple(str(x.get(k,'')) for k in ['transactionHash','proxyWallet','asset','side','size','price','timestamp','outcomeIndex'])


def fetch_page(condition_id,offset):
    q=urllib.parse.urlencode({'market':condition_id,'limit':10000,'offset':offset,'takerOnly':'true'})
    x=get_json(TRADES+'?'+q)
    if not isinstance(x,list): raise RuntimeError('Data API /trades response is not a list')
    return x


def audit_market(ev,rawdir):
    mid=ev['market_id']; cutoff=iso_to_ts(ev['safe_cutoff_utc'])
    meta=get_json(GAMMA.format(id=mid))
    condition=str(meta.get('conditionId') or '')
    tokens={str(x) for x in parse_jsonish(meta.get('clobTokenIds'))}
    outcomes=parse_jsonish(meta.get('outcomes'))
    os.makedirs(os.path.join(rawdir,'gamma'),exist_ok=True); os.makedirs(os.path.join(rawdir,'trades'),exist_ok=True)
    mp=os.path.join(rawdir,'gamma',mid+'.json')
    with open(mp,'w',encoding='utf-8') as f: json.dump(meta,f,sort_keys=True,separators=(',',':'))
    pages=[]
    if HEX64.match(condition):
        p0=fetch_page(condition,0); pages.append(p0)
        if len(p0)==10000: pages.append(fetch_page(condition,10000))
    rows=[x for p in pages for x in p]
    tp=os.path.join(rawdir,'trades',mid+'.jsonl.gz')
    with gzip.open(tp,'wt',encoding='utf-8') as f:
        for x in rows: f.write(json.dumps(x,sort_keys=True,separators=(',',':'))+'\n')
    keys=[trade_key(x) for x in rows]
    unique=set(keys); exact_dups=len(keys)-len(unique)
    txs=[str(x.get('transactionHash') or '') for x in rows]
    wallets=[str(x.get('proxyWallet') or '') for x in rows]
    sides=Counter(str(x.get('side')) for x in rows)
    ts=[int(x.get('timestamp')) for x in rows if str(x.get('timestamp','')).isdigit()]
    pre=[x for x in rows if str(x.get('timestamp','')).isdigit() and int(x['timestamp'])<=cutoff]
    missing=sum(1 for x in rows if any(x.get(k) is None or x.get(k)=='' for k in REQ_FIELDS))
    invalid_price=sum(1 for x in rows if not isinstance(x.get('price'),(int,float)) or not (0 <= float(x['price']) <= 1))
    invalid_size=sum(1 for x in rows if not isinstance(x.get('size'),(int,float)) or float(x['size'])<=0)
    bad_wallet=sum(1 for w in wallets if not HEX40.match(w))
    bad_tx=sum(1 for t in txs if not HEX64.match(t))
    cond_mismatch=sum(1 for x in rows if str(x.get('conditionId'))!=condition)
    asset_mismatch=sum(1 for x in rows if tokens and str(x.get('asset')) not in tokens)
    page_boundary_dup=0
    if len(pages)==2: page_boundary_dup=len(set(map(trade_key,pages[0])) & set(map(trade_key,pages[1])))
    truncation_risk=(len(pages)==2 and len(pages[1])==10000)
    era='V1' if cutoff < CUTOVER else 'V2'
    status='PASS_STRUCTURAL'
    if not HEX64.match(condition): status='FAIL_METADATA'
    elif truncation_risk: status='CONDITIONAL_TRUNCATION_RISK'
    elif missing or invalid_price or invalid_size or bad_wallet or bad_tx or cond_mismatch or asset_mismatch: status='CONDITIONAL_SCHEMA_ANOMALY'
    elif len(rows)==0: status='CONDITIONAL_ZERO_TRADES'
    return {
      'market_id':mid,'event_key':ev['event_key'],'ticker':ev['ticker'],'company_event_date':ev['company_event_date'],
      'safe_cutoff_utc':ev['safe_cutoff_utc'],'era_by_cutoff':era,'condition_id':condition,'token_count':len(tokens),
      'outcome_count':len(outcomes),'total_rows':len(rows),'pre_cutoff_rows':len(pre),'page_count':len(pages),
      'page0_rows':len(pages[0]) if pages else 0,'page1_rows':len(pages[1]) if len(pages)>1 else 0,
      'truncation_risk':truncation_risk,'exact_duplicate_rows':exact_dups,'page_boundary_duplicate_keys':page_boundary_dup,
      'unique_tx_hashes':len(set(txs)),'unique_wallets':len(set(wallets)),'buy_rows':sides.get('BUY',0),'sell_rows':sides.get('SELL',0),
      'missing_required_field_rows':missing,'invalid_price_rows':invalid_price,'invalid_size_rows':invalid_size,
      'bad_wallet_rows':bad_wallet,'bad_txhash_rows':bad_tx,'condition_mismatch_rows':cond_mismatch,'asset_not_in_market_tokens_rows':asset_mismatch,
      'min_timestamp':min(ts) if ts else '','max_timestamp':max(ts) if ts else '','gamma_sha256':sha256_file(mp),'trades_sha256':sha256_file(tp),
      'status':status}


def write_csv(path,rows):
    os.makedirs(os.path.dirname(path),exist_ok=True)
    fields=list(rows[0].keys()) if rows else []
    with open(path,'w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=fields); w.writeheader(); w.writerows(rows)


def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--input',required=True); ap.add_argument('--output-dir',required=True); a=ap.parse_args()
    os.makedirs(a.output_dir,exist_ok=True); raw=os.path.join(a.output_dir,'raw')
    with open(a.input,newline='',encoding='utf-8') as f: events=list(csv.DictReader(f))
    results=[]; errors=[]
    for i,ev in enumerate(events,1):
        print(f'[{i}/{len(events)}] {ev["event_key"]}',flush=True)
        try: results.append(audit_market(ev,raw))
        except Exception as e:
            errors.append({'market_id':ev['market_id'],'event_key':ev['event_key'],'error':repr(e)})
            results.append({**{k:ev.get(k,'') for k in ['market_id','event_key','ticker','company_event_date','safe_cutoff_utc']},'status':'ERROR'})
    audit_path=os.path.join(a.output_dir,'ic02_trade_tape_audit.csv'); write_csv(audit_path,results)
    if errors: write_csv(os.path.join(a.output_dir,'ic02_errors.csv'),errors)
    manifest=[]
    for root,_,files in os.walk(raw):
        for fn in sorted(files):
            p=os.path.join(root,fn); manifest.append({'path':os.path.relpath(p,a.output_dir),'bytes':os.path.getsize(p),'sha256':sha256_file(p)})
    if manifest: write_csv(os.path.join(a.output_dir,'ic02_raw_manifest.csv'),manifest)
    ok=[r for r in results if r.get('status')=='PASS_STRUCTURAL']
    trunc=[r for r in results if r.get('truncation_risk') is True]
    zero=[r for r in results if r.get('status')=='CONDITIONAL_ZERO_TRADES']
    anomalies=[r for r in results if str(r.get('status','')).startswith('CONDITIONAL_SCHEMA')]
    final='PASS_TAPE_STRUCTURAL_DIRECTION_PENDING_IC03' if len(ok)==len(results) else 'CONDITIONAL_IC02'
    report=f'''# ARGOS — IC-02 Empirical Polymarket Trade Tape Audit\n\nGenerated UTC: {datetime.now(timezone.utc).isoformat()}  \nInput events: {len(events)}  \nFinal decision: **{final}**\n\n## Scope\nAudits the public Polymarket Data API trade tape for the complete frozen 117-event ARGOS panel, without consulting event outcomes or post-event equity returns. Each Gamma market ID is resolved to its conditionId/token IDs, then `/trades` is retrieved with explicit `takerOnly=true`, `limit=10000`, and offset pagination. Raw responses are preserved as compressed workflow artifacts and hashed.\n\n## Results\n- structurally clean markets: {len(ok)}/{len(results)}\n- API/runtime errors: {len(errors)}\n- markets with documented offset truncation risk: {len(trunc)}\n- markets with zero returned trades: {len(zero)}\n- markets with schema/semantic anomalies: {len(anomalies)}\n- total returned trade rows: {sum(int(r.get('total_rows') or 0) for r in results):,}\n- total pre-cutoff rows: {sum(int(r.get('pre_cutoff_rows') or 0) for r in results):,}\n\n## Hard interpretation boundary\nThis audit can establish retrieval coverage, schema consistency, token/condition mapping, pagination limits, timestamps, wallet/transaction-hash availability and reproducibility. It **does not yet declare Data API `side` to be ground-truth aggressor direction**. That semantic claim remains gated on IC-03 reconciliation against V1/V2 `OrderFilled` settlement events.\n\n## API limitations tested\nThe public Data API documents `limit <= 10000`, `offset <= 10000` and `takerOnly=true` by default. Therefore a market whose second 10,000-row page is also full is classified as truncation risk rather than silently treated as complete.\n\n## Provenance\n- Polymarket API overview: https://docs.polymarket.com/api-reference/introduction\n- Data API trades: https://docs.polymarket.com/api-reference/core/get-trades-for-a-user-or-markets\n- Rate limits: https://docs.polymarket.com/api-reference/rate-limits\n- Gamma market by id: https://docs.polymarket.com/api-reference/markets/get-market-by-id\n- CLOB V2 migration: https://docs.polymarket.com/v2-migration\n- Contracts: https://docs.polymarket.com/resources/contracts\n\n## Next gate\nIf no truncation or unreconciled structural defect exists, IC-02 closes for **public tape availability** and IC-03 must establish V1/V2 settlement-side semantics before signed-flow features can be frozen.\n'''
    with open(os.path.join(a.output_dir,'ic02_report.md'),'w',encoding='utf-8') as f: f.write(report)
    summary={'decision':final,'events':len(events),'clean':len(ok),'errors':len(errors),'truncation_risk':len(trunc),'zero_trades':len(zero),'schema_anomalies':len(anomalies),'total_rows':sum(int(r.get('total_rows') or 0) for r in results),'pre_cutoff_rows':sum(int(r.get('pre_cutoff_rows') or 0) for r in results)}
    with open(os.path.join(a.output_dir,'ic02_summary.json'),'w') as f: json.dump(summary,f,indent=2)
    print(json.dumps(summary,indent=2))
    if errors: raise SystemExit(2)

if __name__=='__main__': main()
