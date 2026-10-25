"""Offline-first daily cumulative research backtest, then actual-round reconciliation. No trading."""
import argparse,csv,datetime,hashlib,io,json,sys,tempfile,subprocess
from pathlib import Path
HERE=Path(__file__).resolve().parent
BASE=HERE.parent/'t1-b1-v1';sys.path.insert(0,str(BASE))
from runtime_guard import verify_runtime
from rules import daily_states,simulate,validate_bars,H,VERSION
from run_research import native_signals
from signal_report import describe_signal
UTC=datetime.timezone.utc
START=int(datetime.datetime(2026,7,13,tzinfo=UTC).timestamp()*1000)

def sha(b):return hashlib.sha256(b).hexdigest()
def write(p,x):p.write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n')
def day_window(date):
 d=datetime.datetime.fromisoformat(date).replace(tzinfo=datetime.timezone(datetime.timedelta(hours=8)))
 return int(d.timestamp()*1000),int((d+datetime.timedelta(days=1)).timestamp()*1000)
def merge_rows(old,new):
 d={r['ts']:r for r in old}
 for row in new:
  if row['ts'] in d and d[row['ts']]!=row:raise ValueError('Conflicting input timestamp '+str(row['ts']))
  d[row['ts']]=row
 return [d[k] for k in sorted(d)]
def continuous_cost_end(bars,marks,rates):
 for b in bars:
  if b['ts'] not in marks or (b['ts']%(8*H)==0 and b['ts'] not in rates):return b['ts']
 return bars[-1]['ts']+H if bars else START

def day_contribution(curve,trades,funding,start,end):
 prior=next((r for r in curve if r['ts']==start),None)
 rows=[r for r in curve if start<r['ts']<=end]
 if prior is None or not rows:return dict(marked_pnl=None,status='NO_CONTINUOUS_DAY_COVERAGE')
 actual=[t for t in trades if start<=t['ts']<rows[-1]['ts'] and t['reason']!='terminal_liquidation']
 return dict(status='FULL_DAY' if rows[-1]['ts']==end else 'PARTIAL_DAY',start_equity=prior['equity'],end_marked_equity=rows[-1]['equity'],marked_pnl=rows[-1]['equity']-prior['equity'],through=rows[-1]['ts'],fees=sum(t['fee'] for t in actual),slippage=sum(t['slippage'] for t in actual),funding=sum(t['paid'] for t in funding if start<=t['ts']<rows[-1]['ts']),terminal_liquidation_excluded=True)

def validate_mark_source(meta):
 from urllib.parse import urlparse,parse_qs
 u=urlparse(meta.get('url',''));q=parse_qs(u.query)
 valid=u.scheme=='https' and u.netloc=='api.bitget.com' and (u.path=='/api/v2/mix/market/history-mark-candles' or (u.path=='/api/v2/mix/market/candles' and q.get('kLineType')==['mark']))
 if not valid or meta.get('http_status')!=200 or meta.get('code')!='00000':
  raise ValueError('Unverified historical mark price source; uppercase MARK/market prices cannot enter cost ledger. Preserve original evidence and use an explicit audited correction.')

def replay_compatibility(p,required):
 """One audited fetch-only transition, never a generic version bypass."""
 old_hash='78f40cfe3481cae3fc1977607d3b17e7ac789a359aefbdbaa028d54247652943'
 new_hash='d8ba1d1222e454e29988c00b371c9a67f9b7e120cea14706e1bf472090497b78'
 old_manifest='07e516424051a04c1c15e3bb71a9b2c816ac2f8c091e19f551b3c738fd367c53'
 changed=[];proof={}
 # Explicit ST extension changes data fetch / wrapper only for T1/B1.
 # Current and archived whole-file hashes plus exact native function equality are required.
 transition=json.loads((BASE/'st_compatibility.json').read_text())
 current_run=(BASE/'run_research.py').read_bytes()
 if sha(current_run)==transition['new_run_research_sha256']:
  try:
   run=p['files']['source/run_research.py'];old=run['content'].encode()
   manifest=p['files']['source/runtime_manifest.json'];mr=manifest['content'].encode()
   if sha(old)!=run['sha256'] or sha(mr)!=manifest['sha256']:raise ValueError('ST compatibility embedded hash mismatch')
   if sha(old)!=sha(current_run):
    pair=next((x for x in transition['allowed_old_pairs'] if x['source_sha256']==sha(old) and x['manifest_sha256']==sha(mr)),None)
    if pair is None:raise ValueError('Unknown ST extension source/manifest pair')
    frozen=json.loads(mr)
    for name in required:
     entry=p['files']['source/'+name];raw=entry['content'].encode()
     if sha(raw)!=entry['sha256'] or frozen['files'].get(name)!=sha(raw):raise ValueError('Archived source/manifest disagreement')
     if name!='run_research.py' and raw!=(BASE/name).read_bytes():raise ValueError('Non-ST strategy drift')
    def native_bytes(raw):return raw[raw.index(b'def native_signals('):raw.index(b'def fetch(')]
    if native_bytes(old)!=native_bytes(current_run):raise ValueError('Native T1/B1 signal function changed')
    return dict(status='KNOWN_ST_RESEARCH_EXTENSION',changed_files=['run_research.py'],proof=dict(old_source_sha256=sha(old),new_source_sha256=sha(current_run),archived_manifest_sha256=sha(mr),equivalence='Exact unchanged T1/B1 native signal function and all economic references; ST is separate and not backfilled as historical observation'))
  except (KeyError,ValueError,TypeError,StopIteration) as e:return dict(status='UNSUPPORTED',reason=str(e))
 try:
  for name in required:
   entry=p['files']['source/'+name];archived=entry['content'].encode();current=(BASE/name).read_bytes()
   if sha(archived)!=entry['sha256']:raise ValueError('Embedded source digest mismatch')
   if archived==current:continue
   if name!='run_research.py' or sha(archived)!=old_hash or sha(current)!=new_hash:raise ValueError('Unknown source transition')
   # Byte-level whole-file equivalence after exactly the authorized parameter change.
   if archived.count(b"kLineType='MARK'")!=1 or archived.replace(b"kLineType='MARK'",b"kLineType='mark'")!=current:raise ValueError('Not fetch-only equivalent')
   manifest=p['files']['source/runtime_manifest.json'];raw=manifest['content'].encode()
   if sha(raw)!=manifest['sha256'] or sha(raw)!=old_manifest:raise ValueError('Unknown archived runtime manifest')
   frozen=json.loads(raw)
   if any(frozen['files'].get(n)!=p['files']['source/'+n]['sha256'] for n in required):raise ValueError('Archived manifest/source disagreement')
   changed.append(name);proof=dict(old_source_sha256=old_hash,new_source_sha256=new_hash,archived_manifest_sha256=old_manifest,equivalence='Whole source identical after sole MARK-to-mark request literal; replay uses original archived trade bars only')
  return dict(status='KNOWN_MARK_FETCH_ONLY' if changed else 'EXACT_SOURCE',changed_files=changed,proof=proof)
 except (KeyError,ValueError,TypeError) as e:return dict(status='UNSUPPORTED',reason=str(e))

def verify_st_source(p):
 from st_runtime import VERSION as ST_VERSION
 checkpoint=body(p,'run/st_checkpoint.json')
 if checkpoint['version']!=ST_VERSION:raise ValueError('Unknown ST checkpoint version')
 manifest=body(p,'source/runtime_manifest.json')
 for name in ['st_engine.py','st_signals.py','st_indicators.py','st_runtime.py']:
  entry=p['files']['source/'+name];raw=entry['content'].encode()
  if sha(raw)!=entry['sha256'] or manifest['files'].get(name)!=sha(raw) or raw!=(BASE/name).read_bytes():raise ValueError('Unsupported ST source version: '+name)
 return checkpoint

def st_transition_check(signal):
 previous=signal['previous_state'];target=signal['desired_state'];orders=signal.get('incremental_orders',[]);event=signal['event']
 if previous is None:return event=='INITIALIZED' and signal.get('initialization_is_not_live_entry') is True and not orders
 expected='WAIT' if not orders else ('ENTER' if orders[0]['side']=='buy' else 'EXIT') if len(orders)==1 else 'TRANSITIONS'
 state=previous
 for order in orders:
  if order['side']=='buy':
   if state!='CASH':return False
   state='LONG'
  elif order['side']=='sell':
   if state!='LONG':return False
   state='CASH'
  else:return False
 return event==expected and target==state and not signal.get('initialization_is_not_live_entry')

def st_round_check(p):
 if 'run/st_checkpoint.json' not in p['files']:return dict(status='NOT_PRESENT_IN_ORIGINAL_ROUND')
 try:
  from st_signals import features as st_features
  checkpoint=verify_st_source(p);signal=body(p,'run/st_signal.json');bars=archived_bars(p);f=st_features(bars)[bars[-1]['ts']+H]
  checks={k:signal[k]==f[v] for k,v in [('native_entry_flag','entry_a'),('native_exit_flag','exit_a'),('close','close'),('atr10','atr10'),('atr14','atr'),('upper','upper'),('lower','lower'),('supertrend_up','up')]}
  ledger=checkpoint['ledger'];cash=1000+sum((1 if x['side']=='sell' else -1)*x['q']*x['fill']-x['fee'] for x in ledger['orders'])-sum(x['paid'] for x in ledger['fundlog']);q=sum((1 if x['side']=='buy' else -1)*x['q'] for x in ledger['orders'])
  checks['cashflow']=abs(cash-ledger['cash'])<1e-7;checks['quantity']=abs(q-ledger['q'])<1e-8
  checks['transition_receipt']=st_transition_check(signal)
  checks['target']=signal['desired_state']==('LONG' if ledger['q'] else 'CASH')
  return dict(status='SIGNAL_MATCH_LEDGER_RECEIPT_VERIFIED' if all(checks.values()) else 'MISMATCH',checks=checks,previous_state=signal['previous_state'],target_state=signal['desired_state'],event=signal['event'],event_sequence=signal.get('incremental_orders',[]),initialization_is_not_live_entry=signal['initialization_is_not_live_entry'],economic_order_path_replay='NOT_IMPLEMENTED; cashflow and quantity reconciled, not a second independent execution-path replay')
 except (KeyError,ValueError,TypeError) as e:return dict(status='UNSUPPORTED',reason=str(e))

def replay_match_status(checks):
 return 'MATCH' if checks and all(x['matches'] for x in checks.values()) else 'MISMATCH'

def csv_rows(content):return [{k:int(v) if k=='ts' else float(v) if k!='symbol' else v for k,v in r.items()} for r in csv.DictReader(io.StringIO(content))]
def candle_rows(data):return [dict(ts=int(x[0]),open=float(x[1]),high=float(x[2]),low=float(x[3]),close=float(x[4]),volume=float(x[5])) for x in data]
def package(path):
 raw=path.read_bytes();p=json.loads(raw)
 for name,s in p['files'].items():
  b=s['content'].encode()
  if sha(b)!=s['sha256'] or len(b)!=s['bytes']:raise ValueError('Archive hash mismatch '+name)
 return p,sha(raw)
def body(p,name):return json.loads(p['files'][name]['content'])
def archived_bars(p):
 bars=[]
 for spec in body(p,'source/historical_inputs.json'):
  s=p['files']['historical-inputs/'+spec['relative_path']]
  if s['sha256']!=spec['sha256']:raise ValueError('Historical anchor mismatch')
  bars+=csv_rows(s['content'])
 cut=int(datetime.datetime.fromisoformat(body(p,'run/result.json')['closed_data_through_utc']).timestamp()*1000)
 extra=[b for b in candle_rows(body(p,'run/raw/trade_h1.json')['data']) if bars[-1]['ts']<b['ts']<cut]
 bars=validate_bars(bars+sorted(extra,key=lambda b:b['ts']))
 if bars[-1]['ts']+H!=cut:raise ValueError('Archive closed boundary mismatch')
 return bars

def trigger_source(p,verified):
 if p['round_id'] in verified:return 'SCHEDULED_EXTERNALLY_VERIFIED'
 if p.get('kind')=='MANUAL_RESEARCH_VALIDATION':return 'MANUAL'
 return 'UNKNOWN_NOT_INFERRED_FROM_TIMESTAMP'

def review_status(invalid,valid_end,end,issues=(),full_observations=False):
 if invalid:return 'INVALID_BACKTEST_PARTIAL'
 if issues:return 'REVIEW_WITH_EVIDENCE_ISSUES'
 if valid_end<end:return 'PARTIAL_DAY_DIAGNOSTIC'
 return 'REVIEW_COMPLETE' if full_observations else 'BACKTEST_COMPLETE_OBSERVATION_COVERAGE_LIMITED'

def exit_code(status):
 return 1 if status=='BLOCKED_PARTIAL' else 2 if status in ('REVIEW_WITH_EVIDENCE_ISSUES','INVALID_BACKTEST_PARTIAL') else 0

def terminal_receipt(path,p,digest):
 receipt_path=path.parent/'state.json'
 if not receipt_path.is_file():raise ValueError('Original terminal state unavailable; completion cannot be verified')
 raw=receipt_path.read_bytes();state=json.loads(raw)
 if state.get('status')!='COMPLETE':raise ValueError('Original round terminal state is not COMPLETE')
 if state.get('round_id')!=p['round_id'] or state.get('archive_sha256')!=digest:raise ValueError('Original terminal receipt identity/archive mismatch')
 return dict(path=str(receipt_path),sha256=sha(raw),state=state)

def observation_coverage(rows,start,end,asof=None):
 expected=set(range(start+3*60000,end,H))
 verified={int(datetime.datetime.fromisoformat(x['scheduled_utc']).timestamp()*1000) for x in rows if x['trigger_source']=='SCHEDULED_EXTERNALLY_VERIFIED'}
 covered=expected & verified
 asof=int(datetime.datetime.now(UTC).timestamp()*1000) if asof is None else asof
 due={t for t in expected if t<=asof}
 return dict(coverage_asof_utc_ms=asof,due_scheduled_slots=len(due),completed_due_scheduled_slots=len(due & covered),future_scheduled_slots_utc_ms=sorted(expected-due),future_scheduled_slots=len(expected-due),due_slots_complete=due<=covered,observed_rounds=len(rows),scheduled_rounds=sum(x['trigger_source']=='SCHEDULED_EXTERNALLY_VERIFIED' for x in rows),unknown_trigger_rounds=sum(x['trigger_source']=='UNKNOWN_NOT_INFERRED_FROM_TIMESTAMP' for x in rows),manual_rounds=sum(x['trigger_source']=='MANUAL' for x in rows),expected_scheduled_slots=len(expected),verified_scheduled_slots=len(covered),missing_scheduled_slots_utc_ms=sorted(due-covered),full_day_scheduled_observations=covered==expected,not_full_day=covered!=expected,warning='Coverage requires distinct externally verified scheduled slots and COMPLETE receipts; historical bars never backfill observations')

def run_branch(report,name,fn):
 try:
  value=fn()
  report.setdefault('branches',{})[name]=dict(status='COMPUTED')
  return value
 except Exception as e:
  report.setdefault('branches',{})[name]=dict(status='BLOCKED',error=type(e).__name__+': '+str(e))
  return None

def st_observation_coverage(rows,start,end,asof=None):
 activation=json.loads((HERE/'ST_ACTIVATION.json').read_text())
 first=int(datetime.datetime.fromisoformat(activation['scheduled_utc']).timestamp()*1000)
 c=observation_coverage(rows,start,end,asof)
 expected={t for t in range(start+180000,end,H) if t>=first}
 verified={int(datetime.datetime.fromisoformat(x['scheduled_utc']).timestamp()*1000) for x in rows if x['trigger_source']=='SCHEDULED_EXTERNALLY_VERIFIED'}
 covered=expected & verified
 asof=c['coverage_asof_utc_ms'];due={t for t in expected if t<=asof}
 c.update(due_scheduled_slots=len(due),completed_due_scheduled_slots=len(due & covered),future_scheduled_slots_utc_ms=sorted(expected-due),future_scheduled_slots=len(expected-due),due_slots_complete=due<=covered,expected_scheduled_slots=len(expected),pre_activation_slots=len(range(start+180000,end,H))-len(expected),verified_scheduled_slots=len(covered),missing_scheduled_slots_utc_ms=sorted(due-covered),full_day_scheduled_observations=len(expected)==24 and covered==expected,not_full_day=not(len(expected)==24 and covered==expected),activation=activation,calendar_day_full_st_observations=len(expected)==24 and covered==expected,post_activation_complete=covered==expected,coverage_status='NOT_APPLICABLE_BEFORE_ACTIVATION' if not expected else 'POST_ACTIVATION_COMPLETE' if covered==expected else 'POST_ACTIVATION_LIMITED',scope='Only scheduled slots on or after verified first formal ST activation; reconstruction does not backfill observations')
 return c

def fixed_backtest(a,latest,start,end,report):
 original=body(latest,'run/result.json')
 report['backtest_input_archive']=dict(round_id=latest['round_id'],scheduled_utc=latest['scheduled_utc'],acquired_asof_utc=original['asof_utc'],closed_data_through_utc=original['closed_data_through_utc'],acquired_after_report_day=int(datetime.datetime.fromisoformat(original['asof_utc']).timestamp()*1000)>=end,role='BACKTEST_CUTOFF_INPUT_ONLY; later collection is post-hoc reconstruction, not proof of covered-day observations or then-known costs')
 bars=[b for b in archived_bars(latest) if b['ts']<end];states,_=daily_states(bars)
 costs={}
 for spec in json.loads((BASE/'historical_cost_inputs.json').read_text()):
  path=a.history_root/spec['relative_path'];b=path.read_bytes()
  if sha(b)!=spec['sha256']:raise ValueError('Cost anchor mismatch')
  costs[path.name]=csv_rows(b.decode())
 rates={r['ts']:r['fundingRate'] for r in costs['btcusdt_usdt_futures_funding.csv']}
 marks={r['ts']:r for r in costs['btcusdt_usdt_futures_mark_1h_funding_window.csv']}
 for x in body(latest,'run/raw/history_funding.json')['data']:
  t=int(x['fundingTime']);v=float(x['fundingRate'])
  if t in rates and rates[t]!=v:raise ValueError('Funding overlap conflict')
  rates[t]=v
 validate_mark_source(body(latest,'run/raw/mark_h1.metadata.json'))
 for b in candle_rows(body(latest,'run/raw/mark_h1.json')['data']):
  b.pop('volume',None)
  if b['ts'] in marks and marks[b['ts']]!=b:raise ValueError('Mark overlap conflict')
  marks[b['ts']]=b
 if a.mark_supplement:
  supp=json.loads(a.mark_supplement.read_text())
  validate_mark_source(dict(url=supp.get('url',''),http_status=supp['http_status'],code=supp['body'].get('code')))
  for b in candle_rows(supp['body']['data']):
   b.pop('volume',None)
   if b['ts'] in marks and marks[b['ts']]!=b:raise ValueError('Supplement conflict')
   marks[b['ts']]=b
  report['supplement']=dict(path=str(a.mark_supplement),sha256=sha(a.mark_supplement.read_bytes()),retrieved_utc=supp['retrieved_utc'],usage='POST_HOC_COST_REPAIR_NOT_KNOWN_AT_ORIGINAL_ROUND')
 bs=[b for b in bars if b['ts']>=START];desired_end=bs[-1]['ts']+H;valid_end=continuous_cost_end(bs,marks,rates);bs=[b for b in bs if b['ts']<valid_end]
 if not bs:raise ValueError('No actual-funded contiguous backtest interval')
 report['backtest_coverage']=dict(requested_end=end,available_trade_end=desired_end,actual_cost_complete_end=valid_end,full_report_day=valid_end>=end,missing_cost_at=valid_end if valid_end<desired_end else None)
 write(a.output/'backtest_inputs.json',dict(bars=bars,ledger_bars=bs,funding=rates,marks=marks,states=states,protocol=json.loads((HERE/'PROTOCOL.json').read_text()),diagnostic_seen_history=True))
 if a.mark_supplement:write(a.output/'posthoc_mark_supplement.json',supp)
 report['stages'].append('FIXED_BACKTEST_FIRST');results={}
 for name in ['CASH','HOLD','T1','B1']:
  result,curve,trades,fund=simulate(bs,name,states,rates,marks,.0002,0,a.output/'ledger'/name)
  results[name]=dict(cumulative_frozen_terminal_liquidation=result,continuous_marked_equity=curve[-1]['equity'] if curve else None,day_contribution=day_contribution(curve,trades,fund,start,end))
 report['backtest']=results
 return dict(results=results,valid_end=valid_end,desired_end=desired_end)

def st_checkpoint_review(latest,start,end):
 if 'run/st_checkpoint.json' not in latest['files']:
  return dict(strategy='ST-H1-LO-v1',status='NOT_PRESENT_IN_ORIGINAL_HOURLY_EVIDENCE',day_contribution=None)
 from st_runtime import day_contribution as st_day_contribution
 cp=verify_st_source(latest);signal=body(latest,'run/st_signal.json')
 cutoff=int(datetime.datetime.fromisoformat(cp['closed_through_utc']).timestamp()*1000)
 ledger=cp['ledger']
 if ledger['status']!='COMPLETE' or not ledger['curve'] or ledger['curve'][-1]['ts']!=cutoff:raise ValueError('ST checkpoint ledger incomplete or cutoff inconsistent')
 times=[x['ts'] for x in ledger['curve']]
 if times!=list(range(START+H,cutoff+H,H)) or ledger.get('next_bar_ts')!=cutoff or ledger.get('boundary_processed')!=cutoff:raise ValueError('ST continuous curve gap or boundary receipt mismatch')
 if signal.get('summary',{}).get('end')!=cutoff:raise ValueError('ST cumulative summary cutoff mismatch')
 if signal.get('summary',{}).get('status')!='COMPLETE' or not st_transition_check(signal):raise ValueError('ST summary or transition receipt inconsistent')
 contribution=st_day_contribution(cp,start,end)
 cutoff=int(datetime.datetime.fromisoformat(cp['closed_through_utc']).timestamp()*1000)
 return dict(strategy='ST-H1-LO-v1',version=cp['version'],status='APPROVED_RESEARCH_TRACKING_NOT_ECONOMICALLY_VALIDATED',day_contribution=contribution,complete_day=contribution['status']=='FULL_DAY_RESEARCH_RECONSTRUCTION' and cutoff>=end,closed_through_utc=cp['closed_through_utc'],cumulative_research_metrics=signal.get('summary'),cumulative_metrics_asof=cp['closed_through_utc'],risk_comparability='ST uses 0.5% initial risk with 2 ATR stop; T1/B1 90% equity exposure. No cross-risk superiority claim.',economic_order_path_replay='NOT_IMPLEMENTED; independent signal and receipt arithmetic only',checkpoint_source_round=latest['round_id'])

def reconcile_round(p,digest,a,start,end):
 original=body(p,'run/result.json');asof=int(datetime.datetime.fromisoformat(original['asof_utc']).timestamp()*1000)
 if not start<=asof<end:return None
 row=dict(round_id=p['round_id'],scheduled_utc=p['scheduled_utc'],actual_asof_utc=original['asof_utc'],trigger_source=trigger_source(p,a.verified_scheduled_round),archive_sha256=digest,archive_version=original['version'],notification='NOT_INFERRED_FROM_SIGNAL',execution='NO_ACCOUNT_OR_FILL_EVIDENCE')
 scheduled=datetime.datetime.fromisoformat(p['scheduled_utc'])
 row['slot_aligned']=scheduled.minute==3 and scheduled.second==0 and scheduled.microsecond==0
 row['asof_delay_seconds']=asof/1000-scheduled.timestamp()
 # ST checks have a separate fault boundary even when native replay is unsupported.
 try:row['st_research']=st_round_check(p)
 except Exception as e:row['st_research']=dict(status='BLOCKED',error=type(e).__name__+': '+str(e))
 try:
  required=['run_research.py','rules.py','signal_report.py','user_data/strategies/FrozenDailyResearch.py']+[x['path'] for x in json.loads((BASE/'reference_manifest.json').read_text())['frozen_references'][:3]]
  compatibility=replay_compatibility(p,required);row['source_compatibility']=compatibility
  if original['version']!=VERSION or compatibility['status']=='UNSUPPORTED':
   row.update(status='VERSION_REPLAY_UNSUPPORTED',reason='Keep original result; historical code differs from current replay code')
  else:
   then=archived_bars(p);checks={}
   for name in ['T1','B1']:
    df,_=native_signals(then,name);actual=describe_signal(df,name);expected=original['native_signal_checks'][name]['signal_report'];checks[name]=dict(matches=actual==expected,target_state=actual['target_state'],event=actual['event'])
   row.update(status=replay_match_status(checks),signals=checks)
 except Exception as e:row.update(status='REPLAY_BLOCKED',error=type(e).__name__+': '+str(e))
 return row

def main():
 ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--date',required=True);ap.add_argument('--round',type=Path,action='append',required=True);ap.add_argument('--history-root',type=Path,required=True);ap.add_argument('--output',type=Path,required=True);ap.add_argument('--mark-supplement',type=Path);ap.add_argument('--verified-scheduled-round',action='append',default=[]);a=ap.parse_args()
 a.output.mkdir(parents=True,exist_ok=False)
 source_snapshot={p.name:p.read_bytes() for p in sorted(HERE.glob('*.py'))+[HERE/'PROTOCOL.json',HERE/'ST_ACTIVATION.json']}
 start,end=day_window(a.date)
 try:runtime=verify_runtime()
 except Exception as e:
  failure=dict(status='BLOCKED_PARTIAL',stage='RUNTIME_PREFLIGHT',report_date_beijing=a.date,generated_utc=datetime.datetime.now(UTC).isoformat(),error=type(e).__name__+': '+str(e),calculations_started=False,daily_source_hashes={n:sha(b) for n,b in source_snapshot.items()})
  write(a.output/'report.json',failure)
  files={}
  for n,b in dict(source_snapshot,**{'report.json':(a.output/'report.json').read_bytes()}).items():files[n]=dict(content=b.decode(),bytes=len(b),sha256=sha(b))
  write(a.output/'google-evidence.json',dict(kind='DAILY_REVIEW_PREFLIGHT_FAILURE',files=files))
  print(json.dumps(failure));return 1
 packs=[];errors=[];receipts={}
 for path in a.round:
  try:
   p,digest=package(path)
   receipt=terminal_receipt(path,p,digest)
   result=body(p,'run/result.json')
   for value in [result['closed_data_through_utc'],result['asof_utc'],p['scheduled_utc']]:
    if datetime.datetime.fromisoformat(value).utcoffset() is None:raise ValueError('Archive time is timezone-naive')
   if not isinstance(result['version'],str):raise ValueError('Invalid archive version')
   receipts[p['round_id']]=receipt
   existing=next((old for old in packs if old[0]['round_id']==p['round_id']),None)
   if existing and existing[1]!=digest:raise ValueError('Conflicting archives for same round ID')
   if not existing:packs.append((p,digest,path))
  except Exception as e:errors.append(dict(path=str(path),error=str(e)))
 report=dict(version='BTC_DAILY_REVIEW_V1',engineering_revision='DAILY_BRANCH_REVIEW_V2_20261019',research_version=VERSION,generated_utc=datetime.datetime.now(UTC).isoformat(),report_date_beijing=a.date,day_start_utc_ms=start,day_end_exclusive_utc_ms=end,backtest_fixed_start=START,runtime=runtime,adopted=False,orders_enabled=False,provenance=[dict(path=str(path),sha256=digest,round_id=p['round_id']) for p,digest,path in packs],input_errors=errors,terminal_receipts=receipts,stages=[])
 latest=max(packs,key=lambda x:datetime.datetime.fromisoformat(body(x[0],'run/result.json')['closed_data_through_utc']).timestamp())[0] if packs else None
 def require_latest():
  if latest is None:raise ValueError('No valid archived input')
  return latest
 # Fixed economic backtest is attempted first. Failures do not suppress independent evidence checks.
 bt=run_branch(report,'fixed_backtest',lambda:fixed_backtest(a,require_latest(),start,end,report))
 st_packs=[x for x in packs if 'run/st_checkpoint.json' in x[0]['files']]
 st_latest=max(st_packs,key=lambda x:datetime.datetime.fromisoformat(body(x[0],'run/result.json')['closed_data_through_utc']).timestamp())[0] if st_packs else latest
 report['st_research']=run_branch(report,'st_checkpoint',lambda:st_checkpoint_review(st_latest or require_latest(),start,end))
 comparisons=[]
 report['stages'].append('ACTUAL_ROUND_RECONCILIATION')
 for p,digest,path in packs:
  row=run_branch(report,'round:'+p['round_id'],lambda:reconcile_round(p,digest,a,start,end))
  if row is not None:comparisons.append(row)
 report['round_comparisons']=comparisons
 coverage_asof=int(datetime.datetime.fromisoformat(report['generated_utc']).timestamp()*1000)
 report['actual_observation_coverage']=observation_coverage(comparisons,start,end,coverage_asof)
 st_rows=[x for x in comparisons if x['st_research']['status']!='NOT_PRESENT_IN_ORIGINAL_ROUND']
 report['st_observation_coverage']=dict(st_observation_coverage(st_rows,start,end,coverage_asof),initialized_rounds=sum(x['st_research'].get('event')=='INITIALIZED' for x in st_rows),not_backfilled_before_integration=True)
 issues=[]
 if errors:issues.append('INVALID_INPUT_ARCHIVES')
 blocked=[k for k,v in report.get('branches',{}).items() if v['status']=='BLOCKED']
 if blocked:issues.append('BLOCKED_BRANCHES')
 if any(x['st_research']['status'] not in ('NOT_PRESENT_IN_ORIGINAL_ROUND','SIGNAL_MATCH_LEDGER_RECEIPT_VERIFIED') for x in comparisons):issues.append('ST_SIGNAL_OR_RECEIPT_CHECK_FAILED')
 invalid=[n for n,r in (bt or {}).get('results',{}).items() if r['cumulative_frozen_terminal_liquidation']['status']!='COMPLETE']
 report['invalid_strategies']=invalid
 if invalid:issues.append('INVALID_LEDGER_NO_COMPLETE_COMPARISON')
 if bt and bt['valid_end']<bt['desired_end']:issues.append('COST_DATA_GAP')
 if any(x['status']!='MATCH' for x in comparisons):issues.append('REPLAY_MISMATCH_OR_UNSUPPORTED_VERSION')
 st_required=report['st_observation_coverage']['expected_scheduled_slots']>0
 if st_required and not (report.get('st_research') or {}).get('complete_day',False):issues.append('ST_DAY_RECONSTRUCTION_INCOMPLETE')
 if st_required and not report['st_observation_coverage']['post_activation_complete']:issues.append('ST_OBSERVATION_COVERAGE_LIMITED')
 report['diagnosis']=dict(data_and_engineering_issues=issues,economic_diagnosis='NOT_PERFORMED_BY_FIXED_REPLAY',blocked_branches=blocked)
 report['optimization']=dict(status='INSUFFICIENT_EVIDENCE' if issues else 'AWAITING_EVIDENCE_BASED_ECONOMIC_DIAGNOSIS',rule_change=False,economic_review_completed=False,decision='HOLD_FROZEN_RULES_PENDING_REVIEW',candidate_research='NOT_RUN_BY_THIS_ENTRYPOINT',reason='Replay agreement and one daily outcome cannot establish economic superiority; no forced daily tuning.',next_action='Review cumulative and prospective evidence; register a frozen hypothesis only when supported. candidate_registry.py records evidence, not automatic adoption.')
 report['status']='BLOCKED_PARTIAL' if bt is None else review_status(invalid,bt['valid_end'],end,issues,report['actual_observation_coverage']['full_day_scheduled_observations'])
 report['daily_source_hashes']={n:sha(b) for n,b in source_snapshot.items()}
 if any((HERE/n).read_bytes()!=b for n,b in source_snapshot.items()):raise ValueError('Daily source changed during run; no final publication')
 write(a.output/'report.json',report)
 files={}
 for p in sorted(a.output.rglob('*.json')):
  b=p.read_bytes();files[str(p.relative_to(a.output))]=dict(sha256=sha(b),bytes=len(b),content=b.decode())
 for name,b in source_snapshot.items():
  files['source/'+name]=dict(sha256=sha(b),bytes=len(b),content=b.decode())
 write(a.output/'google-evidence.json',dict(kind='DAILY_REVIEW_EVIDENCE',report_date=a.date,files=files,source_archives=report['provenance']))
 package(a.output/'google-evidence.json')
 print(json.dumps(dict(status=report['status'],output=str(a.output),backtest_coverage=report.get('backtest_coverage'),error=report.get('error')),ensure_ascii=False))
 return exit_code(report['status'])
if __name__=='__main__':sys.exit(main())
