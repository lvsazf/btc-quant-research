"""Reconcile native result archives without trusting summary PnL."""
import collections
import csv
import json
import math
from datetime import datetime
from pathlib import Path
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parent
out = {}
rows = []
alignments = {}
for scenario in ('gross', 'net'):
    paths = sorted((ROOT / 'user_data/backtest_results').glob(f'{scenario}-*.zip'))
    assert len(paths) == 1, 'Select the intended result archive explicitly if there are multiple runs'
    path = paths[0]
    with ZipFile(path) as z:
        name = next(n for n in z.namelist() if n.endswith('.json') and not n.endswith('_config.json'))
        result = json.loads(z.read(name))['strategy']['SmokeHourlyResearch']
    trades = result['trades']
    for trade in trades:
        gross = (-1 if trade['is_short'] else 1) * (trade['close_rate'] - trade['open_rate']) * trade['amount']
        fees = (trade['open_rate'] * trade['fee_open'] + trade['close_rate'] * trade['fee_close']) * trade['amount']
        funding = trade['funding_fees']
        net = gross - fees + funding
        assert math.isclose(net, trade['profit_abs'], abs_tol=1e-7)
        notional = trade['amount'] * trade['open_rate']
        assert notional <= 1000 and notional * .0425 <= 20 and trade['leverage'] <= 2
        rows.append(dict(scenario=scenario, open=trade['open_date'], close=trade['close_date'],
                         side='short' if trade['is_short'] else 'long', amount=trade['amount'],
                         entry_notional=notional, leverage=trade['leverage'], planned_loss_budget_proxy=notional*.0425,
                         gross=gross, fees=fees, funding_signed=funding, net=net, exit_reason=trade['exit_reason']))
    selected = [r for r in rows if r['scenario'] == scenario]
    net_total = sum(r['net'] for r in selected)
    assert math.isclose(net_total, result['profit_total_abs'], abs_tol=1e-7)
    assert math.isclose(1000 + net_total, result['final_balance'], abs_tol=1e-7)
    out[scenario] = dict(result_zip=str(path.relative_to(ROOT)), trades=len(trades),
                         gross_price_pnl=sum(r['gross'] for r in selected),
                         trading_fees=sum(r['fees'] for r in selected),
                         signed_funding=sum(r['funding_signed'] for r in selected), net=net_total,
                         final_balance=result['final_balance'], max_drawdown_abs=result['max_drawdown_abs'],
                         max_entry_notional=max(r['entry_notional'] for r in selected),
                         max_planned_risk_proxy=max(r['planned_loss_budget_proxy'] for r in selected),
                         max_actual_loss=max(-r['net'] for r in selected),
                         exit_reasons=dict(collections.Counter(r['exit_reason'] for r in selected)),
                         funding_on_entry_boundary_count=sum(datetime.fromisoformat(t['open_date']).hour%8==0 for t in trades))
    natural = [r for r in selected if r['exit_reason'] != 'force_exit']
    out[scenario]['excluding_forced_end_exit'] = dict(completed_trades=len(natural), **{
        key: sum(r[key] for r in natural) for key in ('gross', 'fees', 'funding_signed', 'net')})
    alignments[scenario] = [(t['open_timestamp'], t['close_timestamp'], t['amount'], t['open_rate'], t['close_rate'], t['is_short']) for t in trades]
assert alignments['gross'] == alignments['net']
with (ROOT/'lookahead-results.csv').open() as f:
    lookahead_rows = list(csv.DictReader(f))
assert len(lookahead_rows) == 1
lookahead = lookahead_rows[0]
assert lookahead['strategy'] == 'SmokeHourlyResearch' and lookahead['has_bias'] == 'False'
assert int(lookahead['biased_entry_signals']) == int(lookahead['biased_exit_signals']) == 0
out['audit'] = dict(same_fills_in_both_runs=True, all_trade_pnl_reconciled=True,
                    native_funding_boundary='entry <= funding timestamp <= exit; differs from prior SR H1 entry-boundary exclusion',
                    does_not_include='spread, slippage, hourly poll/notification delay', strategy_adopted=False,
                    uses_all_historical_funding=False,
                    lookahead={'checked_signals':int(lookahead['total_signals']),
                               'detected_biased_entries':int(lookahead['biased_entry_signals']),
                               'detected_biased_exits':int(lookahead['biased_exit_signals']),
                               'limited_to_triggered_sample':True, 'diagnostic_capital_overridden_by_tool':True},
                    upstream_modified=bool((ROOT/'logs/upstream-clean-status.log').read_text().strip()))
(ROOT/'accounting-audit.json').write_text(json.dumps(out, indent=2)+'\n')
with (ROOT/'gross-net-trades.csv').open('w') as f:
    writer = csv.DictWriter(f, fieldnames=list(rows[0])); writer.writeheader(); writer.writerows(rows)
print(json.dumps(out, indent=2))
