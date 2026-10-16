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

def review_status(invalid,valid_end,end):
 return 'INVALID_BACKTEST_PARTIAL' if invalid else 'PARTIAL_DAY_DIAGNOSTIC' if valid_end<end else 'BACKTEST_COMPLETE_OBSERVATION_COVERAGE_LIMITED'

def main():
 ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--date',required=True);ap.add_argument('--round',type=Path,action='append',required=True);ap.add_argument('--history-root',type=Path,required=True);ap.add_argument('--output',type=Path,required=True);ap.add_argument('--mark-supplement',type=Path);ap.add_argument('--verified-scheduled-round',action='append',default=[]);a=ap.parse_args()
 a.output.mkdir(parents=True,exist_ok=False)
 source_snapshot={p.name:p.read_bytes() for p in sorted(HERE.glob('*.py'))+[HERE/'PROTOCOL.json']}
 start,end=day_window(a.date);runtime=verify_runtime();packs=[];errors=[]
 for path in a.round:
  try:
   p,digest=package(path)
   existing=next((old for old in packs if old[0]['round_id']==p['round_id']),None)
   if existing and existing[1]!=digest:raise ValueError('Conflicting archives for same round ID')
   if not existing:packs.append((p,digest,path))
  except Exception as e:errors.append(dict(path=str(path),error=str(e)))
 report=dict(version='BTC_DAILY_REVIEW_V1',research_version=VERSION,generated_utc=datetime.datetime.now(UTC).isoformat(),report_date_beijing=a.date,day_start_utc_ms=start,day_end_exclusive_utc_ms=end,backtest_fixed_start=START,runtime=runtime,adopted=False,orders_enabled=False,provenance=[dict(path=str(path),sha256=digest,round_id=p['round_id']) for p,digest,path in packs],input_errors=errors,stages=[])
 try:
  if not packs:raise ValueError('No valid archived input')
  latest=max(packs,key=lambda x:body(x[0],'run/result.json')['closed_data_through_utc'])[0]
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
  for b in candle_rows(body(latest,'run/raw/mark_h1.json')['data']):
   b.pop('volume',None)
   if b['ts'] in marks and marks[b['ts']]!=b:raise ValueError('Mark overlap conflict')
   marks[b['ts']]=b
  if a.mark_supplement:
   supp=json.loads(a.mark_supplement.read_text())
   if supp['http_status']!=200 or supp['body']['code']!='00000':raise ValueError('Invalid supplement response')
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
  report['stages'].append('ACTUAL_ROUND_RECONCILIATION');comparisons=[]
  for p,digest,path in packs:
   original=body(p,'run/result.json');asof=int(datetime.datetime.fromisoformat(original['asof_utc']).timestamp()*1000)
   if not start<=asof<end:continue
   row=dict(round_id=p['round_id'],scheduled_utc=p['scheduled_utc'],actual_asof_utc=original['asof_utc'],slot_aligned=datetime.datetime.fromisoformat(p['scheduled_utc']).minute==3 and datetime.datetime.fromisoformat(p['scheduled_utc']).second==0,trigger_source=trigger_source(p,a.verified_scheduled_round),archive_sha256=digest,archive_version=original['version'],notification='NOT_INFERRED_FROM_SIGNAL',execution='NO_ACCOUNT_OR_FILL_EVIDENCE')
   # Never silently replay changed historical rules with today's implementation.
   required=['run_research.py','rules.py','signal_report.py','user_data/strategies/FrozenDailyResearch.py']+list(json.loads((BASE/'reference_manifest.json').read_text())['frozen_references'][i]['path'] for i in range(3))
   if original['version']!=VERSION or any(p['files']['source/'+n]['sha256']!=sha((BASE/n).read_bytes()) for n in required):
    row.update(status='VERSION_REPLAY_UNSUPPORTED',reason='Keep original result; historical code differs from current replay code')
   else:
    then=archived_bars(p);checks={}
    for name in ['T1','B1']:
     df,_=native_signals(then,name);actual=describe_signal(df,name);expected=original['native_signal_checks'][name]['signal_report'];checks[name]=dict(matches=actual==expected,target_state=actual['target_state'],event=actual['event'])
    row.update(status='MATCH' if all(x['matches'] for x in checks.values()) else 'MISMATCH',signals=checks)
   comparisons.append(row)
  report['round_comparisons']=comparisons
  report['actual_observation_coverage']=dict(observed_rounds=len(comparisons),scheduled_rounds=sum(x['trigger_source']=='SCHEDULED_EXTERNALLY_VERIFIED' for x in comparisons),unknown_trigger_rounds=sum(x['trigger_source']=='UNKNOWN_NOT_INFERRED_FROM_TIMESTAMP' for x in comparisons),manual_rounds=sum(x['trigger_source']=='MANUAL' for x in comparisons),not_full_day=True,warning='Only explicitly supplied actual rounds are evidenced; historical bars never backfill observations')
  issues=[]
  if errors:issues.append('INVALID_INPUT_ARCHIVES')
  invalid=[name for name,r in results.items() if r['cumulative_frozen_terminal_liquidation']['status']!='COMPLETE']
  report['invalid_strategies']=invalid
  if invalid:issues.append('INVALID_LEDGER_NO_COMPLETE_COMPARISON')
  if valid_end<desired_end:issues.append('COST_DATA_GAP')
  if any(x['status']!='MATCH' for x in comparisons):issues.append('REPLAY_MISMATCH_OR_UNSUPPORTED_VERSION')
  report['optimization']=dict(status='REPAIR_EVIDENCE_FIRST' if issues else 'NO_RULE_CHANGE_JUSTIFIED_BY_THIS_CHECK',issues=issues,rule_change=False,reason='A short seen-data diagnostic and matching execution do not establish investment advantage. Preserve all frozen baselines; no daily forced parameter changes.',candidate_path='research/daily-review-v1/candidates/<new-version>/; freeze hypothesis, rule code, inputs, costs and falsification before running the same fixed comparisons; explicit adoption is separate')
  report['status']=review_status(invalid,valid_end,end)
 except Exception as e:
  report.update(status='BLOCKED_PARTIAL',error=type(e).__name__+': '+str(e))
 report['daily_source_hashes']={n:sha(b) for n,b in source_snapshot.items()}
 if any((HERE/n).read_bytes()!=b for n,b in source_snapshot.items()):raise ValueError('Daily source changed during run; no final publication')
 write(a.output/'report.json',report)
 files={}
 for p in sorted(a.output.rglob('*.json')):
  b=p.read_bytes();files[str(p.relative_to(a.output))]=dict(sha256=sha(b),bytes=len(b),content=b.decode())
 for name,b in source_snapshot.items():
  files['source/'+name]=dict(sha256=sha(b),bytes=len(b),content=b.decode())
 write(a.output/'google-evidence.json',dict(kind='DAILY_REVIEW_PARTIAL_VALIDATION',report_date=a.date,files=files,source_archives=report['provenance']))
 package(a.output/'google-evidence.json')
 print(json.dumps(dict(status=report['status'],output=str(a.output),backtest_coverage=report.get('backtest_coverage'),error=report.get('error')),ensure_ascii=False))
 return 1 if report['status']=='BLOCKED_PARTIAL' else 0
if __name__=='__main__':sys.exit(main())
