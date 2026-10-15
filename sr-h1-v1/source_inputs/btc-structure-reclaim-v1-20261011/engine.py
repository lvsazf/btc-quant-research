"""Causal Decimal BTC 4H-trend/H1-reclaim simulation; no live operations.
All signal inputs are completed bars. Current bar high/low are used only
AFTER admission, for interval-ambiguous exits with conservative SL priority.
"""
from decimal import Decimal, ROUND_FLOOR, ROUND_CEILING
from bisect import bisect_right
H=3600000
D=lambda x: x if isinstance(x,Decimal) else Decimal(str(x))
TICK=D('.1');STEP=D('.0001');FEE=D('.0006');SLIP=D('.0002');RESERVE=D('.0001');FUND=D('.0001')

def floorq(x): return (x/STEP).to_integral_value(rounding=ROUND_FLOOR)*STEP

def tick(x,up): return (x/TICK).to_integral_value(rounding=ROUND_CEILING if up else ROUND_FLOOR)*TICK

def fill_price(raw,d,entry,slip=SLIP):
 raw=D(raw);side=d if entry else -d
 return tick(raw*(1+side*D(slip))+side,side>0)

def funding_times(entry,exit):
 first=((entry//(8*H))+1)*8*H
 return list(range(first,exit+1,8*H))

def trend_series(a):
 """UTC complete four-hour groups. A later group's data never revises a prior row."""
 groups={}
 for b in a: groups.setdefault((b['ts']//(4*H))*4*H,[]).append(b)
 out=[];ema=None;closes=[]
 for t,bars in sorted(groups.items()):
  if [b['ts'] for b in bars]!=[t+k*H for k in range(4)]:continue
  close=bars[-1]['close'];closes.append(close);prev=ema
  if len(closes)==20:ema=sum(closes,D(0))/20
  elif len(closes)>20:ema=close*D(2)/21+ema*D(19)/21
  direction=None
  if len(closes)>=100 and prev is not None:
   direction=1 if close>ema and ema>prev else -1 if close<ema and ema<prev else 0
  out.append(dict(open_time=t,close_time=t+4*H,close=close,ema=ema,previous_ema=prev,complete_count=len(closes),direction=direction))
 return out

def trend_at(series,t):
 i=bisect_right(series,t,key=lambda x:x['close_time'])-1
 return series[i] if i>=0 else dict(close_time=None,complete_count=0,ema=None,previous_ema=None,direction=None)

def contiguous(a): return all(y['ts']-x['ts']==H for x,y in zip(a,a[1:]))

def signal_at(a,i,series=None):
 if i<1:return None
 b0,b1=a[i-1:i+1];t0=b1['ts']+H
 if b0['ts']+H!=b1['ts']:return None
 trend=trend_at(trend_series(a[:i+1]) if series is None else series,t0);d=trend['direction']
 if d not in (1,-1):return None
 if d==1:
  if not (b0['close']<b0['open'] and b1['close']>b0['high'] and b1['low']>b0['low']):return None
 else:
  if not (b0['close']>b0['open'] and b1['close']<b0['low'] and b1['high']<b0['high']):return None
 boundary=b0['high'] if d==1 else b0['low'];sl=b0['low']-TICK if d==1 else b0['high']+TICK
 swings=[];kind='swing_high' if d==1 else 'swing_low';key='high' if d==1 else 'low'
 for k in range(max(2,i-71),i-1):
  center=a[k];five=a[k-2:k+3]
  if center['ts']<t0-72*H or center['ts']>=b0['ts'] or five[-1]['ts']+H>t0 or not contiguous(five):continue
  price=center[key];neighbors=five[:2]+five[3:]
  if all(d*(price-b[key])>0 for b in neighbors) and d*(price-b1['close'])>0:
   swings.append(dict(kind=kind,price=price,center_time=center['ts'],confirmed_time=five[-1]['ts']+H))
 target=min(swings,key=lambda s:(d*s['price'],-s['center_time'])) if swings else None
 return dict(t0=t0,d=d,boundary=boundary,p0=b1['close'],sl=sl,tp=target['price'] if target else None,target_source=target,eligible_target_structures=swings,b0_time=b0['ts'],b1_time=b1['ts'],trend=trend)

def candidate_status(c,t,completed,quote,trend_direction):
 for b in completed:
  if b['ts']<c['t0'] or b['ts']+H>t:continue
  if b['low']<=c['sl'] if c['d']==1 else b['high']>=c['sl']:return 'cancel_sl'
  if c['d']*(b['close']-c['boundary'])<=0:return 'cancel_close'
  if b['high']>=c['tp'] if c['d']==1 else b['low']<=c['tp']:return 'cancel_tp'
 if trend_direction!=c['d']:return 'cancel_trend'
 if quote is not None:
  if c['d']*(quote-c['sl'])<=0:return 'cancel_sl_quote'
  if c['d']*(quote-c['tp'])>=0:return 'cancel_tp_quote'
 if t>=c['t0']+3*H:return 'expired'
 if quote is not None and c['d']*(quote-c['boundary'])<=0:return 'quote_inside_boundary'
 return 'eligible'

def plan_entry(c,E,t,equity,slip=SLIP):
 E=D(E);ef=fill_price(E,c['d'],True,slip);sf=fill_price(c['sl'],c['d'],False,slip);tf=fill_price(c['tp'],c['d'],False,slip)
 pfund=E*FUND*len(funding_times(t,t+6*H));reserve=ef*RESERVE
 loss=c['d']*(ef-sf)+FEE*(ef+sf)+reserve+pfund
 base=dict(entry_fill=ef,stop_fill=sf,target_fill=tf,planned_loss_per_btc=loss,planned_funding_per_btc=pfund,reserve_per_btc=reserve)
 if c['d']*(c['tp']-E)<=0:return dict(**base,accepted=False,reason='target_exhausted')
 if c['d']*(E-c['sl'])<=0 or loss<=0:return dict(**base,accepted=False,reason='invalid_stop')
 cap=D(equity)/(ef/2+ef*FEE+D('.005')*ef+loss)
 q=floorq(max(D(0),min(D(20)/loss,D(1000)/ef,cap)))
 base.update(q=q,planned_risk=q*loss,notional=q*ef,margin_capacity_q=cap)
 if q<STEP or q*min(ef,sf,tf)<5:return dict(**base,accepted=False,reason='minimum_order')
 reward=q*(c['d']*(tf-ef)-FEE*(ef+tf)-reserve-pfund);ratio=reward/(q*loss)
 base.update(planned_reward=reward,planned_ratio=ratio)
 if ratio<1:return dict(**base,accepted=False,reason='cost_ratio')
 return dict(**base,accepted=True,reason='accepted')

def exit_bar(p,b,slip=SLIP):
 if not p['remaining']:return []
 d=p['d'];t=b['ts']
 def take(price,reason,at_open=False):
  x=dict(time=t if at_open else t+H-1,time_lower=t,time_upper=t if at_open else t+H,time_precision='exact_open' if at_open else 'hour_interval',funding_through=t,quantity=p['remaining'],raw_price=price,fill=fill_price(price,d,False,slip),reason=reason)
  p['remaining']=D(0);return [x]
 if d*(b['open']-p['sl'])<=0:return take(b['open'],'GAP_SL',True)
 if t>=p['entry_time']+6*H:return take(b['open'],'TIMEOUT',True)
 if b['low']<=p['sl'] if d==1 else b['high']>=p['sl']:return take(p['sl'],'SL')
 if b['high']>=p['tp'] if d==1 else b['low']<=p['tp']:return take(p['tp'],'TP',d*(b['open']-p['tp'])>=0)
 return []

def trade_account(p,slip=SLIP):
 raw=sum(p['d']*(x['raw_price']-p['entry_quote'])*x['quantity'] for x in p['exits'])
 execution=sum(p['d']*((p['entry_fill']-p['entry_quote'])+(x['raw_price']-x['fill']))*x['quantity'] for x in p['exits'])
 entryfee=p['q']*p['entry_fill']*FEE;exitfee=sum(x['quantity']*x['fill']*FEE for x in p['exits'])
 funding=sum(x['quantity']*p['entry_quote']*FUND*len(funding_times(p['entry_time'],x['funding_through'])) for x in p['exits'])
 reserve=p['q']*p['entry_fill']*RESERVE;cost=execution+entryfee+exitfee+funding+reserve
 slippage=sum((p['entry_quote']+x['raw_price'])*D(slip)*x['quantity'] for x in p['exits']);spread=D(2)*sum(x['quantity'] for x in p['exits'])
 return dict(raw_gross=raw,execution_pressure=execution,slippage_cost=slippage,spread_stress_cost=spread,tick_rounding_cost=execution-slippage-spread,entry_fee=entryfee,exit_fee=exitfee,funding=funding,reserve=reserve,total_cost=cost,net=raw-cost)

def simulate(a,start,end,delay=0,initial_equity=D(1000),slip=SLIP):
 """Causal single-candidate/position simulation, final-only horizon censoring."""
 if delay not in (0,1,2):raise ValueError('Only prespecified delay 0/1/2')
 a=[b for b in a if b['ts']+H<=end]
 if not a:return dict(candidates=[],trades=[],censored=[],raw_signals=[],events=[],equity=D(initial_equity),provisional_equity=D(initial_equity),equity_curve=[])
 if not contiguous(a):raise ValueError('Data insufficient: gap, duplicate or unordered hourly data')
 if any(b['ts']%H or not (b['low']<=min(b['open'],b['close'])<=max(b['open'],b['close'])<=b['high']) for b in a):raise ValueError('Invalid hourly OHLC')
 series=trend_series(a);idx={b['ts']:i for i,b in enumerate(a)}
 events=[];candidates=[];observed=[];raw_signals=[];curve=[]
 equity=D(initial_equity);active=None;position=None;serial=0;last_exit=-1
 def log(t,event,**kw):events.append(dict(time=t,event=event,**kw))
 def finish_candidate(c,outcome,t):c['outcome']=outcome;c['resolved_time']=t;log(t,outcome,candidate_id=c['id'])
 times=[b['ts'] for b in a if start<=b['ts']<end];terminal=min(end,a[-1]['ts']+H)
 if terminal>=start:times.append(terminal)
 for t in times:
  i=idx.get(t);bar=a[i] if i is not None else None
  previous=a[i-1] if i is not None and i>0 else a[-1] if t==terminal else None
  trend=trend_at(series,t)
  if active:
   status=candidate_status(active,t,[previous] if previous else [],bar['open'] if bar else None,trend['direction'])
   if status.startswith('cancel_') or status=='expired':finish_candidate(active,status,t);active=None
  sig=signal_at(a,i-1 if i is not None else len(a)-1,series) if previous and start<=t<end else None
  if sig:
   sig=dict(sig,id=f'signal_{t}',time=t);raw_signals.append(sig)
   if sig['tp'] is None:sig['disposition']='no_target';log(t,'signal_no_target',signal_id=sig['id'])
   elif active or position or t<=last_exit:
    sig['disposition']='suppressed_active';log(t,'signal_suppressed',reason='active_candidate_or_position_or_same_exit_time',signal_id=sig['id'])
   else:
    serial+=1;sig['disposition']='candidate';active=dict(sig,id=f'candidate_{serial}',signal_id=sig['id'],created_time=t,attempts=[],outcome='pending');candidates.append(active);log(t,'candidate_created',candidate_id=active['id'],d=active['d'])
  if active and bar:
   quote=bar['open'];status=candidate_status(active,t,[],quote,trend['direction'])
   if status.startswith('cancel_') or status=='expired':reason=status
   elif t<active['t0']+delay*H:reason='delay_wait'
   elif status!='eligible':reason=status
   else:reason=None
   plan=plan_entry(active,quote,t,equity,slip) if reason is None else None
   if plan and not plan['accepted']:reason=plan['reason']
   active['attempts'].append(dict(time=t,quote=quote,reason=reason or 'accepted',plan=plan));log(t,'entry_attempt',candidate_id=active['id'],reason=reason or 'accepted',quote=quote)
   if reason and (reason.startswith('cancel_') or reason=='expired'):finish_candidate(active,reason,t);active=None
   if reason is None:
    active['outcome']='entered';active['entry_time']=t
    position=dict(active,entry_time=t,entry_quote=quote,entry_fill=plan['entry_fill'],q=plan['q'],remaining=plan['q'],planned=plan,exits=[],equity_before=equity,slippage=D(slip))
    equity-=plan['q']*plan['entry_fill']*(FEE+RESERVE);log(t,'entry',candidate_id=active['id'],quote=quote,fill=plan['entry_fill'],quantity=plan['q'],planned_risk=plan['planned_risk'],notional=plan['notional']);active=None
  if position and bar:
   for x in exit_bar(position,bar,slip):
    fund=x['quantity']*position['entry_quote']*FUND*len(funding_times(position['entry_time'],x['funding_through']))
    equity+=position['d']*(x['fill']-position['entry_fill'])*x['quantity']-x['fill']*x['quantity']*FEE-fund
    position['exits'].append(x);log(x['time'],'exit',candidate_id=position['id'],**{k:v for k,v in x.items() if k!='time'})
   if not position['remaining']:
    position.update(trade_account(position,slip));position['exit_time']=position['exits'][-1]['time'];position['exit_path']=position['exits'][-1]['reason'];position['equity_after']=equity
    observed.append(position);last_exit=position['exit_time'];position=None
  if bar:
   mark=equity
   if position:
    q=position['remaining'];mf=fill_price(bar['close'],position['d'],False,slip)
    mark+=q*position['d']*(mf-position['entry_fill'])-q*mf*FEE-q*position['entry_quote']*FUND*len(funding_times(position['entry_time'],t))
   curve.append(dict(time=t+H,equity=mark))
 completed=[];censored=[];last_open=a[-1]['ts']
 for p in observed:
  if p['entry_time']+6*H>last_open:p['censor_reason']='missing_full_exit_horizon';censored.append(p)
  else:completed.append(p)
 if position:position['censor_reason']='position_unresolved_at_cutoff';censored.append(position)
 ids={p['id'] for p in censored}
 for c in candidates:
  if c['id'] in ids:c['outcome']='censored_position';log(terminal,'censored_position',candidate_id=c['id'],reason='missing_full_exit_horizon')
  elif c['outcome']=='entered':c['outcome']='completed'
 if active:finish_candidate(active,'censored_candidate',terminal)
 reported=D(initial_equity)+sum((p['net'] for p in completed),D(0))
 return dict(candidates=candidates,trades=completed,censored=censored,raw_signals=raw_signals,events=sorted(events,key=lambda x:x['time']),equity=reported,provisional_equity=equity,equity_curve=curve,last_observed_open=last_open)
