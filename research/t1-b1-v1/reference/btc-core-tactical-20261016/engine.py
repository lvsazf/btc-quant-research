"""Isolated, causal, fully collateralized perpetual research ledger; not trading code."""
import csv, json, math, hashlib, sys, datetime, subprocess
from pathlib import Path
H=3600000
HERE=Path(__file__).resolve().parent
FEE=.0006
STEP=.0001

def floorq(q): return round(math.floor((q+1e-12)/STEP)*STEP, 4)

def signal(close, entry, sale, out_since, close_ts, variant, held):
    if variant['name']=='HOLD': return None
    if held: return 'sell' if close>=entry*(1+variant['gain']) else None
    if close<=sale*(1-variant['dip']): return 'buy_dip'
    if close>=sale*(1+variant['chase']): return 'buy_chase'
    if close_ts-out_since>=variant['timeout_hours']*H: return 'buy_timeout'
    return None

def simulate(bars, variant, funding, marks, slip=.0002, delay=0, save=None):
    assert bars and all(b['ts']-a['ts']==H for a,b in zip(bars,bars[1:]))
    cash=1000.; core=tac=0.; budget=0.; original_tac=0.; entry=sale=0.; out_since=None; pending=None
    trades=[]; costs=[]; curve=[]; cycles=[]; last_sale_q=0.; peak=1000.; peak_time=bars[0]['ts']; maxdd=0.; maxuw=0.; exposure=[]; mincash=1000.; invalid=None; stopped_at=None; failure_headroom=None
    def trade(t,side,q,raw,reason):
        nonlocal cash
        fill=raw*(1+slip if side=='buy' else 1-slip)
        fee=q*fill*FEE
        amount=q*fill
        cash+=(-amount-fee) if side=='buy' else amount-fee
        trades.append(dict(ts=t,side=side,q=q,raw=raw,fill=fill,fee=fee,slippage=q*abs(fill-raw),reason=reason,cash=cash))
        return amount-fee if side=='sell' else amount+fee
    for i,b in enumerate(bars):
        t=b['ts']; raw=b['open']
        # At settlement existing inventory pays first; no retrospective funding on new entries.
        if t in funding and core+tac>0:
            rate=funding[t]; mark=marks[t]['open'] if marks is not None else raw
            paid=(core+tac)*mark*rate; cash-=paid
            costs.append(dict(ts=t,rate=rate,mark=mark,q=core+tac,paid=paid))
            if cash < -1e-8:
                invalid='INVALID_NO_LEVERAGE: funding exhausted non-notional headroom'; stopped_at=t; failure_headroom=cash; mincash=min(mincash,cash); break
        if i==0:
            total=floorq(900/(raw*(1+slip)*(1+FEE)))
            if variant['name']=='HOLD': core=total
            else: tac=floorq(.2*total); core=round(total-tac,4); original_tac=tac
            trade(t,'buy',total,raw,'initial'); entry=raw
        elif pending and t>=pending[0]:
            action=pending[1]; pending=None
            if action=='sell':
                assert tac>0
                last_sale_q=tac; budget=trade(t,'sell',tac,raw,'tactical_profit'); tac=0.; sale=raw; out_since=t
                cycles.append(dict(sold_at=t,sale_raw=raw,sold_q=last_sale_q,max_missed_upside=0.,reentry_at=None))
            else:
                assert tac==0 and out_since is not None
                # Segregated proceeds cap: no borrowing, core/reserve cannot finance repurchase.
                tac=floorq(min(last_sale_q,budget/(raw*(1+slip)*(1+FEE)),cash/(raw*(1+slip)*(1+FEE))))
                if tac>=STEP:
                    spent=trade(t,'buy',tac,raw,action); assert spent<=budget+1e-7; budget-=spent
                    cycles[-1].update(reentry_at=t,reentry_raw=raw,reentry_q=tac,raw_reentry_gap_usdt=last_sale_q*(raw-sale),reason=action)
                    entry=raw; out_since=None
                else: invalid='INVALID_MIN_QUANTITY: segregated tactical proceeds exhausted'; stopped_at=t; failure_headroom=cash; break
        assert cash>=-1e-7
        mincash=min(mincash,cash)
        if out_since is not None:
            cycles[-1]['max_missed_upside']=max(cycles[-1]['max_missed_upside'],last_sale_q*max(0,b['close']-sale))
        # Mark close for actual-window liquidation-equity path; last close otherwise is explicitly a proxy.
        px=marks[t]['close'] if marks is not None else b['close']
        eq=cash+(core+tac)*px
        peak=max(peak,eq)
        if eq>=peak: peak_time=t+H
        maxuw=max(maxuw,(t+H-peak_time)/H)
        dd=1-eq/peak; maxdd=max(maxdd,dd)
        exposure.append((core+tac)*px/eq if eq>0 else float('inf'))
        curve.append(dict(ts=t+H,equity=eq,cash_headroom=cash,core=core,tactical=tac,mark=px,drawdown=dd))
        # Does NOT know future open. A delayed action is kept fixed until scheduled execution.
        if not pending and i<len(bars)-1:
            action=signal(b['close'],entry,sale,out_since,t+H,variant,tac>0)
            if action: pending=(t+(1+delay)*H,action)
    # Equal end liquidation in all variants. Last-close proxy fill, not live execution.
    if not invalid:
        last=bars[-1]; trade(last['ts']+H,'sell',core+tac,last['close'],'terminal_liquidation'); core=tac=0.
        final=cash; maxdd=max(maxdd,1-final/peak)
    else: final=None
    fee=sum(x['fee'] for x in trades); slipcost=sum(x['slippage'] for x in trades); fund=sum(x['paid'] for x in costs)
    # Independent complete cashflow reconciliation, not derived from mutable cash.
    independent=1000+sum((1 if x['side']=='sell' else -1)*x['q']*x['fill']-x['fee'] for x in trades)-fund
    assert abs(independent-cash)<1e-7
    if not invalid: assert abs(sum((1 if x['side']=='buy' else -1)*x['q'] for x in trades))<1e-8
    result=dict(name=variant['name'],status=invalid or 'COMPLETE',stopped_at=stopped_at,failure_headroom=failure_headroom,metrics_are_partial=bool(invalid),last_valued_at=curve[-1]['ts'] if curve else None,start=bars[0]['ts'],end=bars[-1]['ts']+H,hours=len(curve),final_equity=final,pnl=None if final is None else final-1000,return_pct=None if final is None else (final/1000-1)*100,max_hourly_drawdown_pct=maxdd*100,max_underwater_hours=maxuw,unrecovered_at_end=(final if final is not None else curve[-1]['equity'])<peak,fees=fee,slippage=slipcost,funding=fund,turnover=sum(x['q']*x['raw'] for x in trades),mean_exposure_pct=sum(exposure)/len(exposure)*100,max_exposure_pct=max(exposure)*100,min_cash_headroom=mincash,tactical_sales=len(cycles),dip_reentries=sum(c.get('reason')=='buy_dip' for c in cycles),chase_reentries=sum(c.get('reason')=='buy_chase' for c in cycles),timeout_reentries=sum(c.get('reason')=='buy_timeout' for c in cycles),unclosed_tactical_episodes=sum(c['reentry_at'] is None for c in cycles),positive_reentry_gap_usdt=sum(max(0,c.get('raw_reentry_gap_usdt',0)) for c in cycles),signed_reentry_gap_usdt=sum(c.get('raw_reentry_gap_usdt',0) for c in cycles),max_missed_upside_episode_usdt=max([c['max_missed_upside'] for c in cycles]+[0]),ledger_error=independent-cash)
    if save:
        save.mkdir(parents=True,exist_ok=False)
        for name,rows in [('trades',trades),('funding',costs),('curve',curve),('cycles',cycles)]:
            (save/(name+'.json')).write_text(json.dumps(rows,indent=2))
        (save/'summary.json').write_text(json.dumps(result,indent=2))
    return result,curve,trades,costs

def load_csv(path):
    rows=list(csv.DictReader(path.open())); return [{k:(int(v) if k=='ts' else float(v) if k!='symbol' else v) for k,v in row.items()} for row in rows]

def main():
    base=Path('/workspace/shared/btc-quant-research-20261010')
    paths=[base/'v2/data/ohlcv_1h.csv',base/'data/ohlcv_1h.csv',base/'data/btcusdt_usdt_futures_funding.csv',base/'data/btcusdt_usdt_futures_mark_1h_funding_window.csv']
    bars=load_csv(paths[0])+load_csv(paths[1]); rates={r['ts']:r['fundingRate'] for r in load_csv(paths[2])}; marks={r['ts']:r for r in load_csv(paths[3])}
    assert len({b['ts'] for b in bars})==len(bars) and all(b['ts']-a['ts']==H for a,b in zip(bars,bars[1:]))
    assert len(rates)==270 and all(t in rates for t in range(min(rates),max(rates)+1,8*H))
    assert all(t in marks for t in range(min(marks),max(marks)+1,H)) and all(t in marks for t in rates)
    protocol=json.loads((HERE/'protocol.json').read_text()); records=[]
    manifest=dict(created_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),protocol_sha256=hashlib.sha256((HERE/'protocol.json').read_bytes()).hexdigest(),engine_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),python=sys.executable,python_version=sys.version,repo_head=subprocess.check_output(['git','-C','/workspace/shared/btc-quant-worktree','rev-parse','HEAD'],text=True).strip(),data=[dict(path=str(p),sha256=hashlib.sha256(p.read_bytes()).hexdigest(),rows=len(load_csv(p))) for p in paths],actual_rate_count=len(rates),actual_start=min(rates),actual_end=max(rates),actual_mark_count=len(marks),funding_and_mark_gaps=0,full_history_hours=len(bars),all_history_already_exposed=True,engine='new isolated causal ledger, NOT native Freqtrade backtester; executed in cloud quant venv',upstream_source='/workspace/shared/btc-quant-worktree')
    (HERE/'manifest.json').write_text(json.dumps(manifest,indent=2))
    actual=[b for b in bars if min(rates)<=b['ts']<=max(rates)]
    # Frozen four execution scenarios. All are reported, none selected by return.
    for label,slip,delay in [('base',.0002,0),('slip5bp',.0005,0),('delay1h',.0002,1),('stress_both',.0005,1)]:
        for v in protocol['variants']:
            r,*_=simulate(actual,v,rates,marks,slip,delay,HERE/'results'/f'actual_{label}_{v["name"]}'); r.update(window='actual',scenario=label); records.append(r)
    windows=[('full',bars),('year1',bars[:8784]),('year2',bars[8784:17544]),('year3',bars[17544:])]
    for w,bs in windows:
        for rate in [.0001,.0002]:
            fund={b['ts']:rate for b in bs if b['ts']%(8*H)==0}
            for v in protocol['variants']:
                label=f'assumed_{int(rate*1e4)}bp'; r,*_=simulate(bs,v,fund,None,.0002,0,HERE/'results'/f'{w}_{label}_{v["name"]}');r.update(window=w,scenario=label);records.append(r)
    # Compare only complete, identically-windowed/scenario matched groups.
    for r in records:
        bm=next(x for x in records if x['window']==r['window'] and x['scenario']==r['scenario'] and x['name']=='HOLD')
        r['relative_pnl_usdt']=r['pnl']-bm['pnl'] if r['pnl'] is not None and bm['pnl'] is not None else None
    (HERE/'results.json').write_text(json.dumps(records,indent=2))
    for r in records: print(r['window'],r['scenario'],r['name'],r['status'],'PnL',r['pnl'],'relative',r['relative_pnl_usdt'],'DD',r['max_hourly_drawdown_pct'])
if __name__=='__main__': main()
