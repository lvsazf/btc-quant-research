"""Frozen SR H1 pure rules and causal candidate state, no portfolio simulator."""
from copy import deepcopy
from decimal import Decimal
import importlib.util
from pathlib import Path

SOURCE=Path('/workspace/shared/btc-structure-reclaim-v1-20261011/engine.py')
spec=importlib.util.spec_from_file_location('sr_frozen_reference',SOURCE)
rules=importlib.util.module_from_spec(spec); spec.loader.exec_module(rules)
D=rules.D; H=rules.H

def build_signal_cache(bars):
    if not rules.contiguous(bars): raise ValueError('Noncontiguous history')
    series=rules.trend_series(bars)
    signals={}
    for i in range(1,len(bars)):
        s=rules.signal_at(bars,i,series)
        if s: signals[s['t0']]=s
    return dict(signals=signals,series=series,bars={b['ts']:b for b in bars})

def execution_fill(raw,d,entry,slip,mode):
    return D(raw) if mode=='gross' else rules.fill_price(raw,d,entry,slip)

def funding_cashflow(entry,through,d,q,raw,mode,actual):
    if mode=='gross': return D(0)
    cash=D(0)
    for t in rules.funding_times(entry,through):
        if mode=='protocol': cash-=q*raw*D('.0001')
        elif mode=='actual':
            if t not in actual: raise ValueError(f'Missing actual funding at {t}')
            rate,mark=actual[t]; cash-=D(d)*q*rate*mark
        else: raise ValueError(mode)
    return cash

def is_censored(entry,last_open): return entry+6*H>last_open

class CandidateState:
    def __init__(self,delay,slip=D('.0002')):
        self.delay=delay;self.slip=D(slip);self.active=None
        self.raw_signals=[];self.candidates=[];self.events=[];self.serial=0
    def log(self,t,event,**kw): self.events.append(dict(time=t,event=event,**kw))
    def close(self,t,reason):
        self.active.update(outcome=reason,resolved_time=t)
        self.log(t,reason,candidate_id=self.active['id']);self.active=None
    def step(self,t,signal,completed,quote,trend,has_position,equity):
        if self.active:
            status=rules.candidate_status(self.active,t,completed,quote,trend)
            if status.startswith('cancel_') or status=='expired': self.close(t,status)
        if signal:
            s=deepcopy(signal);s['id']=f'signal_{t}_{s["d"]}';self.raw_signals.append(s)
            if s['tp'] is None: s['disposition']='no_target';self.log(t,'signal_no_target',signal_id=s['id'])
            elif self.active or has_position:
                s['disposition']='suppressed_active';self.log(t,'signal_suppressed',signal_id=s['id'])
            else:
                self.serial+=1;s['disposition']='candidate'
                self.active=dict(s,id=f'candidate_{self.serial}',signal_id=s['id'],created_time=t,attempts=[],outcome='pending')
                self.candidates.append(self.active);self.log(t,'candidate_created',candidate_id=self.active['id'])
        if not self.active or quote is None: return None
        c=self.active;status=rules.candidate_status(c,t,[],quote,trend)
        if status.startswith('cancel_') or status=='expired': reason=status
        elif t<c['t0']+self.delay*H: reason='delay_wait'
        elif status!='eligible': reason=status
        else: reason=None
        plan=rules.plan_entry(c,quote,t,equity,self.slip) if reason is None else None
        if plan and not plan['accepted']: reason=plan['reason']
        c['attempts'].append(dict(time=t,quote=quote,reason=reason or 'accepted',plan=plan))
        self.log(t,'entry_attempt',candidate_id=c['id'],reason=reason or 'accepted')
        if reason and (reason.startswith('cancel_') or reason=='expired'): self.close(t,reason)
        if reason is not None: return None
        return dict(candidate=c,plan=plan,entry_quote=quote,entry_time=t)
    def entered(self,t):
        self.active.update(outcome='entered',entry_time=t)
        self.log(t,'entered',candidate_id=self.active['id']);self.active=None
    def finish(self,t,completed,trend):
        self.step(t,None,completed,None,trend,False,D(0))
        if self.active: self.close(t,'censored_candidate')
