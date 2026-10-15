"""Run frozen SR H1 on Freqtrade's native event loop and accounting engine."""
import argparse,csv,hashlib,json,shutil,sys,time
from collections import Counter,defaultdict
from copy import deepcopy
from datetime import datetime,timezone
from pathlib import Path
import pandas as pd
from freqtrade.commands.optimize_commands import setup_optimize_configuration
from freqtrade.configuration import TimeRange
from freqtrade.enums import RunMode
from freqtrade.persistence import LocalTrade
from sr_backtesting import SRBacktesting,dt
from sr_support import D,H,build_signal_cache,execution_fill,funding_cashflow,is_censored

ROOT=Path(__file__).resolve().parent
PAIR='BTC/USDT:USDT'

def json_default(x):
    if isinstance(x,Path):return str(x)
    if isinstance(x,datetime):return x.isoformat()
    try:return float(x)
    except (TypeError,ValueError):return str(x)
def save(path,x): path.write_text(json.dumps(x,default=json_default,ensure_ascii=False,indent=2)+'\n')
def ms(s):return int(pd.Timestamp(s).timestamp()*1000)

def create_backtest(mode,exchange=None):
    cfg=json.loads(Path('/workspace/shared/freqtrade-smoke-20261011/config-net.json').read_text())
    cfg.update(strategy='StructureReclaimV1',user_data_dir=str(ROOT/'user_data'),
               datadir=str(ROOT/'user_data/data'),fee=0 if mode=='gross' else .0006,
               tradable_balance_ratio=1.0,export='none')
    p=ROOT/f'config-{mode}.json';save(p,cfg)
    cache=ROOT/'user_data/data/futures/leverage_tiers_USDT.json'
    if not cache.exists():shutil.copy('/workspace/shared/freqtrade-smoke-20261011/user_data/data/net/futures/leverage_tiers_USDT.json',cache)
    config=setup_optimize_configuration({'config':[str(p)],'user_data_dir':str(ROOT/'user_data'),
                                         'datadir':str(ROOT/'user_data/data'),'verbosity':0},RunMode.BACKTEST)
    bt=SRBacktesting(config,exchange=exchange)
    bt._set_strategy(bt.strategylist[0])
    return bt

def load_history():
    sources=[Path('/workspace/shared/btc-quant-research-20261010/v2/data/ohlcv_1h.csv'),
             Path('/workspace/shared/btc-quant-research-20261010/data/ohlcv_1h.csv')]
    bars=[];seen=set()
    for source in sources:
        with source.open() as f:
            for row in csv.DictReader(f):
                t=int(row['ts'])
                if t in seen:raise ValueError(f'Duplicate history {t}')
                seen.add(t);b={k:(t if k=='ts' else D(v)) for k,v in row.items()}
                assert t%H==0 and b['low']<=min(b['open'],b['close'])<=max(b['open'],b['close'])<=b['high']
                assert b['volume']>=0;bars.append(b)
    bars.sort(key=lambda b:b['ts'])
    assert len(bars)==26304
    cache=build_signal_cache(bars)
    actual={};base=Path('/workspace/shared/btc-quant-research-20261010/data')
    with (base/'btcusdt_usdt_futures_mark_1h_funding_window.csv').open() as f:
        marks={int(r['ts']):D(r['open']) for r in csv.DictReader(f)}
    with (base/'btcusdt_usdt_futures_funding.csv').open() as f:
        for r in csv.DictReader(f):
            t=int(r['ts']);assert t in marks;actual[t]=(D(r['fundingRate']),marks[t])
    save(ROOT/'data_manifest.json',{'h1_rows':len(bars),'raw_signal_count_all_history':len(cache['signals']),
          'funding_rows':len(actual),'funding_start':dt(min(actual)),'funding_end':dt(max(actual)),
          'sources':[{'path':p,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in sources],
          'unseen_holdout':False,'no_ohlcv_filling':True})
    return cache,actual

def run_one(bt,cache,start,end,delay,slip,mode,actual,export=True,label=None):
    started=datetime.now(timezone.utc)
    bt.fee=0 if mode=='gross' else .0006
    bt.config['fee']=bt.fee;bt.strategy.config['fee']=bt.fee
    bt.configure_research(cache,start,end,delay,slip,mode,actual)
    # Preserve the immediately preceding row for native shift(1)/drop-first.
    # The full-history rule cache already enforces 100 complete H4 warmup. Native
    # positional startup trimming would otherwise override timerange and lose t0=start.
    bt.required_startup=0
    bt.timerange=TimeRange('date','date',(start-H)//1000,end//1000)
    bars=[b for t,b in cache['bars'].items() if t+H<=end]
    frame=pd.DataFrame([{**{k:float(v) for k,v in b.items() if k!='ts'},'date':pd.Timestamp(dt(b['ts']))} for b in bars])
    frame=frame[['date','open','high','low','close','volume']]
    processed=bt.strategy.advise_all_indicators({PAIR:frame})
    native=bt.backtest(processed,dt(start-H),dt(end-H))
    closed=list(LocalTrade.bt_trades)
    trades=[];censored=[]
    for trade in closed:
        record=bt.execution_records[trade.id];c=record['candidate'];x=record['exits'][-1]
        q=record['q'];d=c['d'];entry=record['entry_fill'];raw=record['entry_quote'];close=D(trade.close_rate)
        gross=D(d)*(x['raw_price']-raw)*q
        direct=D(d)*(close-entry)*q
        execution=gross-direct
        fees=q*(entry+close)*(D(0) if mode=='gross' else D('.0006'))
        reserve=q*entry*(D(0) if mode=='gross' else D('.0001'))
        funding=funding_cashflow(record['entry_time'],x['funding_through'],d,q,raw,mode,actual)
        net=direct-fees-reserve+funding
        assert abs(float(net)-trade.close_profit_abs)<1e-6,(trade.id,net,trade.close_profit_abs)
        assert abs(float(funding)-trade.funding_fees)<1e-7
        p=record['plan'];assert q*p['planned_loss_per_btc']<=20+D('1e-7') and q*p['entry_fill']<=1000+D('1e-7')
        planned_risk=q*p['planned_loss_per_btc']
        row=dict(candidate_id=c['id'],signal_time=c['t0'],direction=d,entry_time=record['entry_time'],exit_time=x['time'],
                 entry_quote=raw,entry_fill=entry,raw_exit=x['raw_price'],exit_fill=close,q=q,entry_notional=q*entry,
                 planned_notional=q*p['entry_fill'],margin=q*entry/2,leverage=trade.leverage,
                 sl=c['sl'],tp=c['tp'],target_source=c['target_source'],exit_path=x['reason'],
                 exit_precision=x['time_precision'],funding_through=x['funding_through'],planned_risk=planned_risk,
                 planned_ratio=p['planned_ratio'],actual_R=net/planned_risk,gross=gross,execution_pressure=execution,
                 slippage_component=D(0) if mode=='gross' else (raw+x['raw_price'])*q*D(slip),
                 spread_component=D(0) if mode=='gross' else 2*q,
                 fee=fees,reserve=reserve,funding_signed=funding,net=net,native_profit_abs=trade.close_profit_abs)
        row['rounding_component']=execution-row['slippage_component']-row['spread_component']
        row=json.loads(json.dumps(row,default=json_default))
        (censored if is_censored(record['entry_time'],end-H) else trades).append(row)
    for trade in LocalTrade.bt_trades_open:
        r=bt.execution_records[trade.id]
        censored.append({'candidate_id':r['candidate']['id'],'entry_time':r['entry_time'],'unresolved':True,'native_trade':trade.to_json()})
    assert abs(native['final_balance']-(1000+sum(t.close_profit_abs for t in closed)))<1e-6
    out=dict(label=label,mode=mode,delay=delay,slippage=float(slip),start=dt(start),end=dt(end),
             actual_started_utc=started,actual_finished_utc=datetime.now(timezone.utc),
             trades=trades,censored=censored,native_final_balance=native['final_balance'],
             principal_final_balance=1000+sum(t['net'] for t in trades),
             raw_signals=bt.state.raw_signals,candidates=bt.state.candidates,events=bt.state.events,
             native_closed=[t.to_json() for t in closed],native_open=bt.censored_open,
             native_accounting_reconciled=True)
    if export:
        directory=ROOT/'results'/label;directory.mkdir(parents=True,exist_ok=True)
        save(directory/'result.json',out)
        native['results'].to_json(directory/'native_results_frame.json',orient='table',date_format='iso')
        if trades:
            with (directory/'trades.csv').open('w') as f:
                w=csv.DictWriter(f,fieldnames=trades[0].keys());w.writeheader();w.writerows(trades)
    return out

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--run',action='store_true');args=parser.parse_args()
    if not args.run:raise SystemExit('Use --run only after synthetic acceptance and review.')
    contract=ROOT/'migration_contract_frozen.json'
    expected=(ROOT/'migration_contract_frozen.sha256').read_text().split()[0]
    assert hashlib.sha256(contract.read_bytes()).hexdigest()==expected
    for frozen in json.loads(contract.read_text())['frozen_inputs'].values():
        assert hashlib.sha256(Path(frozen['path']).read_bytes()).hexdigest()==frozen['sha256']
    print('Preparing causal data cache before outcomes',flush=True)
    cache,actual=load_history()
    variants=[('D0',0,'.0002'),('D1',1,'.0002'),('D2',2,'.0002'),('D0_SLIP5BP',0,'.0005'),('D1_SLIP5BP',1,'.0005')]
    periods=[('earlier',ms('2025-10-10T18:00:00Z'),ms('2026-04-10T18:00:00Z')),
             ('validation',ms('2026-04-10T18:00:00Z'),ms('2026-10-10T18:00:00Z'))]
    save(ROOT/'implementation_before_results.json',{'utc':datetime.now(timezone.utc),'contract_hash':expected,
         'files':{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in list(ROOT.glob('*.py'))+list((ROOT/'user_data/strategies').glob('*.py'))}})
    bt=create_backtest('gross')
    for mode in ['gross','protocol','actual']:
        selected=periods if mode!='actual' else [('funding_covered',ms('2026-07-13T00:00:00Z'),ms('2026-10-10T18:00:00Z'))]
        for period,start,end in selected:
            for name,delay,slip in variants:
                label=f'{mode}_{period}_{name}'
                r=run_one(bt,cache,start,end,delay,D(slip),mode,actual,label=label)
                print(json.dumps({'run':label,'trades':len(r['trades']),'censored':len(r['censored']),
                                  'net':r['principal_final_balance']-1000}),flush=True)
    bt.cleanup()
