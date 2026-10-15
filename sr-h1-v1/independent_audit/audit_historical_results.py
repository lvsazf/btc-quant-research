"""Read-only verification of observed outputs, not a portfolio simulator.

Recomputes indicators, target provenance, per-attempt plans, observed trade
exits and accounting directly from source CSVs. Does not call engine.simulate
or adapter rules, generate a new portfolio, or modify the research outputs.
"""
import csv
import hashlib
import json
from bisect import bisect_right
from collections import Counter
from datetime import datetime, timezone
from decimal import Decimal, ROUND_CEILING, ROUND_FLOOR
from pathlib import Path

ROOT=Path(__file__).resolve().parent
APP=Path('/workspace/shared/freqtrade-sr-h1-v1-20261011')
DATA=Path('/workspace/shared/btc-quant-research-20261010/data')
H=3600000
D=lambda x: Decimal(str(x))
TICK=D('.1');STEP=D('.0001');FEE=D('.0006');RESERVE=D('.0001');FUND=D('.0001')
checks=Counter()


def near(actual,expected,label,tolerance=D('0.0000001')):
    assert abs(D(actual)-D(expected))<=tolerance,(label,actual,expected)
    checks[label]+=1


def fill(raw,d,entry,slip):
    side=d if entry else -d
    return ((raw*(1+side*slip)+side)/TICK).to_integral_value(
        rounding=ROUND_CEILING if side>0 else ROUND_FLOOR)*TICK


def settlements(entry,through):
    return list(range((entry//(8*H)+1)*8*H,through+1,8*H))


def load():
    bars=[]
    for p in [Path('/workspace/shared/btc-quant-research-20261010/v2/data/ohlcv_1h.csv'),DATA/'ohlcv_1h.csv']:
        for r in csv.DictReader(p.open()):
            bars.append({k:int(v) if k=='ts' else D(v) for k,v in r.items()})
    bars.sort(key=lambda x:x['ts'])
    assert len({b['ts'] for b in bars})==len(bars)==26304
    assert all(y['ts']-x['ts']==H for x,y in zip(bars,bars[1:]))
    index={b['ts']:i for i,b in enumerate(bars)}
    groups={}
    for b in bars:groups.setdefault(b['ts']//(4*H)*4*H,[]).append(b)
    closes=[];ema=None;trends=[]
    for t,g in sorted(groups.items()):
        if [b['ts'] for b in g]!=[t+i*H for i in range(4)]:continue
        closes.append(g[-1]['close']);previous=ema
        if len(closes)==20:ema=sum(closes)/D(20)
        elif len(closes)>20:ema=(D(2)*closes[-1]+D(19)*ema)/D(21)
        direction=None
        if len(closes)>=100:
            direction=1 if closes[-1]>ema>previous else -1 if closes[-1]<ema<previous else 0
        trends.append(dict(time=t+4*H,d=direction,ema=ema,previous=previous,count=len(closes)))
    marks={int(r['ts']):D(r['open']) for r in csv.DictReader((DATA/'btcusdt_usdt_futures_mark_1h_funding_window.csv').open())}
    actual={int(r['ts']):(D(r['fundingRate']),marks[int(r['ts'])]) for r in csv.DictReader((DATA/'btcusdt_usdt_futures_funding.csv').open())}
    return bars,index,trends,actual


BARS,INDEX,TRENDS,ACTUAL=load()
TREND_TIMES=[t['time'] for t in TRENDS]


def trend(t):
    i=bisect_right(TREND_TIMES,t)-1
    return TRENDS[i] if i>=0 else dict(d=None)


def raw_expected(t):
    if t-H not in INDEX or t-2*H not in INDEX:return None
    b0,b1=BARS[INDEX[t-2*H]],BARS[INDEX[t-H]]
    d=trend(t)['d']
    if d==1 and not(b0['close']<b0['open'] and b1['close']>b0['high'] and b1['low']>b0['low']):return None
    if d==-1 and not(b0['close']>b0['open'] and b1['close']<b0['low'] and b1['high']<b0['high']):return None
    if d not in (1,-1):return None
    key='high' if d==1 else 'low';swings=[]
    for center in range(t-72*H,t-2*H,H):
        if any(center+j*H not in INDEX for j in (-2,-1,0,1,2)):continue
        if center+3*H>t:continue
        value=BARS[INDEX[center]][key]
        if d*(value-b1['close'])>0 and all(d*(value-BARS[INDEX[center+j*H]][key])>0 for j in (-2,-1,1,2)):
            swings.append((value,center))
    best=min(swings,key=lambda x:(d*x[0],-x[1])) if swings else None
    return dict(d=d,sl=b0['low']-TICK if d==1 else b0['high']+TICK,
                boundary=b0['high'] if d==1 else b0['low'],p0=b1['close'],target=best)


def status(c,t,end):
    d=c['d'];sl=D(c['sl']);tp=D(c['tp']);boundary=D(c['boundary'])
    for bt in range(c['t0'],t,H):
        b=BARS[INDEX[bt]]
        if b['low']<=sl if d==1 else b['high']>=sl:return 'cancel_sl'
        if d*(b['close']-boundary)<=0:return 'cancel_close'
        if b['high']>=tp if d==1 else b['low']<=tp:return 'cancel_tp'
    if trend(t)['d']!=d:return 'cancel_trend'
    quote=BARS[INDEX[t]]['open'] if t<end and t in INDEX else None
    if quote is not None:
        if d*(quote-sl)<=0:return 'cancel_sl_quote'
        if d*(quote-tp)>=0:return 'cancel_tp_quote'
    if t>=c['t0']+3*H:return 'expired'
    if quote is not None and d*(quote-boundary)<=0:return 'quote_inside_boundary'
    return 'eligible'


def inspect_result(path):
    before=hashlib.sha256(path.read_bytes()).hexdigest()
    r=json.loads(path.read_text());mode=r['mode'];slip=D(r['slippage'])
    start=int(datetime.fromisoformat(r['start']).timestamp()*1000)
    end=int(datetime.fromisoformat(r['end']).timestamp()*1000)
    assert end-H in INDEX
    expected={t:raw_expected(t) for t in range(start,end,H)}
    expected={t:s for t,s in expected.items() if s}
    actual_raw={s['t0']:s for s in r['raw_signals']}
    assert len(actual_raw)==len(r['raw_signals']) and set(expected)==set(actual_raw)
    checks['complete_raw_signal_population']+=1
    for t,s in actual_raw.items():
        exp=expected[t];assert s['d']==exp['d']
        for key in ('sl','boundary','p0'):near(s[key],exp[key],'raw_signal_'+key)
        target=exp['target']
        assert (s['tp'] is None)==(target is None)
        if target:
            near(s['tp'],target[0],'locked_nearest_pivot')
            assert s['target_source']['center_time']==target[1]
            assert s['target_source']['confirmed_time']==target[1]+3*H<=t
        else:assert s['disposition']=='no_target'
        near(s['trend']['ema'],trend(t)['ema'],'independent_sma_seeded_ema')
        assert s['trend']['complete_count']==trend(t)['count']
    closed=r['native_closed'];ledger=r['trades']+[t for t in r['censored'] if not t.get('unresolved')]
    native={t['enter_tag']:t for t in closed}
    candidates={c['id']:c for c in r['candidates']}
    assert len(candidates)==len(r['candidates'])==sum(s['disposition']=='candidate' for s in actual_raw.values())
    accepted={(c['id'],a['time']) for c in r['candidates'] for a in c['attempts'] if a['reason']=='accepted'}
    observed={(t['candidate_id'],t['entry_time']) for t in ledger+r['native_open']}
    assert not r['native_open'], 'Additional unresolved-position audit would be required.'
    assert accepted==observed
    checks['accepted_attempts_equal_observed_entries']+=1
    for at,s in actual_raw.items():
        if s['tp'] is None:continue
        active_candidate=any(c['created_time']<at and (
            at<=c['entry_time'] if 'entry_time' in c else at<c.get('resolved_time',end)
        ) for c in r['candidates'])
        active_position=any(t['entry_time']<at<=t['exit_time'] for t in ledger)
        disposition='suppressed_active' if active_candidate or active_position else 'candidate'
        assert s['disposition']==disposition,(r['label'],at,s['disposition'],disposition)
        checks['independent_suppression_interval']+=1
    for c in r['candidates']:
        s=actual_raw[c['t0']]
        assert c['sl']==s['sl'] and c['tp']==s['tp'] and c['target_source']==s['target_source']
        for a in c['attempts']:
            t=a['time'];quote=BARS[INDEX[t]]['open'];d=c['d']
            near(a['quote'],quote,'only_current_open_admission_quote')
            st=status(c,t,end)
            reason=st if st.startswith('cancel_') or st=='expired' else 'delay_wait' if t<c['t0']+r['delay']*H else st if st!='eligible' else None
            if reason:
                assert a['reason']==reason and a['plan'] is None,(r['label'],c['id'],a['reason'],reason)
                continue
            equity=D(1000)+sum((D(t['close_profit_abs']) for t in closed if t['close_timestamp']<a['time']),D(0))
            ef=fill(quote,d,True,slip);sf=fill(D(c['sl']),d,False,slip);tf=fill(D(c['tp']),d,False,slip)
            pf=quote*FUND*len(settlements(t,t+6*H));reserve=ef*RESERVE
            loss=d*(ef-sf)+FEE*(ef+sf)+reserve+pf
            capacity=equity/(ef/2+ef*FEE+ef*D('.005')+loss)
            q=(max(D(0),min(D(20)/loss,D(1000)/ef,capacity))/STEP).to_integral_value(rounding=ROUND_FLOOR)*STEP
            p=a['plan']
            for key,value in [('entry_fill',ef),('stop_fill',sf),('target_fill',tf),('planned_loss_per_btc',loss),('planned_funding_per_btc',pf),('q',q)]:near(p[key],value,'independent_plan_'+key)
            ratio=(d*(tf-ef)-FEE*(ef+tf)-reserve-pf)/loss
            expected_reason='minimum_order' if q<STEP or q*min(ef,sf,tf)<5 else 'cost_ratio' if ratio<1 else 'accepted'
            assert a['reason']==expected_reason,(r['label'],c['id'],a['reason'],expected_reason)
        if c['outcome'].startswith('cancel_') or c['outcome']=='expired':
            assert status(c,c['resolved_time'],end)==c['outcome'],(r['label'],c['id'],c['outcome'],status(c,c['resolved_time'],end))
    for t in ledger:
        c=candidates[t['candidate_id']];d=t['direction'];q=D(t['q']);entry=t['entry_time']
        assert c['t0']+r['delay']*H<=entry<c['t0']+3*H
        assert D(t['sl'])==D(c['sl']) and D(t['tp'])==D(c['tp']) and t['target_source']==c['target_source']
        assert status(c,entry,end)=='eligible'
        quote=BARS[INDEX[entry]]['open'];expected_exit=None
        # Verify only this observed trade's path, never generate another trade.
        for at in range(entry,min(end,entry+7*H),H):
            b=BARS[INDEX[at]];sl=D(t['sl']);tp=D(t['tp'])
            if d*(b['open']-sl)<=0:expected_exit=(at,at,b['open'],'GAP_SL')
            elif at>=entry+6*H:expected_exit=(at,at,b['open'],'TIMEOUT')
            elif b['low']<=sl if d==1 else b['high']>=sl:expected_exit=(at+H-1,at,sl,'SL')
            elif b['high']>=tp if d==1 else b['low']<=tp:expected_exit=(at if d*(b['open']-tp)>=0 else at+H-1,at,tp,'TP')
            if expected_exit:break
        assert expected_exit is not None
        when,through,raw_exit,reason=expected_exit
        assert (t['exit_time'],t['funding_through'],t['exit_path'])==(when,through,reason)
        near(t['raw_exit'],raw_exit,'earliest_fixed_exit_order')
        ef=quote if mode=='gross' else fill(quote,d,True,slip)
        xf=raw_exit if mode=='gross' else fill(raw_exit,d,False,slip)
        near(t['entry_fill'],ef,'unclipped_entry_pressure_fill');near(t['exit_fill'],xf,'unclipped_exit_pressure_fill')
        fund=D(0)
        if mode=='protocol':fund=-q*quote*FUND*len(settlements(entry,through))
        elif mode=='actual':fund=sum((-d*q*ACTUAL[f][0]*ACTUAL[f][1] for f in settlements(entry,through)),D(0))
        fees=D(0) if mode=='gross' else q*(ef+xf)*FEE
        reserve=D(0) if mode=='gross' else q*ef*RESERVE
        net=d*q*(xf-ef)-fees-reserve+fund
        for key,value in [('fee',fees),('reserve',reserve),('funding_signed',fund),('net',net),('native_profit_abs',net)]:near(t[key],value,'independent_ledger_'+key)
        n=native[t['candidate_id']]
        near(n['funding_fees'],fund,'native_funding_total');near(sum(D(o['funding_fee'] or 0) for o in n['orders']),fund,'native_funding_orders')
        near(n['profit_abs'],net,'native_closed_pnl')
        assert q%STEP==0 and D(t['planned_risk'])<=20 and D(t['planned_notional'])<=1000 and t['leverage']<=2
        assert (t in r['censored'])==(entry+6*H>end-H)
        checks['post_execution_tail_membership']+=1
        # A position present at hour open must suppress a contemporaneous valid raw signal.
        for at,s in actual_raw.items():
            if entry<at<=when and s['tp'] is not None:assert s['disposition']=='suppressed_active'
    near(r['principal_final_balance'],D(1000)+sum((D(t['net']) for t in r['trades']),D(0)),'principal_equity_reconciles')
    near(r['native_final_balance'],D(1000)+sum((D(t['close_profit_abs']) for t in closed),D(0)),'native_wallet_reconciles')
    assert hashlib.sha256(path.read_bytes()).hexdigest()==before
    profits=[D(t['net']) for t in r['trades']]
    wins=sum((x for x in profits if x>0),D(0));losses=-sum((x for x in profits if x<0),D(0))
    return dict(label=r['label'],trades=len(profits),censored=len(r['censored']),raw=len(actual_raw),
                candidates=len(candidates),net=str(sum(profits,D(0))),gross=str(sum((D(t['gross']) for t in r['trades']),D(0))),
                profit_factor=str(wins/losses) if losses else None,
                result_sha256=before,passed=True)


def main():
    summaries=[inspect_result(p) for p in sorted((APP/'results').glob('*/result.json'))]
    assert len(summaries)==25
    for gross_file in sorted((APP/'results').glob('gross_*/result.json')):
        gross=json.loads(gross_file.read_text())
        protocol=json.loads((gross_file.parent.parent/gross_file.parent.name.replace('gross_','protocol_',1)/'result.json').read_text())
        keys=('candidate_id','signal_time','direction','entry_time','exit_time','q','sl','tp','raw_exit','exit_path')
        assert [[t[k] for k in keys] for t in gross['trades']]==[[t[k] for k in keys] for t in protocol['trades']]
        checks['gross_protocol_identical_observed_trades_and_size']+=1
    out=dict(audited_at_utc=datetime.now(timezone.utc).isoformat(),method='Independent static verification of all 25 output ledgers; no portfolio simulation',
             checks=dict(checks),summaries=summaries,passed=True)
    p=ROOT/'historical_audit_evidence.json';p.write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(dict(path=str(p),runs=len(summaries),checks=sum(checks.values()),focus=[x for x in summaries if x['label'] in ['protocol_validation_D0','protocol_validation_D1','actual_funding_covered_D0','gross_validation_D0','gross_validation_D1']]),ensure_ascii=False))


if __name__=='__main__':main()
