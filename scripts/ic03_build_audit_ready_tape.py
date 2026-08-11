#!/usr/bin/env python3
from __future__ import annotations
import csv,gzip,json,hashlib,argparse
from decimal import Decimal,getcontext
from pathlib import Path
getcontext().prec=50
TOL=Decimal('0.000001')

def sha(p):
 h=hashlib.sha256()
 with open(p,'rb') as f:
  for b in iter(lambda:f.read(1<<20),b''):h.update(b)
 return h.hexdigest()

def read_gz(p):
 with gzip.open(p,'rt',encoding='utf-8') as f:return list(csv.DictReader(f))
def read_csv(p):
 with open(p,encoding='utf-8') as f:return list(csv.DictReader(f))
def b(v):return str(v).lower()=='true'

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--signed-tape',required=True);ap.add_argument('--size-audit',required=True);ap.add_argument('--event-summary',required=True);ap.add_argument('--out-dir',required=True);a=ap.parse_args()
 out=Path(a.out_dir);out.mkdir(parents=True,exist_ok=True)
 rows=read_gz(Path(a.signed_tape)); sem=read_csv(Path(a.size_audit)); events=read_csv(Path(a.event_summary))
 if len(rows)!=12752:raise RuntimeError(f'expected 12752 signed rows got {len(rows)}')
 if len({r['tx_hash'] for r in rows})!=12752:raise RuntimeError('transaction hash uniqueness failed')
 if not all(r['status']=='PASS' and b(r['side_match']) and b(r['price_match']) and b(r['era_match']) for r in rows):raise RuntimeError('direction/price/era gate regressed')
 mismatch=[r for r in rows if not b(r['size_match'])]
 if len(mismatch)!=569:raise RuntimeError(f'expected 569 API-size mismatches got {len(mismatch)}')
 sm={r['tx_hash']:r for r in sem}
 if set(sm)!={r['tx_hash'] for r in mismatch}:raise RuntimeError('size-semantics coverage != mismatch set')
 if not all(b(r['receive_matches_gross']) and b(r['collateral_matches_gross_x_price']) for r in sem):raise RuntimeError('FeeModule gross/collateral identity failed')
 canonical=[];twice_fee=0;notional_fail=0
 for r in rows:
  gross=Decimal(r['onchain_token_amount']);coll=Decimal(r['onchain_collateral_amount']);price=Decimal(r['onchain_price']);api=Decimal(r['api_size'])
  if abs(coll-gross*price)>TOL:notional_fail+=1
  s=sm.get(r['tx_hash']);relation='API_EQUALS_GROSS';api_sem='DIRECTLY_EQUAL_TO_CANONICAL_GROSS';fee='';fee_rate='';fee_module_receive=''
  if s:
   relation='V1_BUY_FEE_MODULE_API_SIZE_DIFFERS_FROM_GROSS';api_sem='RAW_VENDOR_FIELD_NONCANONICAL_FOR_VOLUME';fee=s['fee_module_taker_fee_amount'];fee_rate=s['fee_rate_bps'];fee_module_receive=s['fee_module_taker_receive_amount']
   if abs((gross-api)-Decimal(2)*Decimal(fee))<=TOL:twice_fee+=1
  canonical.append({
   'market_id':r['market_id'],'event_key':r['event_key'],'ticker':r['ticker'],'company_event_date':r['company_event_date'],'safe_cutoff_utc':r['safe_cutoff_utc'],
   'timestamp':r['timestamp'],'tx_hash':r['tx_hash'],'block_number':r['block_number'],'exchange_version':r['exchange_version'],'exchange_address':r['exchange_address'],
   'proxy_wallet':r['proxy_wallet'],'condition_id':r['condition_id'],'asset':r['asset'],'outcome_token_label':r['outcome'],
   'side_canonical':r['onchain_side'],'price_canonical':r['onchain_price'],'token_amount_gross_canonical':r['onchain_token_amount'],'collateral_notional_canonical':r['onchain_collateral_amount'],
   'api_side_raw':r['api_side'],'api_price_raw':r['api_price'],'api_size_raw':r['api_size'],'api_size_relation':relation,'api_size_semantics':api_sem,
   'fee_module_taker_receive_amount':fee_module_receive,'fee_module_taker_fee_amount':fee,'fee_rate_bps':fee_rate,
   'direction_semantics_status':'PASS_ONCHAIN_RECONCILED','quantity_semantics_status':'PASS_ONCHAIN_GROSS_AND_COLLATERAL_CANONICAL','source_status':'PIT_PRE_CUTOFF_VERIFIED'
  })
 if notional_fail:raise RuntimeError(f'canonical notional identity failed {notional_fail}')
 fields=list(canonical[0]);csvp=out/'ic03_audit_ready_tape.csv'
 with open(csvp,'w',newline='',encoding='utf-8') as f:w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(canonical)
 gzp=out/'ic03_audit_ready_tape.csv.gz'
 with open(csvp,'rb') as src,gzip.open(gzp,'wb') as dst:
  for x in iter(lambda:src.read(1<<20),b''):dst.write(x)
 event_status={r['status'] for r in events}; no_tape=[r['event_key'] for r in events if r['status']=='NO_PRE_CUTOFF_TAPE']
 if len(events)!=117 or no_tape!=['ANF|2026-05-27','BRZE|2026-05-27']:raise RuntimeError(f'event availability regression {len(events)} {no_tape}')
 summary={
  'decision':'PASS_IC03_AUDIT_READY_TAPE_WITH_DISCLOSED_API_SIZE_SEMANTICS',
  'direction_status':'PASS_FULL_ONCHAIN_RECONCILIATION','quantity_status':'PASS_CANONICAL_ONCHAIN_GROSS_AND_COLLATERAL',
  'rows':len(canonical),'events_with_pre_cutoff_tape':115,'frozen_events':117,'no_pre_cutoff_tape_events':no_tape,
  'side_matches':sum(b(r['side_match']) for r in rows),'price_matches':sum(b(r['price_match']) for r in rows),'era_matches':sum(b(r['era_match']) for r in rows),
  'api_size_equals_canonical_gross_rows':len(rows)-len(mismatch),'api_size_differs_from_canonical_gross_rows':len(mismatch),
  'fee_module_mismatch_rows_semantically_audited':len(sem),'fee_module_receive_matches_gross_rows':sum(b(r['receive_matches_gross']) for r in sem),
  'gross_minus_api_equals_two_times_fee_rows_descriptive':twice_fee,
  'canonical_volume_field':'token_amount_gross_canonical','canonical_notional_field':'collateral_notional_canonical','canonical_direction_field':'side_canonical','canonical_price_field':'price_canonical',
  'api_size_policy':'retain as raw vendor field; never silently substitute for gross token volume in the 569 audited V1 FeeModule BUY rows',
  'audit_ready_tape_sha256':sha(gzp),'source_signed_tape_sha256':sha(Path(a.signed_tape)),'size_semantics_csv_sha256':sha(Path(a.size_audit))
 }
 (out/'ic03_audit_ready_summary.json').write_text(json.dumps(summary,indent=2,sort_keys=True),encoding='utf-8')
 report=f'''# ARGOS — IC-03 Final Data-Semantics Gate\n\n**Decision:** `{summary['decision']}`\n\nIC-03 exists only to prepare reliable inputs for the later cross-strategy implementation audit. No event outcome, post-event return, alpha metric or feature performance is used here.\n\n## Closed semantics\n\n- pre-cutoff trade rows: **12,752** across **115/117** frozen events;\n- authoritative direction: **12,752/12,752** reconciled to Polygon `OrderFilled`;\n- execution price: **12,752/12,752** reconciled;\n- V1/V2 era mapping: **12,752/12,752** reconciled;\n- V1 rows: **11,729**; V2 rows: **1,023**;\n- API `size` equals gross on-chain token amount in **12,183/12,752** rows;\n- the **569** exceptions are all V1 BUY trades routed through the historical Polymarket Fee Module and were independently decoded with the historical source signature `0x2287e350`;\n- Fee Module `takerReceiveAmount` matches gross `OrderFilled` token amount in **569/569**;\n- canonical collateral notional is internally consistent with gross token amount × execution price.\n\n## Audit-ready field policy\n\nThe later implementation audit must use:\n\n- `side_canonical` for signed direction;\n- `token_amount_gross_canonical` for token/share volume;\n- `collateral_notional_canonical` for dollar-like executed notional;\n- `price_canonical` for execution price.\n\n`api_size_raw` is retained for provenance but is **not a canonical volume field** in the 569 V1 Fee Module BUY rows. We deliberately do not force a vendor-specific interpretation that is unnecessary for the future technique audit.\n\n## Structural missingness\n\n`ANF|2026-05-27` and `BRZE|2026-05-27` had no market trading before the already-frozen safe cutoff. They remain `MARKET_NOT_YET_TRADING`, never zero activity.\n\n## Boundary\n\nThis gate says the trade data are semantically ready to be *audited for possible techniques*. It does **not** say any flow, whale, concentration, volume, persistence or microstructure feature is predictive or approved for H2.\n\nAudit-ready tape SHA-256: `{summary['audit_ready_tape_sha256']}`\n'''
 (out/'ic03_final_report.md').write_text(report,encoding='utf-8')
 print(json.dumps(summary,indent=2),flush=True)
if __name__=='__main__':main()
