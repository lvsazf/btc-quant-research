"""Describe official IStrategy dataframe outputs; do not infer executable orders."""
import pandas as pd

def describe_signal(frame,name):
 row=frame.iloc[-1];previous=frame.iloc[-2] if len(frame)>1 else None
 ready=bool(row.research_ready);long=bool(row.research_long_at_close)
 prior_ready=previous is not None and bool(previous.research_ready)
 prior=bool(previous.research_long_at_close) if prior_ready else None
 if not ready:event='INSUFFICIENT_DATA'
 elif not prior_ready:event='INITIALIZED_LONG' if long else 'INITIALIZED_CASH'
 elif long!=prior:event='ENTER_LONG_TRANSITION' if long else 'EXIT_LONG_TRANSITION'
 else:event='WAIT'
 def clean(v):return None if pd.isna(v) else float(v)
 return dict(strategy=name,machine_source='Freqtrade StrategyResolver + IStrategy.advise_indicators/advise_entry/advise_exit',bar_open_utc=row.date.isoformat(),signal_available_utc=(row.date+pd.Timedelta(hours=1)).isoformat(),basis_daily_close_ms=clean(row.research_basis_close_ms),target_state=('LONG' if long else 'CASH') if ready else 'UNKNOWN',previous_target_state=('LONG' if prior else 'CASH') if prior_ready else 'UNKNOWN',event=event,native_flags={'enter_long':int(row.enter_long),'exit_long':int(row.exit_long),'enter_short':int(row.enter_short),'exit_short':int(row.exit_short)},tags={'entry':str(row.enter_tag) if int(row.enter_long) else None,'exit':str(row.exit_tag) if int(row.exit_long) else None},indicators={k:clean(row[k]) for k in ['research_daily_close','research_sma50','research_prior20_high','research_prior10_low']},execution={'account_position':'UNKNOWN_NOT_READ','quantity':None,'entry_price':None,'stoploss':None,'target':None,'entry_deadline':None,'reason':'No adopted execution contract; native flags are not orders. Historical sizing is a research assumption, not account quantity.'},adopted=False,orders_enabled=False,formal_A_signal=False)
