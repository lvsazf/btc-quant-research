"""Narrow Freqtrade execution-semantic adapter; native loop/orders/wallet retained."""
from copy import deepcopy
from datetime import datetime, timezone
import pandas as pd
from freqtrade.optimize.backtesting import Backtesting, DATE_IDX, OPEN_IDX
from freqtrade.persistence import LocalTrade
from sr_support import D,H,rules,CandidateState,execution_fill,funding_cashflow

def dt(ms): return datetime.fromtimestamp(ms/1000,tz=timezone.utc)
def millis(t): return int(t.timestamp()*1000)

class SRBacktesting(Backtesting):
    def configure_research(self,cache,start,end,delay,slip,mode,actual):
        self.cache=cache;self.start_ms=start;self.end_ms=end;self.mode=mode;self.slip=D(slip)
        self.actual=actual
        self.strategy.rule_cache=cache
        self.strategy.candidate_state=CandidateState(delay,self.slip)
        self.state=self.strategy.candidate_state
        self.execution_records={};self.admitted=None;self.seen=set();self.censored_open=[]
        self.strategy.research_adapter=True
    def backtest_loop(self,row,pair,current_time,trade_dir,can_enter):
        t=millis(current_time)
        if t in self.seen: return None
        self.seen.add(t)
        if not self.start_ms<=t<self.end_ms: return None
        previous=self.cache['bars'].get(t-H)
        raw=self.cache['signals'].get(t)
        trend=rules.trend_at(self.cache['series'],t)['direction']
        positions=LocalTrade.bt_trades_open_pp[pair]
        equity=D(self.wallets.get_total('USDT'))
        self.admitted=self.state.step(t,raw,[previous] if previous else [],D(row[OPEN_IDX]),trend,bool(positions),equity)
        direction=None
        if self.admitted:
            direction='long' if self.admitted['candidate']['d']==1 else 'short'
            self.strategy.current_plan=self.admitted['plan']
            mutable=list(row)
            while len(mutable)<12: mutable.append(None)
            # Native tag index obtained by module constant rather than guessed index.
            from freqtrade.optimize.backtesting import ENTER_TAG_IDX
            mutable[ENTER_TAG_IDX]=self.admitted['candidate']['id'];row=mutable
        # Permit the last observed open causally; report-time horizon censoring follows.
        super().backtest_loop(row,pair,current_time,direction,True)
        # Do not return reversal direction: frozen rule forbids same-hour re-entry.
        return None
    def get_valid_entry_price_and_stake(self,pair,row,propose_rate,stake_amount,direction,current_time,entry_tag,trade,order_type,price_precision,precision_mode_price):
        assert trade is None and self.admitted
        a=self.admitted;p=a['plan'];d=a['candidate']['d']
        price=execution_fill(a['entry_quote'],d,True,self.slip,self.mode)
        return float(price),float(p['q']*price/2)+1e-10,2.0,0.0
    def _get_order_filled(self,rate,row):
        # All orders are modeled immediately-filled market orders with explicit adverse
        # execution stress. Do not clamp to candle range or use H/L for admission.
        return True
    def _try_close_open_order(self,order,trade,current_date,row):
        if order and trade.id not in self.execution_records:
            assert self.admitted and order.ft_order_side==trade.entry_side
            a=deepcopy(self.admitted);a['q']=D(order.amount)
            a['entry_fill']=D(order.ft_price);a['exits']=[]
            self.execution_records[trade.id]=a
            trade.fee_open=0 if self.mode=='gross' else .0007
            trade.fee_close=0 if self.mode=='gross' else .0006
            self.state.entered(a['entry_time'])
        return super()._try_close_open_order(order,trade,current_date,row)
    def _run_funding_fees(self,trade,current_time,force=False):
        record=self.execution_records.get(trade.id)
        if record is None: return
        through=record['exits'][-1]['funding_through'] if record['exits'] else millis(current_time)
        total=funding_cashflow(record['entry_time'],through,record['candidate']['d'],record['q'],record['entry_quote'],self.mode,self.actual)
        # Native order closing moves running funding into the order ledger.
        prior=sum(o.funding_fee or 0 for o in trade.orders)
        trade.set_funding_fees(float(total)-prior)
    def _check_trade_exit(self,trade,row,current_time):
        r=self.execution_records[trade.id];c=r['candidate'];t=millis(current_time)
        b=self.cache['bars'][t]
        probe=dict(d=c['d'],sl=c['sl'],tp=c['tp'],entry_time=r['entry_time'],remaining=r['q'])
        exits=rules.exit_bar(probe,b,self.slip)
        self._run_funding_fees(trade,current_time)
        if not exits: return None
        x=exits[0];x['fill']=execution_fill(x['raw_price'],c['d'],False,self.slip,self.mode)
        r['exits'].append(x);trade.exit_reason=x['reason']
        exitrow=list(row);exitrow[DATE_IDX]=pd.Timestamp(dt(x['time']))
        return self._exit_trade(trade,exitrow,float(x['fill']),trade.amount,x['reason'])
    def _process_exit_order(self,order,trade,current_time,row,pair):
        r=self.execution_records[trade.id]
        exact=dt(r['exits'][-1]['time'])
        return super()._process_exit_order(order,trade,exact,row,pair)
    def handle_left_open(self,open_trades,data):
        # No fabricated force exit. Unresolved native positions are retained separately.
        self.censored_open=[t.to_json() for trades in open_trades.values() for t in trades]
        last=self.cache['bars'].get(self.end_ms-H)
        trend=rules.trend_at(self.cache['series'],self.end_ms)['direction']
        self.state.finish(self.end_ms,[last] if last else [],trend)
