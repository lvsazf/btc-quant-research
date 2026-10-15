"""SR H1 v1 research adapter. Requires the audited research Backtesting subclass.
Not a live trading strategy: native unadapted execution is semantically different.
"""
from freqtrade.strategy import IStrategy

class StructureReclaimV1(IStrategy):
    INTERFACE_VERSION=3
    timeframe='1h'
    can_short=True
    startup_candle_count=400
    minimal_roi={}
    stoploss=-.99
    process_only_new_candles=True
    position_adjustment_enable=False
    trailing_stop=False
    order_types={'entry':'market','exit':'market','stoploss':'market','stoploss_on_exchange':False}
    def populate_indicators(self,dataframe,metadata):
        if not getattr(self,'research_adapter',False):
            raise RuntimeError('Use audited SR research adapter; live execution is not authorized')
        return dataframe
    def populate_entry_trend(self,dataframe,metadata):
        # Raw closed-H1 signals; the causal candidate state decides actual admission.
        signals=self.rule_cache['signals']
        directions=[signals.get(int(t.timestamp()*1000)+3600000,{}).get('d',0) for t in dataframe.date]
        dataframe['enter_long']=[int(d==1) for d in directions]
        dataframe['enter_short']=[int(d==-1) for d in directions]
        return dataframe
    def populate_exit_trend(self,dataframe,metadata):
        dataframe['exit_long']=0;dataframe['exit_short']=0
        return dataframe
    def leverage(self,**kwargs): return min(2.0,kwargs['max_leverage'])
    def confirm_trade_entry(self,pair,amount,rate,**kwargs):
        plan=getattr(self,'current_plan',None)
        if not plan or pair!='BTC/USDT:USDT': return False
        return (abs(amount-float(plan['q']))<1e-10 and
                amount*float(plan['entry_fill'])<=1000+1e-8 and
                amount*float(plan['planned_loss_per_btc'])<=20+1e-8)
