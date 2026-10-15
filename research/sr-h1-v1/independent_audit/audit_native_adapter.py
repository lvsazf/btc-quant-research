"""Independent read-only source audit and synthetic native ledger checks.

Writes only this audit directory. Does not run a historical portfolio.
Exchange metadata is mocked; Backtesting loop, Order, LocalTrade, and Wallets
are native. Full-loop acceptance with real public metadata is a separate suite.
"""
import csv
import hashlib
import importlib
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock

ROOT = Path(__file__).resolve().parent
APP = Path('/workspace/shared/freqtrade-sr-h1-v1-20261011')
UPSTREAM = Path('/workspace/shared/freqtrade-smoke-20261011/upstream')
REFERENCE = Path('/workspace/shared/btc-structure-reclaim-v1-20261011')
DATA = Path('/workspace/shared/btc-quant-research-20261010/data')
sys.path[:0] = [str(APP), str(APP/'user_data/strategies'), str(REFERENCE), str(UPSTREAM)]

import pandas as pd
from ccxt import TICK_SIZE
from freqtrade.enums import TradingMode, MarginMode
from freqtrade.persistence import LocalTrade, Trade, PairLocks, disable_database_use
from freqtrade.wallets import Wallets
from sr_backtesting import SRBacktesting, dt
from sr_support import D, H, build_signal_cache, rules
from StructureReclaimV1 import StructureReclaimV1
from test_engine import setup_rows, bar


def synthetic(d, delay, mode):
    disable_database_use('1h')
    Trade.reset_trades()
    PairLocks.reset_locks()
    cfg = dict(dry_run=True, dry_run_wallet=1000, trading_mode=TradingMode.FUTURES,
               margin_mode=MarginMode.ISOLATED, stake_currency='USDT', tradable_balance_ratio=1.0)
    exchange = MagicMock()
    exchange.get_proxy_coin.return_value = 'USDT'
    exchange.margin_mode = MarginMode.ISOLATED
    exchange.get_precision_price.return_value = .1
    exchange.get_precision_amount.return_value = .0001
    exchange.get_contract_size.return_value = 1.0
    exchange.get_pair_base_currency.return_value = 'BTC'
    exchange.get_liquidation_price.return_value = None
    bt = SRBacktesting.__new__(SRBacktesting)
    bt.config = cfg
    bt.strategy = StructureReclaimV1(cfg)
    bt.strategy.max_open_trades = 1
    bt.exchange = exchange
    bt.wallets = Wallets(cfg, exchange, is_backtest=True)
    bt.trading_mode = TradingMode.FUTURES
    bt.margin_mode = MarginMode.ISOLATED
    bt._position_stacking = False
    bt._can_short = True
    bt.enable_protections = False
    bt.price_pair_prec = {}
    bt.precision_mode = TICK_SIZE
    bt.precision_mode_price = TICK_SIZE
    bt.order_id_counter = bt.trade_id_counter = bt.rejected_trades = 0
    bt._exchange_name = 'bitget'
    bt.fee = 0 if mode == 'gross' else .0006
    bt.timeframe_min = 60
    bars = setup_rows() + [bar(h,205,206,204,205) for h in range(400,412)]
    if d == -1:
        bars = [dict(b, open=D(400)-b['open'], high=D(400)-b['low'],
                     low=D(400)-b['high'], close=D(400)-b['close']) for b in bars]
    cache = build_signal_cache(bars)
    actual = {400*H:(D('.0001'),D(200)), 408*H:(D('.0001'),D(200))}
    bt.configure_research(cache,400*H,412*H,delay,D('.0002'),mode,actual)
    for b in bars[400:]:
        row = [pd.Timestamp(dt(b['ts']))] + [float(b[k]) for k in ['open','high','low','close']]
        row += [0,0,0,0,None,None]
        bt.backtest_loop(row,'BTC/USDT:USDT',dt(b['ts']),None,True)
    assert len(LocalTrade.bt_trades) == 1
    tr = LocalTrade.bt_trades[0]
    r = bt.execution_records[tr.id]
    q, ef, x = r['q'], r['entry_fill'], r['exits'][0]
    settlements = [t for t in range(0,500*H,8*H) if r['entry_time'] < t <= x['funding_through']]
    if mode == 'gross':
        fund, fee_open, fee_close = D(0), D(0), D(0)
    else:
        fund = (-q*r['entry_quote']*D('.0001')*len(settlements) if mode == 'protocol'
                else sum((-D(d)*q*actual[t][0]*actual[t][1] for t in settlements),D(0)))
        fee_open, fee_close = q*ef*D('.0007'), q*x['fill']*D('.0006')
    expected = q*D(d)*(x['fill']-ef)-fee_open-fee_close+fund
    assert abs(D(tr.close_profit_abs)-expected) < D('.00000001')
    assert abs(D(tr.funding_fees)-fund) < D('.00000001')
    assert abs(D(bt.wallets.get_total('USDT'))-D(1000)-expected) < D('.00000001')
    assert abs(D(sum(o.funding_fee or 0 for o in tr.orders))-fund) < D('.00000001')
    assert tr.funding_fee_running == 0
    return dict(direction=d,delay=delay,mode=mode,entry_hour=r['entry_time']/H,
                exit_hour=x['time']/H,q=str(q),expected_net=str(expected),native_net=tr.close_profit_abs,
                expected_funding=str(fund),native_funding=tr.funding_fees,
                order_funding=[o.funding_fee for o in tr.orders],native_final_balance=bt.wallets.get_total('USDT'),
                native_fee_open_cost_display=tr.fee_open_cost,correct_full_notional_entry_fee=str(fee_open))


def coverage():
    funding=list(csv.DictReader((DATA/'btcusdt_usdt_futures_funding.csv').open()))
    marks=list(csv.DictReader((DATA/'btcusdt_usdt_futures_mark_1h_funding_window.csv').open()))
    minutes=list(csv.DictReader((DATA/'selected_execution_1m.csv').open()))
    f=[int(r['ts']) for r in funding]
    m=[int(r['ts']) for r in marks]
    ts=[int(r['ts']) for r in minutes]
    s=set(ts)
    groups=Counter(t//H*H for t in ts)
    minute=60000
    start=int(datetime(2026,7,13,tzinfo=timezone.utc).timestamp()*1000)
    end=int(datetime(2026,10,10,18,tzinfo=timezone.utc).timestamp()*1000)
    expected=set(range(start,end,8*H))
    assert not expected-set(f)
    assert len(f)==len(set(f)) and not set(f)-set(m)
    return dict(funding_rows=len(f),funding_missing_expected=sorted(expected-set(f)),
                funding_duplicates=len(f)-len(set(f)),funding_without_mark=sorted(set(f)-set(m)),
                funding_first=dt(min(f)).isoformat(),funding_last=dt(max(f)).isoformat(),
                mark_rows=len(m),mark_gaps=sum(b-a!=H for a,b in zip(m,m[1:])),
                minute_rows=len(ts),minute_duplicates=len(ts)-len(s),minute_complete_hours=sum(
                    all(h+i*minute in s for i in range(60)) for h in groups),minute_hour03_rows=sum(
                    t%H==3*minute for t in ts),minute_complete_6h_from_hour03=sum(
                    all(t+i*minute in s for i in range(361)) for t in ts if t%H==3*minute),
                minute_interrupted_edges=sum(b-a!=minute for a,b in zip(sorted(s),sorted(s)[1:])))


def main():
    source_files=[APP/'sr_support.py',APP/'sr_backtesting.py',APP/'run_research.py',
                  APP/'user_data/strategies/StructureReclaimV1.py',APP/'migration_contract_frozen.json']
    before={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in source_files}
    contract=json.loads((APP/'migration_contract_frozen.json').read_text())
    for value in contract['frozen_inputs'].values():
        assert hashlib.sha256(Path(value['path']).read_bytes()).hexdigest()==value['sha256']
    cases=[synthetic(d,delay,mode) for d in (1,-1) for delay in (0,2)
           for mode in ('gross','protocol','actual')]
    runner=importlib.import_module('run_research')
    captured={}
    runner.save=lambda path,obj:captured.update({str(path):obj})
    cache,actual=runner.load_history()
    after={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in source_files}
    output=dict(audit_time_utc=datetime.now(timezone.utc).isoformat(),scope='Synthetic native ledger only; no historical portfolio run',
                frozen_input_hashes_match=True,source_sha256_before=before,source_sha256_after=after,
                source_changed_during_audit=before!=after,synthetic_cases=cases,
                real_source_checks=dict(h1_bars=len(cache['bars']),complete_h4=len(cache['series']),funding_rows=len(actual)),
                coverage=coverage())
    path=ROOT/'audit_evidence.json'
    path.write_text(json.dumps(output,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(dict(path=str(path),synthetic_passed=len(cases),source_changed=before!=after,
                         real_source_checks=output['real_source_checks'],coverage=output['coverage']),ensure_ascii=False))


if __name__=='__main__':
    main()
