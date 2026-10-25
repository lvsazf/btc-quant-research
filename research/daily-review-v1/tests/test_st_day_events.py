import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parents[1]))
import daily_review as d
from st_engine import simulate
from st_runtime import day_contribution
H=d.H
class DayEvents(unittest.TestCase):
 def test_boundary_funding_stop_and_next_flip_chunk_equal(self):
  bars=[dict(ts=i*H,open=100.,high=101.,low=99.,close=100.) for i in range(49)]
  bars[24].update(low=95.) # Existing holding charged funding then intrabar stop at day boundary.
  features={i*H:dict(daily_long=True,entry_a=i in (1,25),exit_a=i==40,atr=2.) for i in range(49)}
  rates={i*H:.0001 for i in range(0,49,8)};marks={x['ts']:dict(x) for x in bars}
  full=simulate(bars,features,'A',rates,marks,continuous=True)[-1]
  prior=None
  for bar in bars:
   stub=dict(bar,high=bar['open'],low=bar['open'],close=bar['open'])
   prior=simulate([stub],features,'A',rates,marks,continuous=True,previous=prior,boundary_only=True)[-1]
   prior=simulate([stub],features,'A',rates,marks,continuous=True,previous=prior,boundary_only=True)[-1]
   prior=simulate([bar],features,'A',rates,marks,continuous=True,previous=prior)[-1]
  self.assertEqual(full,prior)
  cp={'ledger':full};a=day_contribution(cp,H,24*H);b=day_contribution(cp,24*H,48*H);whole=day_contribution(cp,H,48*H)
  for k in ['marked_pnl','fees','slippage','funding']:self.assertAlmostEqual(a[k]+b[k],whole[k],places=10)
  stops=[x for x in b['orders'] if x['reason']=='STOP_INTRABAR'];self.assertEqual(len(stops),1)
  self.assertEqual(stops[0]['ts'],25*H-1)
  self.assertEqual(len([x for x in full['fundlog'] if x['ts']==24*H]),1)
  self.assertEqual([x['side'] for x in b['orders']],['sell','buy','sell'])
 def test_transition_receipts_do_not_hide_intermediate_stop(self):
  base=dict(previous_state='LONG',desired_state='LONG',event='TRANSITIONS',initialization_is_not_live_entry=False,incremental_orders=[dict(side='sell',reason='STOP'),dict(side='buy')])
  self.assertTrue(d.st_transition_check(base));self.assertFalse(d.st_transition_check(dict(base,event='WAIT')))
  self.assertFalse(d.st_transition_check(dict(base,incremental_orders=[dict(side='buy')])))
  self.assertTrue(d.st_transition_check(dict(previous_state=None,desired_state='LONG',event='INITIALIZED',incremental_orders=[],initialization_is_not_live_entry=True)))

class CheckpointCompleteness(unittest.TestCase):
 def fixture(self):
  cp=dict(version='test',closed_through_utc=d.datetime.datetime.fromtimestamp(2*H/1000,d.UTC).isoformat(),ledger=dict(status='COMPLETE',curve=[dict(ts=H,equity=1000),dict(ts=2*H,equity=1001)],next_bar_ts=2*H,boundary_processed=2*H,orders=[],fundlog=[]))
  signal=dict(summary=dict(status='COMPLETE',end=2*H),previous_state=None,desired_state='CASH',event='INITIALIZED',incremental_orders=[],initialization_is_not_live_entry=True)
  return cp,signal
 def run_checkpoint(self,cp,signal):
  from unittest.mock import patch
  with patch.object(d,'START',0),patch.object(d,'verify_st_source',return_value=cp),patch.object(d,'body',return_value=signal):
   return d.st_checkpoint_review(dict(round_id='r',files={'run/st_checkpoint.json':{}}),H,2*H)
 def test_complete_curve_is_bounded(self):
  cp,s=self.fixture();self.assertTrue(self.run_checkpoint(cp,s)['complete_day'])
 def test_gap_and_bad_summary_cannot_claim_complete(self):
  cp,s=self.fixture();cp['ledger']['curve']=cp['ledger']['curve'][1:]
  with self.assertRaisesRegex(ValueError,'curve gap'):self.run_checkpoint(cp,s)
  cp,s=self.fixture();s['summary']['end']=3*H
  with self.assertRaisesRegex(ValueError,'summary cutoff'):self.run_checkpoint(cp,s)
