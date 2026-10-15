"""Pre-specified reporting and adoption gates; does not change trading decisions."""
from collections import Counter,defaultdict
from datetime import datetime,timezone
from pathlib import Path
import csv,json,statistics
from sr_support import D,H,execution_fill,funding_cashflow
from run_research import ROOT,load_history,save,ms

def drawdown(curve):
    peak=1000.;absmax=0.;pctmax=0.
    for equity in curve:
        peak=max(peak,equity);absmax=max(absmax,peak-equity);pctmax=max(pctmax,(peak-equity)/peak)
    return absmax,pctmax

def metrics(trades):
    profits=[t['net'] for t in sorted(trades,key=lambda t:t['exit_time'])]
    wins=sum(x for x in profits if x>0);losses=-sum(x for x in profits if x<0)
    curve=[];equity=1000.;streak=0;longest=0
    for p in profits:
        equity+=p;curve.append(equity);streak=streak+1 if p<0 else 0;longest=max(longest,streak)
    dd,ddpct=drawdown(curve)
    fields=['gross','execution_pressure','fee','reserve','funding_signed','net']
    out={k:sum(t[k] for t in trades) for k in fields}
    out.update(completed_trades=len(trades),win_rate=sum(p>0 for p in profits)/len(profits) if profits else None,
               profit_factor=wins/losses if losses else None,profit_factor_no_losses=bool(profits and not losses),
               mean_net=statistics.mean(profits) if profits else None,median_net=statistics.median(profits) if profits else None,
               max_losing_streak=longest,realized_max_drawdown=dd,realized_max_drawdown_pct=ddpct,
               largest_loss=max([0]+[-p for p in profits]),final_balance=1000+sum(profits))
    for key in ['planned_risk','planned_ratio','actual_R','entry_notional','planned_notional','leverage','margin']:
        vals=[t[key] for t in trades]
        out[key+'_distribution']={'min':min(vals),'median':statistics.median(vals),'max':max(vals)} if vals else None
    return out

def gates(total,quarters):
    tests={'net_positive':total['net']>0,'profit_factor_above_one':total['profit_factor'] is not None and total['profit_factor']>1,
           'at_least_30_trades':total['completed_trades']>=30,
           'first_quarter_10_trades':quarters[0]['completed_trades']>=10,
           'second_quarter_10_trades':quarters[1]['completed_trades']>=10,
           'first_quarter_net_positive':quarters[0]['net']>0,'second_quarter_net_positive':quarters[1]['net']>0}
    return {'tests':tests,'all_pass':all(tests.values())}

def marked_curve(r,cache,actual):
    start,end=ms(r['start']),ms(r['end']);curve=[];trades=r['trades']
    for t in range(start,end,H):
        b=cache['bars'][t];marktime=t+H-1
        equity=1000+sum(x['net'] for x in trades if x['exit_time']<=marktime)
        for x in trades:
            if x['entry_time']<=t and x['exit_time']>marktime:
                q=D(x['q']);entry=D(x['entry_fill']);d=x['direction'];mode=r['mode']
                fill=execution_fill(b['close'],d,False,D(r['slippage']),mode)
                fee=q*(entry+fill)*(D(0) if mode=='gross' else D('.0006'))
                reserve=q*entry*(D(0) if mode=='gross' else D('.0001'))
                funding=funding_cashflow(x['entry_time'],t,d,q,D(x['entry_quote']),mode,actual)
                equity+=float(d*(fill-entry)*q-fee-reserve+funding)
        curve.append({'time':t+H,'principal_equity_marked':equity})
    dd,pct=drawdown([x['principal_equity_marked'] for x in curve])
    return {'max_drawdown':dd,'max_drawdown_pct':pct,'curve':curve,
            'scope':'Principal uncensored trades only, after all entry/exit stresses, fees, reserve and actual held funding; last H1 close mark. Native unadjusted wallet.total is not MTM.'}

def summarize():
    cache,actual=load_history();summary={};flat=[];all_ledgers=[]
    for p in sorted((ROOT/'results').glob('*/result.json')):
        r=json.loads(p.read_text());trades=r['trades'];s=metrics(trades)
        s['raw_signals']=len(r['raw_signals']);s['raw_dispositions']=dict(Counter(x['disposition'] for x in r['raw_signals']))
        s['candidates']=len(r['candidates']);s['candidate_outcomes']=dict(Counter(x['outcome'] for x in r['candidates']))
        s['attempt_reasons']=dict(Counter(a['reason'] for c in r['candidates'] for a in c['attempts']))
        s['censored']=len(r['censored']);s['exit_paths']=dict(Counter(t['exit_path'] for t in trades))
        s['mode']=r['mode'];s['start']=r['start'];s['end']=r['end'];s['native_accounting_reconciled']=r['native_accounting_reconciled']
        s['native_final_balance']=r['native_final_balance']
        mark=marked_curve(r,cache,actual);s['marked_max_drawdown']=mark['max_drawdown'];s['marked_max_drawdown_pct']=mark['max_drawdown_pct']
        save(p.parent/'principal_marked_equity.json',mark)
        groups=defaultdict(list)
        for t in trades:
            month=datetime.fromtimestamp(t['entry_time']/1000,tz=timezone.utc).strftime('%Y-%m')
            groups[month].append(t)
            all_ledgers.append({'run':r['label'],**t})
        s['months']={k:metrics(v) for k,v in groups.items()}
        s['directions']={side:metrics([t for t in trades if t['direction']==d]) for side,d in [('long',1),('short',-1)]}
        if '_validation_' in r['label']:
            mid=ms('2026-07-10T18:00:00Z')
            s['quarters']=[metrics([t for t in trades if t['entry_time']<mid]),metrics([t for t in trades if t['entry_time']>=mid])]
        summary[r['label']]=s
        flat.append({'run':r['label'],**{k:s[k] for k in ['completed_trades','gross','execution_pressure','fee','reserve','funding_signed','net','profit_factor','win_rate','realized_max_drawdown','marked_max_drawdown','max_losing_streak','largest_loss','censored']}})
    adoption={name:gates(summary['protocol_validation_'+name],summary['protocol_validation_'+name]['quarters']) for name in ['D0','D1']}
    adoption['stress']={name:summary['protocol_validation_'+name+'_SLIP5BP']['net']>=0 for name in ['D0','D1']}
    adoption['passed']=all(adoption[x]['all_pass'] for x in ['D0','D1']) and all(adoption['stress'].values())
    adoption['decision']='REJECT_FROZEN_CANDIDATE' if not adoption['passed'] else 'SCREEN_PASSED_NOT_ADOPTED'
    adoption['count_evidence_insufficient']=any(not adoption[x]['tests']['at_least_30_trades'] for x in ['D0','D1'])
    adoption['unseen_holdout']=False
    save(ROOT/'results_summary.json',summary);save(ROOT/'adoption_result.json',adoption)
    for name,rows in [('results_table.csv',flat),('all_trades.csv',all_ledgers)]:
        with (ROOT/name).open('w') as f:
            w=csv.DictWriter(f,fieldnames=rows[0].keys());w.writeheader();w.writerows(rows)
    print(json.dumps(adoption,indent=2));print('Principal table rows:',len(flat),'all ledger rows:',len(all_ledgers))

if __name__=='__main__':summarize()
