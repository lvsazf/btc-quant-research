"""Isolated fixed daily research; accounting conventions reused from audited core/tactical ledger."""
import sys,json,hashlib,datetime,csv,subprocess
from pathlib import Path
from bisect import bisect_right
sys.path.insert(0,str(Path(__file__).resolve().parent.parent/'btc-core-tactical-20261016'))
from engine import floorq,load_csv,H,FEE
P=Path(__file__).resolve().parent
D=24*H

def daily_states(bars):
 groups={}
 for b in bars:groups.setdefault(b['ts']//D*D,[]).append(b)
 days=[];states={'T1':{},'B1':{}};t1=b1=False
 for start,bs in sorted(groups.items()):
  if len(bs)!=24 or [b['ts'] for b in bs]!=list(range(start,start+D,H)):continue
  day=dict(ts=start,close=bs[-1]['close'],high=max(b['high'] for b in bs),low=min(b['low'] for b in bs))
  # Reject discontinuity across daily lookback, rather than accidentally compress missing days.
  prev=days[-50:]
  continuous=not prev or all(b['ts']-a['ts']==D for a,b in zip(prev,prev[1:])) and start-prev[-1]['ts']==D
  if len(days)>=49 and continuous:
   sma=sum(x['close'] for x in days[-49:]+[day])/50
   if day['close']>sma:t1=True
   elif day['close']<sma:t1=False
   states['T1'][start+D]=t1
  if len(days)>=20 and continuous:
   if day['close']>max(x['high'] for x in days[-20:]):b1=True
   elif day['close']<min(x['low'] for x in days[-10:]):b1=False
   states['B1'][start+D]=b1
  days.append(day)
 return states,days

def simulate(bs,name,states,funding,marks,slip=.0002,delay=0,save=None):
 cash=1000.;q=0.;trades=[];fundlog=[];curve=[];pending=None;invalid=None;stopped=None;failure=None
 peak=1000.;peak_t=bs[0]['ts'];maxdd=0.;maxuw=0.;mincash=1000.;desired=False
 sd=states.get(name,{});keys=sorted(sd)
 def state(t):
  if name=='HOLD':return True
  if name=='CASH':return False
  i=bisect_right(keys,t)-1
  return sd[keys[i]] if i>=0 else False
 def trade(t,enter,raw,reason):
  nonlocal cash,q
  fill=raw*(1+slip if enter else 1-slip)
  qty=floorq(.9*cash/(fill*(1+FEE))) if enter else q
  if enter and qty<.0001:return False
  fee=qty*fill*FEE
  cash+=(-qty*fill-fee) if enter else qty*fill-fee
  q=qty if enter else 0.
  trades.append(dict(ts=t,side='buy' if enter else 'sell',q=qty,raw=raw,fill=fill,fee=fee,slippage=qty*abs(fill-raw),reason=reason,cash=cash))
  return True
 for i,b in enumerate(bs):
  t=b['ts']
  if t in funding and q:
   mark=marks[t]['open'] if marks is not None else b['open'];paid=q*mark*funding[t];cash-=paid
   fundlog.append(dict(ts=t,q=q,rate=funding[t],mark=mark,paid=paid));mincash=min(mincash,cash)
   if cash < -1e-8:invalid='INVALID_NO_LEVERAGE';stopped=t;failure=cash;break
  # Inputs at t are only complete UTC days ending <=t. No current H1 close used.
  now=state(t)
  if i==0 or now!=desired:
   desired=now
   if desired!=bool(q):pending=(t+delay*H,desired)
  if pending and t>=pending[0]:
   want=pending[1];pending=None
   if want!=bool(q):
    if not trade(t,want,b['open'],'initial' if i<=delay else 'daily_state_change'):
     invalid='INVALID_MIN_QUANTITY';stopped=t;failure=cash;break
  assert cash>=-1e-7
  px=marks[t]['close'] if marks is not None else b['close'];eq=cash+q*px
  if eq>=peak:peak=eq;peak_t=t+H
  dd=1-eq/peak;maxdd=max(maxdd,dd);maxuw=max(maxuw,(t+H-peak_t)/H);mincash=min(mincash,cash)
  curve.append(dict(ts=t+H,equity=eq,cash_headroom=cash,q=q,mark=px,drawdown=dd,exposure=q*px/eq))
 if not invalid:
  if q:trade(bs[-1]['ts']+H,False,bs[-1]['close'],'terminal_liquidation')
  final=cash;maxdd=max(maxdd,1-final/peak)
 else:final=None
 fund=sum(x['paid'] for x in fundlog)
 independent=1000+sum((1 if x['side']=='sell' else -1)*x['q']*x['fill']-x['fee'] for x in trades)-fund
 assert abs(independent-cash)<1e-7
 if not invalid:assert abs(sum((1 if x['side']=='buy' else -1)*x['q'] for x in trades))<1e-8
 r=dict(name=name,status=invalid or 'COMPLETE',start=bs[0]['ts'],scheduled_end=bs[-1]['ts']+H,stopped_at=stopped,failure_headroom=failure,metrics_are_partial=bool(invalid),last_valued_at=curve[-1]['ts'] if curve else None,final_equity=final,pnl=final-1000 if final is not None else None,max_hourly_drawdown_pct=maxdd*100,max_underwater_hours=maxuw,unrecovered_at_end=(final if final is not None else curve[-1]['equity'])<peak,mean_exposure_pct=sum(x['exposure'] for x in curve)/len(curve)*100 if curve else None,fees=sum(x['fee'] for x in trades),slippage=sum(x['slippage'] for x in trades),funding=fund,turnover=sum(x['q']*x['raw'] for x in trades),entries=sum(x['side']=='buy' for x in trades),min_cash_headroom=mincash,ledger_error=independent-cash,hours=len(curve))
 if save:
  save.mkdir(parents=True,exist_ok=False)
  for k,v in [('summary',r),('trades',trades),('funding',fundlog),('curve',curve)]: (save/f'{k}.json').write_text(json.dumps(v,indent=2))
 return r,curve,trades,fundlog

def main():
 base=Path('/workspace/shared/btc-quant-research-20261010');paths=[base/'v2/data/ohlcv_1h.csv',base/'data/ohlcv_1h.csv',base/'data/btcusdt_usdt_futures_funding.csv',base/'data/btcusdt_usdt_futures_mark_1h_funding_window.csv']
 bars=load_csv(paths[0])+load_csv(paths[1]);rates={r['ts']:r['fundingRate'] for r in load_csv(paths[2])};marks={r['ts']:r for r in load_csv(paths[3])}
 assert len({b['ts'] for b in bars})==len(bars) and all(b['ts']-a['ts']==H for a,b in zip(bars,bars[1:]))
 assert len(rates)==270 and all(t in rates for t in range(min(rates),max(rates)+1,8*H)) and all(t in marks for t in range(min(marks),max(marks)+1,H))
 states,days=daily_states(bars)
 (P/'daily_states.json').write_text(json.dumps(states,indent=2))
 (P/'manifest.json').write_text(json.dumps(dict(created_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),protocol_sha256=hashlib.sha256((P/'protocol.json').read_bytes()).hexdigest(),engine_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),python=sys.executable,git_head=subprocess.check_output(['git','-C','/workspace/shared/btc-quant-worktree','rev-parse','HEAD'],text=True).strip(),data=[dict(path=str(p),sha256=hashlib.sha256(p.read_bytes()).hexdigest()) for p in paths],h1_count=len(bars),daily_count=len(days),actual_funding_count=len(rates),actual_mark_count=len(marks),old_seen_data=True,model='isolated fixed daily ledger, reuses audited accounting convention; not Freqtrade native engine'),indent=2))
 actual=[b for b in bars if min(rates)<=b['ts']<=max(rates)];records=[]
 names=['CASH','HOLD','T1','B1']
 for label,slip,delay in [('base',.0002,0),('slip5bp',.0005,0),('delay1h',.0002,1),('stress_both',.0005,1)]:
  for name in names:
   r,*_=simulate(actual,name,states,rates,marks,slip,delay,P/'results'/f'actual_{label}_{name}');r.update(window='actual',scenario=label);records.append(r)
 cutoff=int(datetime.datetime(2023,12,1,tzinfo=datetime.timezone.utc).timestamp()*1000)
 windows=[('full_after_warmup',[b for b in bars if b['ts']>=cutoff]),('period1',[b for b in bars[:8784] if b['ts']>=cutoff]),('period2',bars[8784:17544]),('period3',bars[17544:])]
 for w,bs in windows:
  for rate in [.0001,.0002]:
   fund={b['ts']:rate for b in bs if b['ts']%(8*H)==0};label=f'assumed_{int(rate*1e4)}bp'
   for name in names:
    r,*_=simulate(bs,name,states,fund,None,.0002,0,P/'results'/f'{w}_{label}_{name}');r.update(window=w,scenario=label);records.append(r)
 for r in records:
  bm=next(x for x in records if x['window']==r['window'] and x['scenario']==r['scenario'] and x['name']=='HOLD')
  r['relative_hold_usdt']=r['pnl']-bm['pnl'] if r['pnl'] is not None and bm['pnl'] is not None else None
 (P/'results.json').write_text(json.dumps(records,indent=2))
 for r in records:print(r['window'],r['scenario'],r['name'],r['status'],r['pnl'],r['relative_hold_usdt'],r['max_hourly_drawdown_pct'])
if __name__=='__main__':main()
