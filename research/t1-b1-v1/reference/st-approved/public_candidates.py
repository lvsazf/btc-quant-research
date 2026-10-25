"""Two fixed public signal adaptations. No account/network/production code.
The old engine's daily_long=True is an adapter switch, NOT a daily trend claim.
"""
import sys
from pathlib import Path
REFERENCE=Path(__file__).resolve().parent/'reference'/'original'
sys.dont_write_bytecode=True
sys.path.insert(0,str(REFERENCE))
from indicators import H, validate_bars, build_features
from engine import simulate
NAMES=('ST-H1-LO-v1','R2-H1-LO-v1')

def rsi_wilder(close,n=2):
 out=[None]*len(close)
 if len(close)<=n:return out
 gains=[max(close[i]-close[i-1],0.) for i in range(1,len(close))]
 losses=[max(close[i-1]-close[i],0.) for i in range(1,len(close))]
 gain=sum(gains[:n])/n;loss=sum(losses[:n])/n
 def value():return 50. if gain==loss==0 else 100. if loss==0 else 100-100/(1+gain/loss)
 out[n]=value()
 for i in range(n+1,len(close)):
  gain=(gain*(n-1)+gains[i-1])/n;loss=(loss*(n-1)+losses[i-1])/n;out[i]=value()
 return out

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
 base=build_features(bars);st=supertrend(bars);closes=[b['close'] for b in bars];rs=rsi_wilder(closes);out={}
 for i,(b,f,s) in enumerate(zip(bars,base,st)):
  sma=sum(closes[i-199:i+1])/200 if i>=199 else None
  entry=sma is not None and b['close']>sma and i>=4 and rs[i-2] is not None and rs[i-2]<65 and rs[i-1]<rs[i-2] and rs[i]<rs[i-1]
  out[f['close_time']]=dict(ts=b['ts'],close_time=f['close_time'],close=b['close'],atr=f['atr'],daily_long=True,adapter_daily_filter_disabled=True,st_entry=s['entry'],st_exit=s['exit'],st_upper=s['upper'],st_lower=s['lower'],st_up=s['up'],atr10=s['atr10'],rsi2=rs[i],sma200=sma,r2_entry=bool(entry),r2_exit=rs[i] is not None and rs[i]>75)
 return out

def simulate_public(bars,fmap,name,funding,marks=None,slip=.0002,delay=0):
 if name not in NAMES:raise ValueError('unknown public candidate')
 prefix='st' if name==NAMES[0] else 'r2'
 # No legacy A signal/exit survives: only ATR14 and constant adapter gate.
 adapted={t:dict(atr=f['atr'],daily_long=True,entry_a=f[prefix+'_entry'],exit_a=f[prefix+'_exit']) for t,f in fmap.items()}
 result=simulate(bars,adapted,'A',funding,marks,slip,delay)
 result[0]['name']=name
 return result
