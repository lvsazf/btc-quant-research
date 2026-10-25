"""Pure presentation of verified research output; never creates an order or rule."""
import copy
from datetime import datetime, timezone

def utc(ms):
 return None if ms is None else datetime.fromtimestamp(ms/1000,timezone.utc).isoformat()

def order_time(order):
 t=order.get('ts');intrabar=order.get('reason')=='STOP_INTRABAR'
 start=(t//3600000)*3600000 if intrabar and t is not None else None
 return dict(ledger_time_utc=utc(t),execution_time_utc=None if intrabar else utc(t),time_semantics='Closed H1 stop reconstruction: exact intrabar trigger time unknown; ledger timestamp is not execution time' if intrabar else 'Research open-price accounting time, not an actual account fill timestamp',possible_execution_interval_start_utc=utc(start),possible_execution_interval_end_utc=utc(start+3600000) if start is not None else None)

def describe_execution(name, signal, checkpoint=None):
 st=name=='ST'; event=signal.get('event');target=signal.get('desired_state') if st else signal.get('target_state')
 previous=signal.get('previous_state') if st else signal.get('previous_target_state')
 orders=copy.deepcopy(signal.get('incremental_orders',[])) if st else []
 if event in ('INITIALIZED','INITIALIZED_LONG','INITIALIZED_CASH'):
  action='INITIALIZE_RESEARCH_POSITION';reason='Research state initialization only; historical entries are not a new entry recommendation.'
 elif event=='WAIT' and target==previous and target in ('LONG','CASH'):
  action='MAINTAIN_'+target;reason='No new research entry or exit in this observation; existing target continues.'
 elif event=='ENTER_LONG_TRANSITION' or (st and event=='ENTER' and len(orders)==1 and orders[0].get('side')=='buy'):
  action='ENTER_LONG';reason='New research entry event; any price/quantity below belongs to the research ledger, not an account fill.'
 elif event=='EXIT_LONG_TRANSITION' or (st and event=='EXIT' and len(orders)==1 and orders[0].get('side')=='sell'):
  action='EXIT_LONG';reason='New research exit event; not confirmation of an account close.'
 elif st and event=='TRANSITIONS' and orders:
  action='MULTIPLE_RESEARCH_EVENTS';reason='Read every ordered event, including stops; final target alone does not describe this interval.'
 else:
  action='UNKNOWN';reason='Unrecognized or incomplete state/event combination; do not substitute WAIT.'
 initialized=action=='INITIALIZE_RESEARCH_POSITION'
 # Defensive: initialization never republishes historical orders as new orders.
 if initialized:orders=[]
 order_details=[dict(source='run/st_signal.json:incremental_orders',sequence=i+1,side=o.get('side'),reason=o.get('reason'),**order_time(o),signal_time_utc=utc(o.get('signal_time')),raw_price=o.get('raw'),research_execution_price=o.get('fill'),quantity=o.get('q'),stoploss=o.get('stop'),fee=o.get('fee'),slippage=o.get('slippage'),planned_risk_usdt=o.get('planned_risk'),not_account_fill=True) for i,o in enumerate(orders)]
 position=None;missing=[]
 if st:
  ledger=(checkpoint or {}).get('ledger')
  if ledger is None:missing.append('Verified st_checkpoint position provenance unavailable; no entry price inferred from ticker.')
  else:
   if ledger['q']!=signal.get('research_quantity') or ledger['stop']!=signal.get('research_stop'):raise ValueError('ST display checkpoint/signal mismatch')
   p=ledger.get('position')
   if p and ledger['q']:
    position=dict(source='run/st_checkpoint.json:ledger.position',origin='HISTORICAL_RECONSTRUCTION' if initialized else 'CONTINUOUS_RESEARCH_LEDGER',entry_time_utc=utc(p.get('entry_time')),signal_time_utc=utc(p.get('entry_signal_time')),entry_raw_price=p.get('entry_raw'),entry_price=p.get('entry_fill'),quantity=p.get('q'),stoploss=ledger['stop'],initial_stoploss=p.get('initial_stop'),planned_risk_usdt=p.get('planned_risk'),not_current_entry_recommendation=True)
  exit_rule='Fixed entry 2 ATR14 protective stop or closed H1 Supertrend down flip, following frozen ledger execution order; after stop wait for a new up flip.'
 else:
  missing=['Current T1/B1 signal-only path does not calculate research entry price, quantity or position provenance; no structured stop or price target is defined.']
  exit_rule='Completed UTC daily close below SMA50; equality preserves state.' if name=='T1' else 'Completed UTC daily close below prior 10 complete days low, excluding the signal day; otherwise preserve state.'
 return dict(scope='INDEPENDENT_RESEARCH_NOT_ACCOUNT_EXECUTION',action=action,reason=reason,event=event,previous_state=previous,target_state=target,new_entry=(action=='ENTER_LONG' or any(o.get('side')=='buy' for o in orders)),new_orders=orders,new_order_details=order_details,signal_available_utc=signal.get('signal_available_utc'),quantity=signal.get('research_quantity') if st else None,stoploss=signal.get('research_stop') if st else None,position=position,exit_rule=exit_rule,fixed_profit_target=None,stop_execution='Closed H1 reconstruction, not a hosted realtime stop' if st else 'No strategy protective stop defined',missing_research_fields=missing,manual_execution=dict(authorized=False,entry_deadline=None,allowed_price_deviation=None,account_quantity=None,leverage_margin_constraints=None,missing=['Entry validity duration and allowed price deviation not defined','Account execution sizing, fees and leverage/margin constraints not approved'],account_read_required_for_research=False),risk_basis='ST frozen research 0.5% initial planned risk; not the old 20 USDT budget and not a guaranteed maximum loss' if st else 'Frozen research assumptions only; no 20 USDT stop guarantee')
