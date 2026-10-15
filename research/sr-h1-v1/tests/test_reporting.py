import importlib
import pytest

def test_metric_loss_streak_pf_and_drawdown():
    try:m=importlib.import_module('summarize_research')
    except ModuleNotFoundError:pytest.fail('Research reporting not implemented')
    rows=[{'net':x,'gross':x,'execution_pressure':0,'fee':0,'reserve':0,'funding_signed':0,
           'planned_risk':20,'actual_R':x/20,'planned_ratio':1,'entry_notional':100,
           'planned_notional':100,'leverage':2,'margin':50,'direction':1,
           'entry_time':i*3600000,'exit_time':i*3600000+1,'exit_path':'TIMEOUT'}
          for i,x in enumerate([10,-4,-3,2,-1])]
    s=m.metrics(rows)
    assert s['net']==4 and s['profit_factor']==1.5
    assert s['max_losing_streak']==2 and s['realized_max_drawdown']==7
    assert s['completed_trades']==5 and s['win_rate']==.4

def test_nonpositive_net_rejects_even_with_enough_trades():
    m=importlib.import_module('summarize_research')
    good={'net':1,'profit_factor':1.1,'completed_trades':30}
    quarters=[dict(net=1,completed_trades=10),dict(net=1,completed_trades=20)]
    assert m.gates(good,quarters)['all_pass']
    bad=dict(good,net=-1)
    assert not m.gates(bad,quarters)['all_pass']
