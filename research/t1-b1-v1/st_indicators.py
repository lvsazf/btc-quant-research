"""Causal features keyed by information availability, never by the day's label."""
import math
H=3600000; D=24*H

def validate_bars(bars):
 if not bars:raise ValueError('empty bars')
 for i,b in enumerate(bars):
  if b['ts']%H:raise ValueError('non-hour boundary')
  if i and b['ts']-bars[i-1]['ts']!=H:raise ValueError('non-contiguous or duplicated hours')
  if not all(math.isfinite(b[k]) and b[k]>0 for k in ('open','high','low','close')):raise ValueError('invalid finite positive OHLC')
  if b['high']<max(b['open'],b['close'],b['low']) or b['low']>min(b['open'],b['close'],b['high']):raise ValueError('invalid OHLC bounds')

def build_features(bars):
 validate_bars(bars)
 out=[];days=[];day=[];daily=False;b1=False;basis=None;sma50=None;atr=None;trs=[]
 for i,b in enumerate(bars):
  t=b['ts']; end=t+H
  if day and day[0]['ts']//D!=t//D:day=[]
  day.append(b)
  updated=False
  if end%D==0:
   if len(day)==24 and day[0]['ts']==end-D:
    d={'ts':end-D,'close':b['close'],'high':max(z['high'] for z in day),'low':min(z['low'] for z in day)}
    basis=end;updated=True
    if len(days)>=49:
     sma50=sum(x['close'] for x in days[-49:]+[d])/50
     if d['close']>sma50:daily=True
     elif d['close']<sma50:daily=False
    if len(days)>=20:
     if d['close']>max(z['high'] for z in days[-20:]):b1=True
     elif d['close']<min(z['low'] for z in days[-10:]):b1=False
    days.append(d)
   day=[]
  tr=b['high']-b['low'] if i==0 else max(b['high']-b['low'],abs(b['high']-bars[i-1]['close']),abs(b['low']-bars[i-1]['close']))
  trs.append(tr)
  if i==13:atr=sum(trs)/14
  elif i>13:atr=(atr*13+tr)/14
  ma=sum(z['close'] for z in bars[i-19:i+1])/20 if i>=19 else None
  ph=max(z['high'] for z in bars[i-24:i]) if i>=24 else None
  pl=min(z['low'] for z in bars[i-12:i]) if i>=12 else None
  raw_a=ph is not None and b['close']>ph
  raw_b=ma is not None and i>0 and out[-1]['ma20'] is not None and b['close']>ma and bars[i-1]['close']<=out[-1]['ma20']
  out.append(dict(ts=t,close_time=end,close=b['close'],daily_long=daily,b1=b1,daily_updated=updated,daily_basis_close=basis,sma50=sma50,ma20=ma,atr=atr,prior24_high=ph,prior12_low=pl,raw_entry_a=raw_a,raw_entry_b=raw_b,entry_a=daily and raw_a,entry_b=daily and raw_b,exit_a=pl is not None and b['close']<pl,exit_b=ma is not None and b['close']<ma))
 return out
