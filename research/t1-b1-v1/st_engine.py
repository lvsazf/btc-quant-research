"""Independent fully funded long-only perpetual research ledger. No network/account code."""
import math
from st_indicators import H,D,validate_bars
FEE=.0006;STEP=.0001; RISK_STRATEGIES={'A','B','DAILY_RISK'}

def floorq(value):return math.floor((value+1e-12)/STEP)*STEP

def simulate(bars,features,strategy,funding,marks=None,slip=.0002,delay=0, continuous=False, previous=None, boundary_only=False):
 validate_bars(bars)
 if strategy not in {'A','B','DAILY_RISK','T1','B1','HOLD','CASH'}:raise ValueError('unknown strategy')
 if delay not in (0,1):raise ValueError('unsupported fixed delay')
 if marks is not None and any(b['ts'] not in marks or not all(k in marks[b['ts']] for k in ('open','close')) for b in bars):raise ValueError('missing actual hourly mark')
 end=bars[-1]['ts']+H
 if marks is not None and end in funding and (end not in marks or 'open' not in marks[end]):raise ValueError('missing terminal settlement mark open')
 cash=1000.;q=0.;stop=None;pending=None;position=None
 orders=[];fundlog=[];curve=[];trades=[];peak=1000.;peak_t=bars[0]['ts'];maxdd=0.;maxuw=0;mincash=cash;status='COMPLETE';stopped=None;skipped=0
 boundary_processed=None
 if previous is not None:
  if not continuous:raise ValueError('Resume requires continuous mode')
  if previous['status']!='COMPLETE':raise ValueError('Cannot resume invalid ledger')
  cash=previous['cash'];q=previous['q'];stop=previous['stop'];pending=previous['pending'];position=previous['position']
  orders=list(previous['orders']);fundlog=list(previous['fundlog']);curve=list(previous['curve']);trades=list(previous['trades'])
  peak=previous['peak'];peak_t=previous['peak_t'];maxdd=previous['maxdd'];maxuw=previous['maxuw'];mincash=previous['mincash'];skipped=previous['skipped']
  boundary_processed=previous['boundary_processed']
  if bars[0]['ts']!=previous['next_bar_ts']:raise ValueError('Non-contiguous ledger continuation')
 risk_mode=strategy in RISK_STRATEGIES
 def charge(t,raw):
  nonlocal cash,status,stopped,mincash
  if q and t in funding:
   mark=marks[t]['open'] if marks is not None else raw
   paid=q*mark*funding[t];cash-=paid;position['funding']+=paid
   fundlog.append(dict(ts=t,q=q,mark=mark,rate=funding[t],paid=paid))
   mincash=min(mincash,cash)
   if cash < -1e-8:status='INVALID_NO_LEVERAGE';stopped=t
 def enter(t,raw,f,signal_time):
  nonlocal cash,q,stop,position,skipped,mincash
  fill=raw*(1+slip);initial_equity=cash
  if risk_mode:
   atr=f.get('atr')
   if atr is None or atr<=0:skipped+=1;return False
   stop=math.floor((raw-2*atr)*10+1e-9)/10
   if stop<=0 or stop>=raw:skipped+=1;stop=None;return False
   exitfill=stop*(1-slip)
   per_unit=fill-exitfill+FEE*(fill+exitfill)
   qty=floorq(min(.005*cash/per_unit,.9*cash/(fill*(1+FEE))))
   planned=qty*per_unit
  else:qty=floorq(.9*cash/(fill*(1+FEE)));planned=None;stop=None
  if qty<STEP-1e-12 or qty*fill<5:skipped+=1;stop=None;return False
  fee=qty*fill*FEE;cash-=qty*fill+fee;q=qty;mincash=min(mincash,cash)
  position=dict(entry_time=t,entry_signal_time=signal_time,entry_raw=raw,entry_fill=fill,entry_fee=fee,q=q,initial_equity=initial_equity,initial_stop=stop,planned_risk=planned,funding=0.)
  orders.append(dict(ts=t,side='buy',q=q,raw=raw,fill=fill,fee=fee,slippage=q*(fill-raw),reason='ENTRY',signal_time=signal_time,stop=stop,planned_risk=planned,cash=cash))
  if cash < -1e-7:raise AssertionError('entry borrowed')
  return True
 def exit_position(t,raw,reason):
  nonlocal cash,q,stop,position,mincash
  fill=raw*(1-slip);fee=q*fill*FEE;cash+=q*fill-fee;mincash=min(mincash,cash)
  orders.append(dict(ts=t,side='sell',q=q,raw=raw,fill=fill,fee=fee,slippage=q*(raw-fill),reason=reason,cash=cash))
  tr=dict(position);tr.update(exit_time=t,exit_raw=raw,exit_fill=fill,exit_fee=fee,reason=reason,terminal=reason=='TERMINAL',gross=q*(raw-position['entry_raw']),net=q*(fill-position['entry_fill'])-fee-position['entry_fee']-position['funding'])
  tr['exceeds_initial_risk']=risk_mode and -tr['net']>tr['planned_risk']+1e-7
  trades.append(tr);q=0.;stop=None;position=None
 def wants_exit(f):
  if not f.get('daily_long',False):return True
  if strategy=='A':return f.get('exit_a',False)
  if strategy=='B':return f.get('exit_b',False)
  return False
 def eligible_entry(f,t,i):
  if strategy=='CASH':return False
  if strategy=='HOLD':return i==0
  if strategy=='T1':return f.get('daily_long',False)
  if strategy=='B1':return f.get('b1',False)
  if not f.get('daily_long',False):return False
  if strategy=='DAILY_RISK':return t%D==0 or i==0
  return f.get('entry_'+strategy.lower(),False)
 for i,b in enumerate(bars):
  t=b['ts'];f=features.get(t,{})
  if boundary_processed!=t:
   charge(t,b['open'])
   if status!='COMPLETE':break
   exited=False
   if q and stop is not None and b['open']<=stop:
    exit_position(t,b['open'],'STOP_GAP');pending=None;exited=True
   # Actions already scheduled from an earlier completed bar take priority.
   if pending is not None and pending['due']<=t:
    p=pending;pending=None
    if p['action']=='exit' and q:exit_position(t,b['open'],'SIGNAL_EXIT');exited=True
    elif p['action']=='entry' and not q and not exited:
     if not risk_mode or not wants_exit(f):enter(t,b['open'],p['feature'],p['signal_time'])
     else:skipped+=1
   if pending is None and not exited:
    if q:
     do_exit=(not f.get('daily_long',False)) if strategy=='T1' else (not f.get('b1',False)) if strategy=='B1' else False if strategy=='HOLD' else wants_exit(f)
     if do_exit:
      if delay:pending=dict(action='exit',due=t+H,signal_time=t)
      else:exit_position(t,b['open'],'SIGNAL_EXIT');exited=True
    elif eligible_entry(f,t,i):
     if delay:pending=dict(action='entry',due=t+H,signal_time=t,feature=dict(f))
     else:enter(t,b['open'],f,t)
  if boundary_only and i==len(bars)-1:
   boundary_processed=t
   break
  boundary_processed=None
  if q and stop is not None and b['low']<=stop:
   exit_position(t+H-1,stop,'STOP_INTRABAR');pending=None
  px=marks[t]['close'] if marks is not None else b['close'];eq=cash+q*px
  if eq>=peak:peak=eq;peak_t=t+H
  dd=1-eq/peak;maxdd=max(maxdd,dd);maxuw=max(maxuw,(t+H-peak_t)/H);mincash=min(mincash,cash)
  curve.append(dict(ts=t+H,equity=eq,cash=cash,q=q,mark=px,drawdown=dd,exposure=q*px/eq if eq>0 else None))
 if status=='COMPLETE' and not continuous:
  charge(end,bars[-1]['close'])
  if status=='COMPLETE':
   if q:exit_position(end,bars[-1]['close'],'TERMINAL')
   final=cash;maxdd=max(maxdd,1-final/peak)
  else:final=None
 else:final=None
 if continuous and status=='COMPLETE':
  px=marks[bars[-1]['ts']]['open' if boundary_only else 'close'] if marks is not None else bars[-1]['open' if boundary_only else 'close']
  final=cash+q*px
 independent=1000+sum((1 if x['side']=='sell' else -1)*x['q']*x['fill']-x['fee'] for x in orders)-sum(x['paid'] for x in fundlog)
 if abs(independent-cash)>1e-7:raise AssertionError('cashflow mismatch')
 if not continuous and final is not None and (abs(q)>1e-9 or abs(final-1000-sum(x['net'] for x in trades))>1e-7):raise AssertionError('closed trade reconciliation')
 ordinary=[x for x in trades if not x['terminal']];wins=sum(x['net']>0 for x in ordinary);profit=sum(max(0,x['net']) for x in ordinary);loss=-sum(min(0,x['net']) for x in ordinary)
 r=dict(name=strategy,status=status,start=bars[0]['ts'],end=end,hours=len(curve),final_equity=final,pnl=None if final is None else final-1000,return_pct=None if final is None else (final/1000-1)*100,max_drawdown_pct=100*maxdd,max_underwater_hours=maxuw,unrecovered_at_end=(final if final is not None else curve[-1]['equity'])<peak,entries=sum(x['side']=='buy' for x in orders),completed_nonterminal_trades=len(ordinary),terminal_trades=len(trades)-len(ordinary),win_rate=None if not ordinary else wins/len(ordinary),profit_factor=None if not loss else profit/loss,fees=sum(x['fee'] for x in orders),slippage=sum(x['slippage'] for x in orders),funding=sum(x['paid'] for x in fundlog),turnover=sum(x['q']*x['raw'] for x in orders),mean_exposure_pct=sum(x['exposure'] for x in curve)/len(curve)*100 if curve else 0,minimum_cash_headroom=mincash,largest_trade_loss=max([-x['net'] for x in trades]+[0]),risk_budget_breaches=sum(x['exceeds_initial_risk'] for x in trades),skipped_entries=skipped,ledger_error=independent-cash,stopped_at=stopped)
 if continuous:
  state=dict(status=status,cash=cash,q=q,stop=stop,pending=pending,position=position,orders=orders,fundlog=fundlog,curve=curve,trades=trades,peak=peak,peak_t=peak_t,maxdd=maxdd,maxuw=maxuw,mincash=mincash,skipped=skipped,boundary_processed=boundary_processed,next_bar_ts=bars[-1]['ts'] if boundary_only else end)
  r['terminal_liquidation']=False;r['end']=bars[-1]['ts'] if boundary_only else end
  return r,curve,orders,fundlog,trades,state
 return r,curve,orders,fundlog,trades
