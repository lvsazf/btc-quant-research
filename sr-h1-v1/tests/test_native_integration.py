"""Native loop/Order/LocalTrade/Wallet integration, official public market metadata."""
import importlib
import sys
from pathlib import Path
import pytest
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
sys.path.insert(0,'/workspace/shared/btc-structure-reclaim-v1-20261011')

def runner_module():
    try:return importlib.import_module('run_research')
    except ModuleNotFoundError:pytest.fail('Native research runner is not implemented')

@pytest.fixture(scope='module')
def native():
    return {'bt':None}

def synthetic_case(native,extra,delay=0,mode='protocol'):
    m=runner_module()
    if native['bt'] is None: native['bt']=m.create_backtest('protocol')
    sys.path.insert(0,'/workspace/shared/btc-structure-reclaim-v1-20261011')
    from test_engine import setup_rows,bar
    from sr_support import build_signal_cache,H,D
    bars=setup_rows()+extra
    cache=build_signal_cache(bars)
    # The known synthetic raw signal has TP225/SL195.9. Entry205 qualifies.
    return m.run_one(native['bt'],cache,400*H,(400+len(extra))*H,delay,D('.0002'),mode,{},export=False)

def test_native_same_bar_stop_before_target_and_pressure_outside_range(native):
    from test_engine import bar
    result=synthetic_case(native,[bar(400,205,230,194,210)]+[bar(h,210,211,209,210) for h in range(401,408)])
    t=result['trades'][0]
    assert t['exit_path']=='SL'
    assert t['raw_exit']==195.9
    assert t['entry_time']==400*3600000
    assert t['exit_time']==401*3600000-1
    assert t['planned_risk']<=20 and t['entry_notional']<=1000
    assert abs(t['net']-t['native_profit_abs'])<1e-6

def test_native_timeout_and_funding_entry_boundary(native):
    from test_engine import bar
    result=synthetic_case(native,[bar(h,205,206,204,205) for h in range(400,408)])
    t=result['trades'][0]
    assert t['exit_path']=='TIMEOUT' and t['exit_time']==406*3600000
    assert t['funding_signed']==0 # entry400h settles; excluded; next408h is after exit
    assert abs(result['native_final_balance']-(1000+sum(t['net'] for t in result['trades'])))<1e-6

def test_native_gap_stop_before_timeout(native):
    from test_engine import bar
    result=synthetic_case(native,[bar(h,205,206,204,205) for h in range(400,406)]+[bar(406,190,210,189,200),bar(407)])
    t=result['trades'][0]
    assert t['exit_path']=='GAP_SL' and t['raw_exit']==190

def test_native_tail_early_target_censored(native):
    from test_engine import bar
    result=synthetic_case(native,[bar(400,205,226,200,220),bar(401,220,223,219,221)])
    assert result['trades']==[] and len(result['censored'])==1
    assert result['censored'][0]['exit_path']=='TP'
