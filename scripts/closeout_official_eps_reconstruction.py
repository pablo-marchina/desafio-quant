#!/usr/bin/env python3
from __future__ import annotations
import csv, hashlib, html, io, json, re, time, urllib.request
from collections import defaultdict
from datetime import datetime
from pathlib import Path

ROOT=Path('.')
SEED=ROOT/'registry/official_eps_pending_66_seed.csv'
OUT=ROOT/'registry/official_eps_closeout_66.csv'
SUMMARY=ROOT/'registry/official_eps_closeout_summary.json'
RAW=ROOT/'artifacts/closeout_eps/raw'
UA='ARGOS-QuantAI-2026 evidence-reconciliation research'
SEC_TICKERS='https://www.sec.gov/files/company_tickers.json'
SEC_SUB='https://data.sec.gov/submissions/CIK{cik:010d}.json'
SEC_ARCH='https://www.sec.gov/Archives/edgar/data/{cik}/{acc}/{name}'
FORMS={'8-K','6-K','10-Q','10-K','20-F','40-F'}
NON_GAAP_TERMS=[r'adjusted\s+(?:diluted\s+)?(?:earnings|income|net income)?\s*(?:per\s+(?:common\s+)?(?:diluted\s+)?share|eps)',r'non[-\s]?gaap\s+(?:diluted\s+)?(?:earnings|income|net income)?\s*(?:per\s+(?:diluted\s+)?share|eps)',r'core\s+(?:diluted\s+)?(?:earnings\s+)?(?:per\s+(?:diluted\s+)?share|eps)',r'adjusted\s+eps',r'non[-\s]?gaap\s+eps',r'core\s+eps']
GAAP_TERMS=[r'diluted\s+earnings\s+per\s+(?:common\s+)?share',r'earnings\s+per\s+diluted\s+(?:common\s+)?share',r'diluted\s+loss\s+per\s+(?:common\s+)?share',r'loss\s+per\s+diluted\s+(?:common\s+)?share',r'diluted\s+eps',r'eps']
NUM=r'(?P<num>\(?\s*[-+]?\$?\s*\d{1,3}(?:,\d{3})*(?:\.\d+)?\s*\)?)'

def sha_bytes(b): return hashlib.sha256(b).hexdigest()
def sha_file(p):
    h=hashlib.sha256()
    with open(p,'rb') as f:
        for x in iter(lambda:f.read(1<<20),b''): h.update(x)
    return h.hexdigest()
def get(url,retries=5):
    last=None
    for i in range(retries):
        try:
            req=urllib.request.Request(url,headers={'User-Agent':UA,'Accept':'*/*','Accept-Encoding':'identity'})
            with urllib.request.urlopen(req,timeout=40) as r: return r.read()
        except Exception as e:
            last=e; time.sleep(min(2**i,8))
    raise RuntimeError(f'GET {url}: {last}')
def get_json(url): return json.loads(get(url).decode('utf-8','replace'))
def html_to_text(b,name):
    if name.lower().endswith('.pdf'):
        try:
            from pypdf import PdfReader
            return '\n'.join((p.extract_text() or '') for p in PdfReader(io.BytesIO(b)).pages)
        except Exception: return ''
    s=b.decode('utf-8','replace')
    s=re.sub(r'(?is)<script.*?</script>|<style.*?</style>',' ',s)
    s=re.sub(r'(?s)<[^>]+>',' ',s); s=html.unescape(s).replace('\xa0',' ')
    return re.sub(r'\s+',' ',s).strip()
def parse_num(s):
    t=s.strip(); neg=t.startswith('(') and t.endswith(')'); t=re.sub(r'[$,\s()]','',t)
    try: v=float(t)
    except: return None
    return -abs(v) if neg else v
def load_rows():
    with open(SEED,newline='',encoding='utf-8') as f: return list(csv.DictReader(f))
def ticker_map():
    obj=get_json(SEC_TICKERS); out={}
    for r in obj.values(): out[str(r['ticker']).upper()]=int(r['cik_str'])
    return out
def filing_candidates(cik,event_date):
    js=get_json(SEC_SUB.format(cik=cik)); rec=js.get('filings',{}).get('recent',{}); keys=['accessionNumber','filingDate','form','primaryDocument']; rows=[]
    n=len(rec.get('accessionNumber',[])); ed=datetime.strptime(event_date,'%Y-%m-%d').date()
    for i in range(n):
        r={k:(rec.get(k,['']*n)[i] if i<len(rec.get(k,[])) else '') for k in keys}
        if r['form'] not in FORMS: continue
        try: fd=datetime.strptime(r['filingDate'],'%Y-%m-%d').date()
        except: continue
        delta=(fd-ed).days
        if -2<=delta<=7: r['delta_days']=delta; rows.append(r)
    rows.sort(key=lambda r:(abs(r['delta_days']),0 if r['form'] in {'8-K','6-K'} else 1,r['filingDate']))
    return rows[:5]
def filing_docs(cik,filing):
    acc_dash=filing['accessionNumber']; acc=acc_dash.replace('-',''); index_url=f'https://www.sec.gov/Archives/edgar/data/{cik}/{acc}/index.json'; names=[]
    try:
        idx=get_json(index_url)
        for item in idx.get('directory',{}).get('item',[]):
            name=str(item.get('name','')); low=name.lower()
            if low.endswith(('.htm','.html','.txt','.pdf')): names.append(name)
    except Exception: pass
    primary=filing.get('primaryDocument','')
    if primary and primary not in names: names.insert(0,primary)
    def rank(n):
        l=n.lower(); return (0 if re.search(r'(ex(?:hibit)?[-_]?99|99[-_.]?1|earnings|press|release|results)',l) else 1,0 if n==primary else 1,n)
    names=sorted(set(names),key=rank)[:10]
    return [(n,SEC_ARCH.format(cik=cik,acc=acc,name=n),acc_dash) for n in names]
def metric_patterns(metric):
    terms=NON_GAAP_TERMS if metric=='non_gaap_eps' else GAAP_TERMS; pats=[]
    for term in terms:
        pats.append(('forward',re.compile(rf'(?i)(?P<phrase>{term}).{{0,45}}?{NUM}')))
        pats.append(('reverse',re.compile(rf'(?i){NUM}.{{0,35}}?(?P<phrase>{term})')))
    return pats
def candidate_from_match(text,m,direction,metric,source_url,accession,doc_name,event_year):
    val=parse_num(m.group('num'))
    if val is None or abs(val)>100: return None
    ctx=text[max(0,m.start()-450):min(len(text),m.end()+450)]; low=ctx.lower(); phrase=m.group('phrase'); immediate=text[max(0,m.start()-70):min(len(text),m.end()+70)].lower()
    if metric=='gaap_eps' and re.search(r'adjusted|non[-\s]?gaap|core',immediate): return None
    score=24.0
    if re.search(r'quarter|three months|q[1-4]',low): score+=5
    if str(event_year) in low: score+=4
    if m.start()<15000: score+=4
    if re.search(r'ex(?:hibit)?[-_]?99|99[-_.]?1|earnings|press|release|results',doc_name.lower()): score+=5
    pre=text[max(0,m.start()-220):m.start()].lower()
    if re.search(r'guidance|outlook|expects|forecast|full[- ]year guidance',pre): score-=14
    if re.search(r'year[- ]ago|prior year|last year',pre[-100:]): score-=6
    return {'value':val,'score':score,'direction':direction,'phrase':phrase[:120],'context':ctx[:900],'source_url':source_url,'accession_number':accession,'document_name':doc_name}
def select_candidate(cands):
    if not cands: return None,[],'NO_CANDIDATES'
    groups=defaultdict(list)
    for c in cands: groups[round(c['value'],4)].append(c)
    ranked=[]
    for v,xs in groups.items():
        docs=len({x['source_url'] for x in xs}); best=max(x['score'] for x in xs); total=best+min(8,4*(docs-1))+min(4,len(xs)-1); bestrow=max(xs,key=lambda x:x['score']).copy(); bestrow.update({'group_score':total,'occurrences':len(xs),'documents':docs}); ranked.append(bestrow)
    ranked.sort(key=lambda x:(-x['group_score'],x['value'])); top=ranked[0]; second=ranked[1]['group_score'] if len(ranked)>1 else -999; margin=top['group_score']-second; top['margin']=margin
    if top['group_score']>=34 and (margin>=6 or top['documents']>=2): return top,ranked[:8],'AUTO_VALIDATED_OFFICIAL_SOURCE'
    return None,ranked[:8],'AMBIGUOUS_MANUAL_REVIEW'
def reconstruct(row,tmap):
    ticker=row['ticker'].upper(); event_date=row['company_event_date']; metric=row['metric']; base={k:row.get(k,'') for k in ['index','market_id','event_key','ticker','company_event_date','metric','contract_operator','contract_threshold_eps','polymarket_outcome_label']}
    base.update({'official_eps_actual':'','official_eps_status':'','reconstructed_outcome_label':'','reconstructed_matches_polymarket':'','official_document_url':'','official_document_sha256':'','accession_number':'','evidence_phrase':'','evidence_context':'','candidate_score':'','candidate_margin':'','candidate_count_total':0,'top_candidates_json':'[]','validation_method':''})
    cik=tmap.get(ticker)
    if not cik: base['official_eps_status']='NO_SEC_TICKER_MAPPING'; return base,[]
    patterns=metric_patterns(metric); cands=[]; rawrefs=[]
    try: filings=filing_candidates(cik,event_date)
    except Exception as e: base['official_eps_status']='SEC_SUBMISSIONS_ERROR'; base['evidence_context']=repr(e)[:500]; return base,[]
    for filing in filings:
        for name,url,acc in filing_docs(cik,filing):
            try: b=get(url); text=html_to_text(b,name)
            except Exception: continue
            if not text or len(text)<200: continue
            p=RAW/str(row['market_id']); p.mkdir(parents=True,exist_ok=True); safe=re.sub(r'[^A-Za-z0-9._-]+','_',name)[:120]; rp=p/safe; rp.write_bytes(b); rawrefs.append({'path':str(rp),'sha256':sha_bytes(b),'url':url})
            for direction,pat in patterns:
                for m in pat.finditer(text):
                    c=candidate_from_match(text,m,direction,metric,url,acc,name,event_date[:4])
                    if c: cands.append(c)
    chosen,ranked,status=select_candidate(cands); base['candidate_count_total']=len(cands); base['top_candidates_json']=json.dumps([{k:x[k] for k in ['value','group_score','margin','occurrences','documents','phrase','source_url'] if k in x} for x in ranked],ensure_ascii=False); base['validation_method']='closeout_official_filing_metric_context_v1'
    if chosen:
        v=chosen['value']; th=float(row['contract_threshold_eps']); op=row['contract_operator']; recon=1 if (v>th if op=='>' else v>=th) else 0
        base.update({'official_eps_actual':v,'official_eps_status':status,'reconstructed_outcome_label':recon,'reconstructed_matches_polymarket':str(recon==int(float(row['polymarket_outcome_label']))).lower(),'official_document_url':chosen['source_url'],'accession_number':chosen['accession_number'],'evidence_phrase':chosen['phrase'],'evidence_context':chosen['context'],'candidate_score':chosen['group_score'],'candidate_margin':chosen['margin']})
        for rr in rawrefs:
            if rr['url']==chosen['source_url']: base['official_document_sha256']=rr['sha256']; break
    else: base['official_eps_status']=status
    return base,rawrefs
def write_csv(path,rows):
    path.parent.mkdir(parents=True,exist_ok=True); fields=[]
    for r in rows:
        for k in r:
            if k not in fields: fields.append(k)
    with open(path,'w',newline='',encoding='utf-8') as f: w=csv.DictWriter(f,fieldnames=fields); w.writeheader(); w.writerows(rows)
def main():
    RAW.mkdir(parents=True,exist_ok=True); rows=load_rows()
    if len(rows)!=66: raise RuntimeError(f'expected 66 rows, got {len(rows)}')
    tmap=ticker_map(); out=[]; manifest=[]
    for i,row in enumerate(rows,1):
        print(f'[{i}/66] {row["event_key"]}',flush=True); r,refs=reconstruct(row,tmap); out.append(r); manifest.extend(refs); time.sleep(0.11)
    write_csv(OUT,out); write_csv(ROOT/'registry/official_eps_closeout_raw_manifest.csv',manifest)
    validated=[r for r in out if r['official_eps_status']=='AUTO_VALIDATED_OFFICIAL_SOURCE']; matches=[r for r in validated if r['reconstructed_matches_polymarket']=='true']; mism=[r for r in validated if r['reconstructed_matches_polymarket']=='false']; pending=[r for r in out if r['official_eps_status']!='AUTO_VALIDATED_OFFICIAL_SOURCE']
    summary={'artifact':'POST_H2_FAIL_EPS_RECONCILIATION','seed_events':66,'auto_validated_new':len(validated),'remaining_pending':len(pending),'new_matches_polymarket':len(matches),'new_mismatches_polymarket':len(mism),'historical_validated':51,'population_validated_total':51+len(validated),'population_complete':len(pending)==0,'selection_used_polymarket_outcome':False,'policy':'Official metric/quarter context selects EPS; Polymarket label is compared only after selection.','remaining_event_keys':[r['event_key'] for r in pending],'mismatch_event_keys':[r['event_key'] for r in mism],'output_sha256':sha_file(OUT),'raw_manifest_sha256':sha_file(ROOT/'registry/official_eps_closeout_raw_manifest.csv'),'decision':'PASS_POPULATION_COMPLETE' if not pending else 'PARTIAL_FAIL_CLOSED_RESIDUAL_MANUAL_REVIEW'}
    SUMMARY.write_text(json.dumps(summary,indent=2,sort_keys=True),encoding='utf-8'); print(json.dumps(summary,indent=2),flush=True)
if __name__=='__main__': main()
