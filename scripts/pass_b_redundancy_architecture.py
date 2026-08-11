#!/usr/bin/env python3
from __future__ import annotations
import csv,gzip,json,math,statistics,hashlib,bisect
from collections import defaultdict
from pathlib import Path
from datetime import datetime,timezone

ROOT=Path('.')
AUD=ROOT/'registry/implementation_audit.csv'
TAPE=ROOT/'data/ic03_audit_ready_tape.csv.gz'
PRICE=ROOT/'data/ic04_yes_probability_trajectory.csv.gz'
OUT_FEATURE=ROOT/'registry/pass_b_label_free_feature_matrix.csv'
OUT_CORR=ROOT/'registry/pass_b_feature_correlations.csv'
OUT_ARCH=ROOT/'registry/pass_b_architecture.csv'
OUT_SUM=ROOT/'registry/pass_b_summary.json'
OUT_REPORT=ROOT/'docs/23_cross_strategy_implementation_audit_pass_b.md'


def sha(p):
 h=hashlib.sha256()
 with open(p,'rb') as f:
  for b in iter(lambda:f.read(1<<20),b''): h.update(b)
 return h.hexdigest()

def write_csv(path,rows,fields=None):
 path.parent.mkdir(parents=True,exist_ok=True)
 if fields is None: fields=list(rows[0]) if rows else []
 with open(path,'w',newline='',encoding='utf-8') as f:
  w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(rows)

def parse_dt(s):
 return int(datetime.fromisoformat(s.replace('Z','+00:00')).timestamp())

def sign(x,eps=1e-15): return 1 if x>eps else -1 if x<-eps else 0

def rankdata(xs):
 order=sorted(range(len(xs)),key=lambda i:xs[i]);r=[0.0]*len(xs);i=0
 while i<len(xs):
  j=i+1
  while j<len(xs) and xs[order[j]]==xs[order[i]]: j+=1
  rr=(i+j-1)/2+1
  for k in range(i,j): r[order[k]]=rr
  i=j
 return r

def pearson(x,y):
 n=len(x)
 if n<3:return None
 mx=sum(x)/n;my=sum(y)/n
 a=sum((v-mx)**2 for v in x);b=sum((v-my)**2 for v in y)
 if a<=0 or b<=0:return None
 return sum((x[i]-mx)*(y[i]-my) for i in range(n))/math.sqrt(a*b)

def spearman(x,y):
 return pearson(rankdata(x),rankdata(y))

def quantile(vals,q):
 if not vals:return None
 a=sorted(vals);pos=(len(a)-1)*q;lo=int(math.floor(pos));hi=int(math.ceil(pos))
 return a[lo] if lo==hi else a[lo]*(hi-pos)+a[hi]*(pos-lo)

def last_le(ts,ps,target):
 i=bisect.bisect_right(ts,target)-1
 return None if i<0 else ps[i]

def price_features(event_key,rows):
 ts=[int(r['timestamp']) for r in rows];ps=[float(r['price']) for r in rows];cut=parse_dt(rows[0]['safe_cutoff_utc'])
 p0=last_le(ts,ps,cut)
 if p0 is None:return {}
 def p(h):return last_le(ts,ps,cut-int(h*3600))
 p1,p6,p24,p48=p(1),p(6),p(24),p(48)
 d1=None if p1 is None else p0-p1;d6=None if p6 is None else p0-p6;d24=None if p24 is None else p0-p24
 sc=None
 if None not in (d1,d6,d24):sc=(sign(d1)+sign(d6)+sign(d24))/3
 vel6=None if d6 is None else d6/6
 acc=None if d1 is None or d6 is None else d1-(d6/6)
 # fixed hourly grid over last 24h; no interpolation, last observation at/before grid point
 grid=[]
 for h in range(24,-1,-1):
  v=last_le(ts,ps,cut-h*3600)
  if v is not None:grid.append(v)
 diffs=[b-a for a,b in zip(grid,grid[1:])]
 rv=statistics.pstdev(diffs) if len(diffs)>=6 else None
 volscaled=None if d6 is None or rv in (None,0) else d6/(rv*math.sqrt(6))
 jump=max((abs(x) for x in diffs),default=None)
 rough=sum(abs(x) for x in diffs) if diffs else None
 # simple fixed CUSUM proxy on hourly changes, centered by their own pre-cutoff mean; label-free diagnostic only
 cus=None
 if len(diffs)>=6:
  m=sum(diffs)/len(diffs);s=0;mx=0
  for x in diffs:
   s+=x-m;mx=max(mx,abs(s))
  cus=mx
 return {'event_key':event_key,'price_last':p0,'delta_1h':d1,'delta_6h':d6,'delta_24h':d24,'sign_consistency_1_6_24h':sc,'velocity_6h_per_hour':vel6,'acceleration_proxy_1h_vs_6h':acc,'hourly_realized_scale_24h':rv,'vol_scaled_delta_6h':volscaled,'max_hourly_jump_24h':jump,'path_roughness_24h':rough,'cusum_proxy_24h':cus}

def tape_features(event_key,rows):
 n=len(rows);notional=[float(r['collateral_notional_canonical']) for r in rows]
 sides=[1 if r['side_canonical'].upper()=='BUY' else -1 for r in rows];total=sum(notional)
 signed_n=None if total<=0 else sum(s*v for s,v in zip(sides,notional))/total
 signed_count=sum(sides)/n if n else None
 # top decile-by-count trades, deterministic within-event descriptive share
 q90=quantile(notional,.9);large=None if total<=0 else sum(v for v in notional if v>=q90)/total
 wallet=defaultdict(float)
 for r,v in zip(rows,notional):wallet[r['proxy_wallet'].lower()]+=v
 shares=[v/total for v in wallet.values()] if total>0 else []
 hhi=sum(x*x for x in shares) if shares else None;top=max(shares) if shares else None
 same=None
 if n>=2:same=sum(1 for a,b in zip(sides,sides[1:]) if a==b)/(n-1)
 maxrun=0;cur=0;last=None
 for s in sides:
  if s==last:cur+=1
  else:cur=1;last=s
  maxrun=max(maxrun,cur)
 return {'event_key':event_key,'trade_count':n,'log_trade_count':math.log1p(n),'total_collateral_notional':total,'log_total_notional':math.log1p(total),'wallet_count':len(wallet),'log_wallet_count':math.log1p(len(wallet)),'signed_notional_imbalance':signed_n,'signed_count_imbalance':signed_count,'large_trade_share_top_decile':large,'wallet_hhi_notional':hhi,'top_wallet_notional_share':top,'same_side_transition_share':same,'max_run_share':(maxrun/n if n else None)}

def load_feature_matrix():
 tape_by=defaultdict(list)
 with gzip.open(TAPE,'rt',encoding='utf-8') as f:
  for r in csv.DictReader(f):tape_by[r['event_key']].append(r)
 price_by=defaultdict(list)
 with gzip.open(PRICE,'rt',encoding='utf-8') as f:
  for r in csv.DictReader(f):price_by[r['event_key']].append(r)
 keys=sorted(set(tape_by)|set(price_by));out=[]
 for k in keys:
  row={'event_key':k}
  if k in tape_by:row.update(tape_features(k,tape_by[k]))
  if k in price_by:row.update(price_features(k,price_by[k]))
  out.append(row)
 fields=['event_key']+sorted({x for r in out for x in r if x!='event_key'})
 write_csv(OUT_FEATURE,out,fields)
 return out,fields

def correlation_table(rows,fields):
 num=[f for f in fields if f!='event_key']
 out=[]
 for i,a in enumerate(num):
  for b in num[i+1:]:
   pairs=[]
   for r in rows:
    x=r.get(a);y=r.get(b)
    if x not in (None,'') and y not in (None,''):
     pairs.append((float(x),float(y)))
   if len(pairs)<30:continue
   x=[p[0] for p in pairs];y=[p[1] for p in pairs];rho=spearman(x,y);pr=pearson(x,y)
   out.append({'feature_a':a,'feature_b':b,'n_overlap':len(pairs),'spearman_rho':'' if rho is None else f'{rho:.8f}','pearson_r':'' if pr is None else f'{pr:.8f}','abs_spearman':'' if rho is None else f'{abs(rho):.8f}','near_duplicate_flag':str(rho is not None and abs(rho)>=.90).lower(),'high_overlap_flag':str(rho is not None and abs(rho)>=.75).lower()})
 out.sort(key=lambda r:float(r['abs_spearman'] or 0),reverse=True)
 write_csv(OUT_CORR,out)
 return out

# Pass-B decisions: simple-first, one representative per mechanism where possible.
# Existing hard no-go and pre-Pass-B DEFERRED rows are preserved unchanged.
B={
'Signed notional imbalance':('GO_CORE_CANDIDATE','H2_FLOW','CORE_FEATURE','Distinct signed-dollar-flow mechanism; canonical on-chain notional/direction.','ART-028 materialize fixed windows; ART-029 core flow family.'),
'Large-trade share':('GO_CHALLENGER','H2_FLOW_SIZE','CHALLENGER_FEATURE','Size-conditioning is distinct from net direction but adds a threshold degree of freedom.','Keep one prior-only size definition; ablate after core flow.'),
'HHI and top-k notional share':('GO_CORE_CANDIDATE','H2_CONCENTRATION','CORE_FEATURE','Participant concentration is distinct from direction; HHI/top-k variants are internal duplicates within one family.','Use one primary concentration statistic; top-k only sensitivity.'),
'Run length and signed-flow persistence':('GO_CORE_CANDIDATE','H2_FLOW_PERSISTENCE','CORE_FEATURE','Temporal ordering adds information not contained in aggregate net flow.','Freeze minimum trade count and one persistence statistic.'),
'Inventory-style decision band':('GO_CORE_CANDIDATE','H5_ABSTENTION','CORE_DECISION','Directly implements LONG/SHORT/NO_TRADE with simple deterministic abstention.','Only after H4; retain C0 no-trade null.'),
'Implementation shortfall':('CONDITIONAL','H5_EXECUTION','CONDITIONAL_ROBUSTNESS','NBBO is retrievable but realized shortfall is not yet materialized/identified.','Open a separate execution-data gate only if H5 is reached.'),
'Multi-horizon sign consistency':('GO_ROBUSTNESS','H2_TRAJECTORY','ROBUSTNESS_FEATURE','Sign-only trajectory summary is simpler but overlaps magnitude-based trajectory measures; useful as ablation/robustness.','Do not count as separate core family; compare against velocity family.'),
'Velocity and acceleration':('GO_CORE_CANDIDATE','H2_TRAJECTORY','CORE_FEATURE','Timestamp-aware trajectory slope/curvature is directly materializable and interpretable.','Freeze a small fixed window set; acceleration secondary to velocity.'),
'Volatility-scaled movement':('GO_CORE_CANDIDATE','H2_STATE_NORMALIZATION','CORE_TRANSFORMATION','Scale normalization changes interpretation across activity regimes rather than duplicating raw movement.','Use causal pre-cutoff scale only; no global normalization.'),
'Volatility/panic state interaction':('NO_GO_REDUNDANT','H3_RISK_STATE','REDUNDANT_WITH_REALIZED_VOL_REGIME','Same intended regime mechanism can be represented more cleanly by one realized-volatility state.','Fold into Realized volatility regime; do not test separately.'),
'Conditional z-score':('GO_CORE_CANDIDATE','H2_RESIDUAL_STATE','CORE_TRANSFORMATION','Canonical simple observed-minus-expected residualization; simple-first representative of state normalization.','Make residual state model baseline before complex anomaly challengers.'),
'Half-life/post-jump decay':('CONDITIONAL','H2_PRICE_DYNAMICS','CONDITIONAL_CHALLENGER','Distinct persistence-vs-reversion mechanism but eligibility depends on a predeclared jump with enough pre-cutoff tail.','ART-028 measure label-free eligible-event coverage after one fixed jump rule.'),
'Expected-versus-realized residual':('CONDITIONAL','H3_SURPRISE','CONDITIONAL_FEATURE','Admissible only if both expectation and realized quantity are pre-cutoff; post-event EPS/disclosure would leak.','Write exact pre-cutoff definition before any materialization.'),
'Delayed incorporation metric':('GO_CORE_CANDIDATE','H4_TRANSMISSION','CORE_TEST','Direct low-dimensional H4 transmission question.','Only after H2 pass; freeze event-response horizons before returns.'),
'Friday/weekday indicator':('GO_CORE_CANDIDATE','H3_ATTENTION','CORE_CONTEXT','Complete deterministic PIT calendar context with almost zero degrees of freedom.','If H2 passes, one predeclared weekday coding only.'),
'Concurrent announcement intensity':('GO_CHALLENGER','H3_ATTENTION','CHALLENGER_CONTEXT','Distinct crowding/attention proxy but current measure is internal-universe only.','Keep naming narrow; do not claim market-wide attention.'),
'Residual return versus factors':('CONDITIONAL','H4_COUNTERFACTUAL','CONDITIONAL_ROBUSTNESS','Useful secondary benchmark but factor version/hash must first be frozen.','Materialize factors only if H4 is reached.'),
'Rank/z-score transforms':('GO_ROBUSTNESS','NORMALIZATION','TRANSFORMATION_RULE','Transformation rule, not independent alpha mechanism; train-only scaling protects comparability.','Apply as protocol rule where needed; do not count as separate signal family.'),
'Size/volatility/liquidity neutralization':('CONDITIONAL','H4_COUNTERFACTUAL','CONDITIONAL_ROBUSTNESS','Partially overlaps existing vol/turnover controls; PIT size field not materialized.','Use only audited existing controls unless minimal SEC schema is separately frozen.'),
'Realized volatility regime':('GO_CORE_CANDIDATE','H3_RISK_STATE','CORE_CONTEXT','Simplest auditable ex-ante risk-state interaction from existing equity data.','If H2 passes, freeze one window/state definition.'),
'Jump intensity/change score':('GO_CORE_CANDIDATE','H2_REGIME_CHANGE','CORE_FEATURE','Simple deterministic regime-change representative; lower degrees of freedom than BOCPD.','Make simple jump/change score the core representative.'),
'Skew/tail conditional loss':('GO_ROBUSTNESS','H5_TAIL_RISK','CORE_ROBUSTNESS','Direct tail-risk diagnostic and more primitive than redundant normal-vs-tail summary.','Pre-register tail metrics if H5 reached.'),
'Forecast/variance disagreement':('NO_GO_REDUNDANT','H2_FORECAST_DISAGREEMENT','REDUNDANT','Abstractly duplicates the concrete Dispersion across simple forecasters representation.','Use Dispersion across simple forecasters as the single disagreement implementation.'),
'Normal-state payoff versus tail state':('NO_GO_REDUNDANT','H5_TAIL_RISK','REDUNDANT','Same tail-decomposition question can be covered by predeclared tail conditional loss/stress diagnostics.','Fold into H5 tail-risk robustness family.'),
'Liquidity stress interaction':('GO_ROBUSTNESS','H5_STRESS','ROBUSTNESS','Distinct pre-event stress conditioning if named via existing turnover/volatility proxies.','Do not relabel turnover as spread/depth.'),
'Short-horizon reversal diagnostic':('GO_ROBUSTNESS','H4_TRANSMISSION','ROBUSTNESS_TEST','Useful continuation-vs-reversal falsification but overlaps the core delayed-incorporation family.','Keep as one predeclared secondary horizon/sign diagnostic.'),
'Turnover-conditioned response':('GO_CHALLENGER','H3_LIQUIDITY_STATE','CHALLENGER_CONTEXT','Distinct turnover state from volatility, using audited daily volume.','One window/interact form only if H2 passes.'),
'State-dependent coefficients':('DEFERRED','H3_REGIME','DEFERRED_COMPLEXITY','Generic regime splitting adds degrees of freedom and is subsumed initially by explicit realized-volatility/turnover contexts.','Reopen only if explicit simple interactions are inadequate after confirmatory work.'),
'Macro-news coincidence':('CONDITIONAL','H3_ATTENTION','CONDITIONAL_CONTEXT','Potentially distinct information-load flag but official event set/window not materialized.','Freeze minimal BLS/BEA/Fed release set before construction if retained.'),
'Residualized managerial tone':('DEFERRED','H3_TEXT','DEFERRED_TEXT','Requires a new frozen PIT corpus and overlaps other text-context candidates under a tight sample/deadline.','Do not open a multi-text search before H2; reconsider only one text family later.'),
'Vagueness/uncertainty score':('CONDITIONAL','H3_TEXT','SINGLE_TEXT_OPTION','Simplest interpretable text-context candidate if a prior-document-only corpus is frozen.','If H3 is reached and text is justified, this is the sole preferred text feature.'),
'Text entropy/topic surprise':('DEFERRED','H3_TEXT','DEFERRED_TEXT','Higher model/version/topic degrees of freedom than a simple uncertainty score with same corpus burden.','Do not include in initial H3 architecture.'),
'Chronologically bounded language model':('GO_CORE_CANDIDATE','GOV_PIT_TEXT','MANDATORY_GOVERNANCE_IF_TEXT','Not an alpha feature; mandatory firewall if any text path is reopened.','Record model/version/knowledge cutoff and document timestamps.'),
'Platt/isotonic/online calibration':('GO_ROBUSTNESS','H2_CALIBRATION','ROBUSTNESS_MODEL','Calibration does not add information; keep one parsimonious prequential calibration as robustness.','Prefer one predeclared simple calibrator, fit date-batched on prior data.'),
'Online weighted ensemble':('GO_CHALLENGER','H2_MODEL_POOLING','CHALLENGER_MODEL','Small fixed expert pooling is PIT-compatible and simpler than maintaining separate regret-family tests.','Freeze expert set and one update rule; no expert proliferation.'),
'Dispersion across simple forecasters':('GO_CHALLENGER','H2_FORECAST_DISAGREEMENT','CHALLENGER_FEATURE','Concrete low-dimensional second-order uncertainty representation; preferred over abstract duplicate.','Use a very small frozen forecaster set.'),
'BOCPD':('DEFERRED','H2_REGIME_CHANGE','DEFERRED_COMPLEX_CHALLENGER','Shares regime-change mechanism with simple jump/CUSUM but adds prior/hazard choices with only ~115 independent events.','Simple jump core + CUSUM challenger first; BOCPD documented for future.'),
'CUSUM/score-CUSUM':('GO_CHALLENGER','H2_REGIME_CHANGE','CHALLENGER_FEATURE','Sequential evidence accumulator is distinct implementation but simpler than BOCPD.','Freeze one score definition and reference level before ART-029.'),
'Matrix Profile discord score':('GO_CHALLENGER','H2_PATTERN_NOVELTY','CHALLENGER_FEATURE','Provides model-free path novelty distinct from pointwise residual/jump families.','Use one fixed subsequence scale if retained; no window search.'),
'Matrix Profile motif similarity':('NO_GO_REDUNDANT','H2_PATTERN_NOVELTY','REDUNDANT','Uses the same pattern-distance machinery/data as discord; anomaly thesis is more directly represented by discord.','Keep discord only for initial architecture.'),
'Wavelet decomposition':('DEFERRED','H2_MULTI_SCALE','DEFERRED_COMPLEXITY','Adds basis/scale choices while fixed-window trajectory features already cover multi-horizon movement.','Reopen only if fixed-window representation proves structurally inadequate.'),
'Mutual information lead-lag':('DEFERRED','H4_NONLINEAR_TRANSMISSION','DEFERRED_COMPLEXITY','Nonlinear lead-lag adds estimator/binning choices and small-sample burden beyond event-time lag regression.','Use event-time lag + reverse-direction control first.'),
'Event-time lag regression':('GO_CHALLENGER','H4_TRANSMISSION','CHALLENGER_TEST','Concrete interpretable lead-lag parameterization complementary to core delayed-incorporation summary.','If H2 passes, freeze a small lag set before returns.'),
'Synthetic control':('CONDITIONAL','H4_COUNTERFACTUAL','CONDITIONAL_ROBUSTNESS','Potentially stronger counterfactual but donor construction/data requirements are not frozen.','Only if H4 primary result warrants deeper robustness; donor rules frozen first.'),
'Reverse-direction equity-to-PM test':('GO_ROBUSTNESS','H4_NEGATIVE_CONTROL','MANDATORY_NEGATIVE_CONTROL','Directly addresses reverse causality and uses the same timestamp discipline.','Include as predeclared H4 negative control if H2 passes.'),
'Matched event study':('GO_ROBUSTNESS','H4_COUNTERFACTUAL','ROBUSTNESS_TEST','Interpretable counterfactual robustness with lower complexity than synthetic control.','Freeze matching covariates/rules before H4 outcomes.'),
'Regret-based expert weighting':('NO_GO_REDUNDANT','H2_MODEL_POOLING','REDUNDANT','Same adaptive expert-pooling role as Online weighted ensemble; testing both inflates model-family multiplicity.','Retain one online weighted ensemble implementation only.'),
'Conformal/change-drift monitor':('GO_ROBUSTNESS','H2_DRIFT','ROBUSTNESS_MONITOR','Useful process/stability monitor rather than primary incremental-information feature.','Use only as predeclared drift/coverage robustness, not extra alpha search.'),
'Worst-case expected return':('GO_CHALLENGER','H5_UNCERTAINTY_DECISION','CHALLENGER_DECISION','Distinct robust decision rule that naturally supports no-trade under uncertainty.','Only after H4; compare to simple deterministic abstention without tuning on test.'),
'Turnover penalty':('GO_ROBUSTNESS','H5_COST_CONTROL','ROBUSTNESS_DECISION','Simple regularizer of economic activity/fragility with low extra complexity.','Predeclare penalty convention if H5 reached.'),
'Fractional Kelly':('DEFERRED','H5_SIZING','DEFERRED_SIZING','Sizing adds estimation risk and conflicts with the simple equal-notional/no-leverage confirmatory architecture; not needed to test existence of edge.','Keep equal-notional primary; revisit sizing only after validated economic edge.'),
'Risk-coverage curve':('GO_CORE_CANDIDATE','H5_ABSTENTION','CORE_EVALUATION','Direct evaluation of abstention/no-trade tradeoff without requiring a second learned model.','Use with frozen confidence score after H4; report coverage versus risk/utility.'),
'Conformal martingale':('GO_CHALLENGER','H2_SEQUENTIAL_EVIDENCE','CHALLENGER_FEATURE','Anytime evidence accumulation is conceptually distinct from fixed-window residuals, but should remain one sequential challenger.','Freeze conformity score and betting rule ex ante if retained.'),
'Multivariate anomaly distance':('GO_CHALLENGER','H2_MULTIVARIATE_ANOMALY','CHALLENGER_FEATURE','Combines multiple audited state dimensions without labels; useful as one multivariate anomaly challenger.','Use a simple shrinkage/diagonal distance before nonlinear alternatives.'),
'Deflated Sharpe Ratio':('GO_ROBUSTNESS','GOV_MULTIPLE_TESTING','MANDATORY_IF_ECONOMIC_SEARCH_EXPANDS','Corrects economic-performance selection when multiple H5 variants are tried; not a signal.','Apply if enough economic variants are evaluated; count all trials from ledger.'),
'PBO/CSCV':('CONDITIONAL','GOV_BACKTEST_OVERFIT','CONDITIONAL_GOVERNANCE','Useful only if the number/structure of comparable strategy trials makes CSCV estimable.','Decide from frozen trial count before final economic freeze.'),
'Trial ledger':('GO_CORE_CANDIDATE','GOV_TRIAL_ACCOUNTING','MANDATORY_GOVERNANCE','Required to make later multiple-testing controls truthful.','Assign immutable trial IDs before ART-029/030 execution.'),
'Random-null/placebo tests':('GO_CORE_CANDIDATE','GOV_PLACEBO','MANDATORY_GOVERNANCE','Provides falsification without selecting candidates by outcome and is compatible with frozen protocol.','Pre-register placebo family and seeds before confirmatory testing.'),
'Frozen feature/model family':('GO_CORE_CANDIDATE','GOV_PREREGISTRATION','MANDATORY_GOVERNANCE','Central protection against outcome-driven specification after this architecture pass.','Freeze final ART-029 feature/model universe and hashes before ART-030.')
}

def main():
 rows=list(csv.DictReader(open(AUD,encoding='utf-8')))
 assert len(rows)==69
 assert json.load(open(ROOT/'registry/pass_a_summary.json'))['decision']=='PASS_A_COMPLETE_FULL_SUPERSET_OUTCOME_BLIND'
 # explicit read whitelist: no outcomes, labels-for-comparison, equity post-event returns or performance files
 fm,fields=load_feature_matrix();corr=correlation_table(fm,fields)
 updated=[];arch=[]
 pending=0
 for r in rows:
  tech=r['technique'];old=r['final_status']
  if old=='PENDING_PASS_B':
   assert tech in B, f'missing Pass B decision: {tech}'
   status,family,role,basis,nxt=B[tech];r['final_status']=status;r['pass_b_status']='AUDITED_PASS_B';r['architecture_family']=family;r['architecture_role']=role;r['redundancy_basis']=basis;r['next_step']=nxt
  else:
   r['pass_b_status']='PRESERVED_PASS_A_STRUCTURAL_DISPOSITION';r['architecture_family']=r.get('redundancy_group','');r['architecture_role']=r.get('role_recommendation','');r['redundancy_basis']='Preserved hard structural no-go or pre-Pass-B deferred disposition from outcome-blind Pass A.'
  if r['final_status']=='PENDING_PASS_B':pending+=1
  updated.append(r)
  arch.append({'technique':tech,'target_gate':r['target_gate'],'pass_a_status':r['pass_a_status'],'pass_b_status':r['pass_b_status'],'final_status':r['final_status'],'architecture_family':r['architecture_family'],'architecture_role':r['architecture_role'],'redundancy_basis':r['redundancy_basis'],'next_step':r['next_step']})
 assert pending==0
 fields2=list(rows[0].keys())
 for c in ['pass_b_status','architecture_family','architecture_role','redundancy_basis']:
  if c not in fields2:fields2.append(c)
 write_csv(AUD,updated,fields2);write_csv(OUT_ARCH,arch)
 counts=defaultdict(int);gate_counts=defaultdict(lambda:defaultdict(int))
 for r in updated:counts[r['final_status']]+=1;gate_counts[r['target_gate']][r['final_status']]+=1
 core_h2=[r['technique'] for r in updated if r['target_gate']=='H2' and r['final_status']=='GO_CORE_CANDIDATE']
 chall_h2=[r['technique'] for r in updated if r['target_gate']=='H2' and r['final_status']=='GO_CHALLENGER']
 robust_h2=[r['technique'] for r in updated if r['target_gate']=='H2' and r['final_status']=='GO_ROBUSTNESS']
 no_go_red=[r['technique'] for r in updated if r['final_status']=='NO_GO_REDUNDANT']
 highcorr=[r for r in corr if r['near_duplicate_flag']=='true']
 summary={
  'decision':'PASS_B_COMPLETE_REDUNDANCY_ARCHITECTURE_OUTCOME_BLIND',
  'audited_rows':69,'pass_b_input_rows':59,'pending_after_pass_b':0,
  'outcomes_or_performance_read_by_script':False,
  'label_free_feature_events':len(fm),'label_free_feature_columns':len(fields)-1,
  'feature_matrix_sha256':sha(OUT_FEATURE),'feature_correlations_sha256':sha(OUT_CORR),
  'near_duplicate_feature_pairs_abs_spearman_ge_0_90':len(highcorr),
  'status_counts':dict(sorted(counts.items())),
  'target_status_counts':{g:dict(sorted(v.items())) for g,v in sorted(gate_counts.items())},
  'h2_core_candidates':core_h2,'h2_challengers':chall_h2,'h2_robustness':robust_h2,
  'no_go_redundant':no_go_red,
  'architecture_principles':['simple-first within each mechanism','one primary representative per redundancy family where possible','challengers must test a distinct representation, not parameter variants','conditional/unmaterialized inputs do not become features by assumption','H3/H4/H5 remain dependency-gated','all later performance trials must enter the trial ledger'],
  'art028_h2_core_families':['H2_RESIDUAL_STATE','H2_TRAJECTORY','H2_STATE_NORMALIZATION','H2_FLOW','H2_CONCENTRATION','H2_FLOW_PERSISTENCE','H2_REGIME_CHANGE'],
  'art028_h2_challenger_families':['H2_FLOW_SIZE','H2_FORECAST_DISAGREEMENT','H2_PATTERN_NOVELTY','H2_SEQUENTIAL_EVIDENCE','H2_MULTIVARIATE_ANOMALY','H2_MODEL_POOLING'],
  'art029_model_cap':'one interpretable regularized M_MOVE champion plus at most one nonlinear challenger, consistent with ART-027',
  'boundary':'Pass B selects architecture and removes redundant representations without outcomes. It does not establish incremental predictive value or authorize H2 claims.'
 }
 OUT_SUM.write_text(json.dumps(summary,indent=2,sort_keys=True),encoding='utf-8')
 report=f'''# ARGOS — Cross-Strategy Implementation Audit — Pass B\n\n**Decision:** `PASS_B_COMPLETE_REDUNDANCY_ARCHITECTURE_OUTCOME_BLIND`  \n**Input:** 59 Pass-A survivors; all 69 registry rows receive final architecture dispositions.\n\n## Empirical redundancy check without labels\nPass B materialized a descriptive event-level feature matrix only from the frozen IC-03 canonical tape and IC-04 pre-cutoff YES trajectory. It reads no EPS outcomes, Polymarket resolution labels for comparison, post-event equity returns or candidate performance. Fixed descriptive proxies are used only to reveal overlap, not to tune candidate parameters.\n\n- events with at least one materialized H2 input: {len(fm)}\n- descriptive feature columns: {len(fields)-1}\n- pairwise feature correlations computed: {len(corr)}\n- near-duplicate pairs |Spearman| >= 0.90: {len(highcorr)}\n\n## Architecture rule\nSimple-first within mechanisms. One primary representative per redundancy family where possible; challengers must add a genuinely different representation rather than another threshold/window. H3/H4/H5 remain dependency-gated.\n\n## H2 core families handed to ART-028\n- residual state: Conditional z-score\n- trajectory: Velocity and acceleration\n- state normalization: Volatility-scaled movement\n- signed flow: Signed notional imbalance\n- participant concentration: HHI/top-k family (one primary statistic)\n- flow persistence: Run length/signed persistence\n- regime change: simple Jump intensity/change score\n\n## H2 challengers retained structurally\n{chr(10).join('- '+x for x in chall_h2)}\n\n## Redundancy eliminations added in Pass B\n{chr(10).join('- '+x for x in no_go_red) if no_go_red else '- none'}\n\n## Model-family cap\nART-029 must still freeze one interpretable regularized `M_MOVE` champion and at most one nonlinear challenger. Pass B does not authorize trying every retained challenger. ART-028 first closes label-free coverage/materialization for retained families; ART-029 then freezes the actual test universe and trial IDs before ART-030.\n'''
 OUT_REPORT.write_text(report,encoding='utf-8')
 print(json.dumps(summary,indent=2),flush=True)

if __name__=='__main__':main()
