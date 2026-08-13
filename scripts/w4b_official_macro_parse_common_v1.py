#!/usr/bin/env python3
from __future__ import annotations
import hashlib,re,time
from datetime import date,datetime,timezone
from html.parser import HTMLParser
from urllib.error import HTTPError,URLError
from urllib.request import Request,urlopen
MONTHS=['January','February','March','April','May','June','July','August','September','October','November','December']
MN={m.lower():i+1 for i,m in enumerate(MONTHS)}
FULL=re.compile(r'\b('+'|'.join(MONTHS)+r')\s+(\d{1,2}),\s+(20\d{2})\b',re.I)
MD=re.compile(r'\b('+'|'.join(MONTHS)+r')\s+(\d{1,2})\b',re.I)
UA='ARGOS-W4B-official-macro-occurrences/1.0 date-only'
class TextLines(HTMLParser):
    def __init__(self): super().__init__(convert_charrefs=True); self.lines=[]
    def handle_data(self,d):
        x=' '.join(d.split())
        if x:self.lines.append(x)
def html_lines(body):
    p=TextLines(); p.feed(body.decode('utf-8','ignore')); return p.lines
def fetch(label,url,retries=5):
    last=''
    for i in range(retries):
        try:
            with urlopen(Request(url,headers={'User-Agent':UA,'Accept':'text/html,application/xhtml+xml'}),timeout=60) as r:
                b=r.read(); return {'label':label,'url':url,'http_status':getattr(r,'status',200),'content_type':r.headers.get('Content-Type','').split(';')[0],'response_bytes':len(b),'sha256':hashlib.sha256(b).hexdigest(),'retrieved_at_utc':datetime.now(timezone.utc).isoformat(),'error':''},b
        except HTTPError as e:
            last=f'HTTP_{e.code}'
            if 400<=e.code<500 and e.code!=429:
                b=e.read(); return {'label':label,'url':url,'http_status':e.code,'content_type':e.headers.get('Content-Type','').split(';')[0],'response_bytes':len(b),'sha256':hashlib.sha256(b).hexdigest(),'retrieved_at_utc':datetime.now(timezone.utc).isoformat(),'error':last},b
        except (URLError,TimeoutError,OSError) as e:last=f'{type(e).__name__}:{str(e)[:120]}'
        time.sleep(min(12,1.2*(2**i)))
    return {'label':label,'url':url,'http_status':'','content_type':'','response_bytes':0,'sha256':'','retrieved_at_utc':datetime.now(timezone.utc).isoformat(),'error':last or 'unknown'},b''
def full_date(s):
    m=FULL.search(s)
    return date(int(m.group(3)),MN[m.group(1).lower()],int(m.group(2))) if m else None
def month_day(s,year):
    m=MD.search(s)
    if not m:return None
    try:return date(year,MN[m.group(1).lower()],int(m.group(2)))
    except ValueError:return None
def nearby_date(lines,index,year=None,radius=8):
    hits=[]
    for j in range(max(0,index-radius),min(len(lines),index+radius+1)):
        d=full_date(lines[j]) or (month_day(lines[j],year) if year else None)
        if d:hits.append((abs(j-index),j,d))
    if not hits:return None
    hits.sort(key=lambda x:(x[0],x[1]))
    if len(hits)>1 and hits[0][0]==hits[1][0] and hits[0][2]!=hits[1][2]:return None
    return hits[0][2]
def occurrence(family,subject,d,authority,meta,ref):
    if not d:return None
    return {'resolved_family':family,'normalized_subject_key':subject,'official_event_reference_date':d.isoformat(),'source_authority':authority,'source_url':meta['url'],'retrieved_at_utc':meta['retrieved_at_utc'],'source_body_sha256':meta['sha256'],'structured_release_date_reference':ref}
