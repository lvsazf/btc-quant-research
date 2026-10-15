import importlib
import sys
from decimal import Decimal
from pathlib import Path
import pytest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))

def module():
    try: return importlib.import_module('sr_support')
    except ModuleNotFoundError: pytest.fail('Migration support is not implemented')

def test_funding_entry_excluded_exit_included():
    m=module(); H=m.H
    rows={8*H:(Decimal('.001'),Decimal('100')),16*H:(Decimal('.002'),Decimal('101'))}
    assert m.funding_cashflow(8*H,16*H,1,Decimal('2'),Decimal('100'),'actual',rows)==Decimal('-.404')
    assert m.funding_cashflow(8*H,16*H,-1,Decimal('2'),Decimal('100'),'actual',rows)==Decimal('.404')
    assert m.funding_cashflow(8*H,16*H,-1,Decimal('2'),Decimal('100'),'protocol',rows)==Decimal('-.02')

def test_missing_actual_funding_is_error_not_zero():
    m=module(); H=m.H
    with pytest.raises(ValueError,match='Missing actual funding'):
        m.funding_cashflow(7*H,8*H,1,Decimal('1'),Decimal('100'),'actual',{})

def test_tail_censor_independent_of_early_exit():
    m=module(); H=m.H
    assert m.is_censored(10*H,15*H)
    assert not m.is_censored(10*H,16*H)

def test_causal_signal_prefix_and_pivot_confirmation():
    m=module();
    sys.path.insert(0,'/workspace/shared/btc-structure-reclaim-v1-20261011')
    from test_engine import setup_rows,bar
    a=setup_rows()+[bar(400,204,206,202,205),bar(401,205,210,203,209)]
    full=m.build_signal_cache(a)
    prefix=m.build_signal_cache(a[:400])
    assert full['signals'][400*m.H]==prefix['signals'][400*m.H]
    assert full['signals'][400*m.H]['tp']==Decimal('225')

def test_one_candidate_invalidates_before_delayed_admission():
    m=module(); H=m.H
    c={'t0':0,'d':1,'boundary':Decimal('100'),'sl':Decimal('95'),'tp':Decimal('110')}
    state=m.CandidateState(delay=2)
    state.active=dict(c,id='c',attempts=[])
    result=state.step(H,None,[dict(ts=0,low=Decimal('94'),high=Decimal('106'),close=Decimal('103'))],Decimal('103'),1,False,Decimal('1000'))
    assert result is None and state.active is None
    assert state.events[-1]['event']=='cancel_sl'

def test_position_suppresses_raw_signal_before_exit():
    m=module(); H=m.H
    c={'t0':H,'d':1,'boundary':Decimal('100'),'sl':Decimal('95'),'tp':Decimal('110')}
    state=m.CandidateState(delay=0)
    assert state.step(H,c,[],Decimal('102'),1,True,Decimal('1000')) is None
    assert state.raw_signals[-1]['disposition']=='suppressed_active'
    assert state.active is None

def test_pressure_fill_is_not_clipped_to_bar_high():
    m=module(); assert m.execution_fill(Decimal('100'),1,True,Decimal('.0002'),'protocol')==Decimal('101.1')
    assert m.execution_fill(Decimal('100'),1,True,Decimal('.0002'),'gross')==Decimal('100')

def test_terminal_candidate_processes_last_completed_bar_before_censor():
    m=module();H=m.H
    state=m.CandidateState(delay=2)
    state.active={'t0':0,'d':1,'boundary':Decimal('100'),'sl':Decimal('95'),'tp':Decimal('110'),'id':'c','attempts':[]}
    state.finish(H,[dict(ts=0,low=Decimal('94'),high=Decimal('106'),close=Decimal('103'))],1)
    assert state.events[-1]['event']=='cancel_sl'
