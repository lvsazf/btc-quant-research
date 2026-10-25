"""Independent incremental ST research ledger. No network or account access."""
import json,hashlib,datetime,copy,math
from pathlib import Path
from st_engine import simulate
from st_signals import features
from st_indicators import H
START=1783900800000 # 2026-07-13 00:00 UTC
VERSION='ST_H1_LO_V1_CONTINUOUS_RESEARCH_20261019'
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def utc(t):return datetime.datetime.fromtimestamp(t/1000,datetime.timezone.utc).isoformat()
def load_previous(storage,task_id,scheduled,exclude=None):
 candidates=[]
 for path in storage.glob('*/state.json'):
  s=json.loads(path.read_text())
  if s.get('task_id')!=task_id or s.get('round_id')==exclude:continue
  cp=path.parent/'run/st_checkpoint.json'
  if s.get('status')!='COMPLETE':continue
  if not cp.exists():
   archive=path.parent/'google-evidence.json'
   if s.get('st_version') or (archive.exists() and b'run/st_checkpoint.json' in archive.read_bytes()):raise ValueError('Completed ST round is missing its archived local checkpoint; restore exact bytes before continuing')
   continue
  if s['scheduled_utc']>=scheduled:raise ValueError('Later ST round exists; cannot branch ledger backwards')
  candidates.append((s['scheduled_utc'],path,s,cp))
 if not candidates:return None
 _,path,s,cp=max(candidates,key=lambda x:x[0]);archive=path.parent/'google-evidence.json'
 if digest(archive)!=s['archive_sha256']:raise ValueError('Previous ST archive hash mismatch')
 pack=json.loads(archive.read_text());spec=pack['files']['run/st_checkpoint.json']
 if digest(cp)!=spec['sha256'] or cp.read_text()!=spec['content']:raise ValueError('Previous ST checkpoint not equal to archived bytes')
 state=json.loads(cp.read_text())
 if state['version']!=VERSION:raise ValueError('Unknown ST checkpoint version')
 return dict(path=str(cp),round_id=s['round_id'],archive_sha256=s['archive_sha256'],checkpoint_sha256=digest(cp))
def object_hash(x):return hashlib.sha256(json.dumps(x,sort_keys=True,separators=(',',':')).encode()).hexdigest()
def prefix_hashes(bars,marks,rates,cut):
 return dict(trade=object_hash([b for b in bars if b['ts']<cut]),mark=object_hash({t:marks[t] for t in sorted(marks) if START<=t<cut}),funding=object_hash({t:rates[t] for t in sorted(rates) if START<=t<=cut}))
def numeric(v):
 x=float(v)
 if not math.isfinite(x):raise ValueError('Non-finite cost or boundary input')
 return x
def calculate(bars,bodies,history_root,out,previous=None):
 from rules import load_csv
 root=Path(__file__).parent
 specs=json.loads((root/'historical_cost_inputs.json').read_text())
 for spec in specs:
  if digest(history_root/spec['relative_path'])!=spec['sha256']:raise ValueError('ST historical cost anchor drift')
 rates={int(r['ts']):r['fundingRate'] for r in load_csv(history_root/specs[0]['relative_path'])}
 marks={int(r['ts']):{k:r[k] for k in ('open','high','low','close')} for r in load_csv(history_root/specs[1]['relative_path'])}
 cut=bars[-1]['ts']+H
 seen_rates=set()
 for x in bodies['history_funding']['data']:
  t=int(x['fundingTime']);v=numeric(x['fundingRate'])
  if t%(8*H) or t>cut or t in seen_rates:raise ValueError('Invalid, future or duplicate funding timestamp')
  seen_rates.add(t)
  if t in rates and rates[t]!=v:raise ValueError('ST funding overlap conflict')
  rates[t]=v
 seen_marks=set()
 for x in bodies['mark_h1']['data']:
  t=int(x[0]);v={k:numeric(x[i]) for i,k in enumerate(('open','high','low','close'),1)}
  if t%H or t>cut or t in seen_marks:raise ValueError('Invalid, future or duplicate mark timestamp')
  seen_marks.add(t)
  if t<cut and not 0<v['low']<=min(v['open'],v['close'])<=max(v['open'],v['close'])<=v['high']:raise ValueError('Invalid mark OHLC')
  if t in marks and marks[t]!=v:raise ValueError('ST mark overlap conflict')
  marks[t]=v
 boundary=next((x for x in bodies['trade_h1']['data'] if int(x[0])==cut),None)
 if boundary is None or cut not in marks:raise ValueError('Current boundary open unavailable; cannot invent next-open execution price')
 raw=numeric(boundary[1]);markopen=marks[cut]['open']
 if min(raw,markopen)<=0:raise ValueError('Invalid boundary open')
 # Only current open is used; current high/low/close are unclosed and forbidden.
 marks[cut]={'open':markopen,'close':markopen,'high':markopen,'low':markopen}
 fs=features(bars);p=None
 if previous:
  path=Path(previous['path'])
  if digest(path)!=previous['checkpoint_sha256']:raise ValueError('ST previous changed during run')
  p=json.loads(path.read_text())
  if p['version']!=VERSION:raise ValueError('ST version mismatch')
  boundary_before=p['boundary_open']
  t=boundary_before['ts']
  if prefix_hashes(bars,marks,rates,t)!=p['used_input_hashes']:raise ValueError('Previously used ST trade/mark/funding prefix revised; immutable ledger continuation refused')
  trade_before=next((b['open'] for b in bars if b['ts']==t),raw if t==cut else None)
  if trade_before!=boundary_before['trade_open'] or t not in marks or marks[t]['open']!=boundary_before['mark_open']:raise ValueError('Previously executed boundary open revised; cannot mix old execution with revised candle')
 start=p['ledger']['next_bar_ts'] if p else START
 if start>cut:raise ValueError('ST future checkpoint')
 bs=[b for b in bars if start<=b['ts']<cut]
 if bs and bs[0]['ts']!=start:raise ValueError('ST history gap')
 if not bs and start!=cut:raise ValueError('ST no new closed bars despite gap')
 for b in bs:
  if b['ts'] not in marks:raise ValueError('ST closed mark gap')
 for t in range(start,cut+1,H):
  if t%(8*H)==0 and t not in rates:raise ValueError('ST funding gap')
 before_count=len(p['ledger']['orders']) if p else 0
 oldstate='LONG' if p and p['ledger']['q'] else 'CASH' if p else None
 ledger=copy.deepcopy(p['ledger']) if p else None
 if bs:ledger=simulate(bs,fs,'A',rates,marks,continuous=True,previous=ledger)[-1]
 if ledger is None:raise ValueError('ST initialization requires fixed start coverage')
 stub=dict(ts=cut,open=raw,high=raw,low=raw,close=raw)
 result=simulate([stub],fs,'A',rates,marks,continuous=True,previous=ledger,boundary_only=True)
 summary,curve,orders,fundlog,trades,ledger=result
 summary['name']='ST-H1-LO-v1';summary['start']=START;summary['window']='Cumulative continuous research ledger since fixed start; no terminal liquidation'
 if ledger['status']!='COMPLETE':raise ValueError('ST ledger invalid: '+ledger['status'])
 neworders=orders[before_count:];desired='LONG' if ledger['q'] else 'CASH'
 event='INITIALIZED' if p is None else 'WAIT' if not neworders else 'TRANSITIONS'
 if p is not None and len(neworders)==1:event='ENTER' if neworders[0]['side']=='buy' else 'EXIT'
 f=fs[cut]
 report=dict(strategy='ST-H1-LO-v1',version=VERSION,status='RESEARCH_TRACKING_NOT_ECONOMICALLY_VALIDATED',source='Independent audited research signal and cost ledger; NOT Freqtrade native order/cost certification',previous_state=oldstate,desired_state=desired,event=event,native_entry_flag=bool(f['entry_a']),native_exit_flag=bool(f['exit_a']),latest_closed_h1_open_utc=utc(cut-H),signal_available_utc=utc(cut),close=f['close'],atr10=f['atr10'],upper=f['upper'],lower=f['lower'],supertrend_up=f['up'],atr14=f['atr'],research_quantity=ledger['q'],research_stop=ledger['stop'],research_equity_at_boundary=summary['final_equity'],incremental_orders=[] if p is None else neworders,historical_initialization_order_count=len(orders) if p is None else 0,initialization_is_not_live_entry=p is None,account_execution=False,not_live_execution_price=True,stop_execution='Closed H1 reconstruction only, not hosted stop',summary=summary)
 checkpoint=dict(version=VERSION,strategy='ST-H1-LO-v1',fixed_start_utc=utc(START),closed_through_utc=utc(cut),previous=previous,used_input_hashes=prefix_hashes(bars,marks,rates,cut),boundary_open=dict(ts=cut,trade_open=raw,mark_open=markopen),ledger=ledger)
 for name,value in [('st_checkpoint.json',checkpoint),('st_signal.json',report),('st_inputs.json',dict(cost_anchors=specs,funding=rates,marks={t:marks[t] for t in range(START,cut+1,H) if t in marks},boundary_open_only=stub))]:
  (out/name).write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n')
 return report

def day_contribution(checkpoint,start,end):
 """Beijing or explicit UTC boundaries; curves are pre-next-open, no terminal liquidation."""
 ledger=checkpoint['ledger'];index={r['ts']:r for r in ledger['curve']}
 if start not in index or end not in index:
  return dict(status='NO_COMPLETE_CONTINUOUS_DAY_COVERAGE',marked_pnl=None)
 a=index[start]['equity'];b=index[end]['equity']
 orders=[x for x in ledger['orders'] if start<=x['ts']<end]
 funds=[x for x in ledger['fundlog'] if start<=x['ts']<end]
 return dict(status='FULL_DAY_RESEARCH_RECONSTRUCTION',start_equity=a,end_marked_equity=b,marked_pnl=b-a,return_pct=(b/a-1)*100,fees=sum(x['fee'] for x in orders),slippage=sum(x['slippage'] for x in orders),funding=sum(x['paid'] for x in funds),orders=orders,terminal_liquidation_excluded=True,not_proof_of_historical_live_observation=True)
