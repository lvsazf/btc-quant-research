"""Frozen ST-H1-LO-v1 signals, copied verbatim Supertrend function from approved research source."""
from st_indicators import H,validate_bars,build_features
def supertrend(bars,n=10,multiplier=3.):
 validate_bars(bars);out=[];trs=[];atr=None;upper=lower=None;up=False
 for i,b in enumerate(bars):
  prevclose=bars[i-1]['close'] if i else b['close']
  tr=max(b['high']-b['low'],abs(b['high']-prevclose),abs(b['low']-prevclose));trs.append(tr)
  previous_up=up
  if i==n-1:atr=sum(trs)/n
  elif i>=n:atr=(atr*(n-1)+tr)/n
  if atr is not None:
   bu=(b['high']+b['low'])/2+multiplier*atr;bl=(b['high']+b['low'])/2-multiplier*atr
   if upper is None:upper,lower,up=bu,bl,False
   else:
    upper=bu if bu<upper or prevclose>upper else upper
    lower=bl if bl>lower or prevclose<lower else lower
    up=(b['close']>=lower) if previous_up else (b['close']>upper)
  out.append(dict(atr10=atr,upper=upper,lower=lower,up=up,entry=up and not previous_up,exit=previous_up and not up))
 return out

def features(bars):
 base=build_features(bars);st=supertrend(bars)
 return {f['close_time']:dict(atr=f['atr'],daily_long=True,entry_a=s['entry'],exit_a=s['exit'],close=b['close'],atr10=s['atr10'],upper=s['upper'],lower=s['lower'],up=s['up']) for b,f,s in zip(bars,base,st)}
