"""Native Freqtrade signal interface ONLY. Account/live/dry-run trading blocked.
Use research/t1-b1-v1/run_research.py for audited costs and ledger semantics.
Native default Backtesting execution/costs are NOT certified equivalent.
"""
from pathlib import Path
from bisect import bisect_right
import sys
from freqtrade.strategy import IStrategy
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from rules import daily_states,validate_bars,H,VERSION

class _FrozenDailyResearch(IStrategy):
    INTERFACE_VERSION=3
    timeframe='1h'
    startup_candle_count=1224
    can_short=False
    process_only_new_candles=True
    minimal_roi={}
    stoploss=-.99  # Framework-required placeholder; NOT a frozen-rule stop.
    trailing_stop=False
    use_exit_signal=True
    position_adjustment_enable=False
    order_types={'entry':'market','exit':'market','stoploss':'market','stoploss_on_exchange':False}
    research_version=VERSION
    rule_name='INVALID'
    def _guard(self):
        mode=self.config.get('runmode');mode=getattr(mode,'value',mode)
        if self.config.get('t1b1_research_only') is not True or mode!='backtest':
            raise RuntimeError('Research only: live/dry-run/account execution prohibited')
    def bot_start(self,**kwargs):self._guard()
    def populate_indicators(self,dataframe,metadata):
        self._guard()
        if metadata.get('pair')!='BTC/USDT:USDT':raise ValueError('Frozen instrument mismatch')
        bars=[dict(ts=int(r.date.timestamp()*1000),open=float(r.open),high=float(r.high),low=float(r.low),close=float(r.close)) for r in dataframe.itertuples()]
        validate_bars(bars)
        states,days=daily_states(bars);s=states[self.rule_name];keys=sorted(s)
        desired=[];ready=[]
        for b in bars:
            i=bisect_right(keys,b['ts']+H)-1;ready.append(i>=0);desired.append(bool(s[keys[i]]) if i>=0 else False)
        # Explain the same frozen inputs; these fields do not alter signals.
        details={}
        for j,day in enumerate(days):
            details[day['ts']+24*H]={
                'research_daily_close':day['close'],
                'research_sma50':sum(x['close'] for x in days[j-49:j+1])/50 if j>=49 else None,
                'research_prior20_high':max(x['high'] for x in days[j-20:j]) if j>=20 else None,
                'research_prior10_low':min(x['low'] for x in days[j-10:j]) if j>=10 else None}
        for field in ['research_daily_close','research_sma50','research_prior20_high','research_prior10_low']:
            dataframe[field]=[details[keys[bisect_right(keys,b['ts']+H)-1]][field] if bisect_right(keys,b['ts']+H)>0 else None for b in bars]
        dataframe['research_basis_close_ms']=[keys[bisect_right(keys,b['ts']+H)-1] if bisect_right(keys,b['ts']+H)>0 else None for b in bars]
        dataframe['research_ready']=ready
        dataframe['research_long_at_close']=desired
        return dataframe
    def populate_entry_trend(self,dataframe,metadata):
        self._guard();dataframe['enter_long']=(dataframe['research_ready']&dataframe['research_long_at_close']).astype(int)
        dataframe['enter_short']=0;dataframe['enter_tag']=self.research_version+':'+self.rule_name
        return dataframe
    def populate_exit_trend(self,dataframe,metadata):
        self._guard();dataframe['exit_long']=(dataframe['research_ready']&~dataframe['research_long_at_close']).astype(int);dataframe['exit_short']=0;dataframe['exit_tag']=self.research_version+':'+self.rule_name+':CASH'
        return dataframe
    def leverage(self,**kwargs):return 1.0
    def confirm_trade_entry(self,**kwargs):
        # No native order execution certified: historical research uses own audited ledger.
        return False

class FrozenT1Research(_FrozenDailyResearch):rule_name='T1'
class FrozenB1Research(_FrozenDailyResearch):rule_name='B1'
