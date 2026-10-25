import sys, unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parents[1]))
import daily_review as d
class IsolationTests(unittest.TestCase):
 def test_failure_is_recorded_without_raising(self):
  report={}
  self.assertIsNone(d.run_branch(report,'st',lambda:1/0))
  self.assertEqual(report['branches']['st']['status'],'BLOCKED')
  self.assertEqual(d.run_branch(report,'backtest',lambda:7),7)
 def test_st_pre_activation_slots_are_not_missing(self):
  start,end=d.day_window('2026-10-18')
  c=d.st_observation_coverage([],start,end)
  self.assertEqual(c['expected_scheduled_slots'],0)
  self.assertEqual(c['pre_activation_slots'],24)
  self.assertFalse(c['full_day_scheduled_observations'])
  self.assertEqual(c['coverage_status'],'NOT_APPLICABLE_BEFORE_ACTIVATION')
 def test_st_activation_day_has_nine_slots(self):
  start,end=d.day_window('2026-10-19')
  c=d.st_observation_coverage([],start,end)
  self.assertEqual(c['expected_scheduled_slots'],9)
  self.assertEqual(c['pre_activation_slots'],15)
 def test_day_costs_are_half_open_and_additive(self):
  curve=[dict(ts=t,equity=e) for t,e in [(0,1000),(24,1010),(48,1005)]]
  trades=[dict(ts=t,fee=1,slippage=2,reason=r) for t,r in [(0,'entry'),(24,'stop'),(48,'entry'),(23,'terminal_liquidation')]]
  funds=[dict(ts=t,paid=3) for t in [0,24,48]]
  a=d.day_contribution(curve,trades,funds,0,24);b=d.day_contribution(curve,trades,funds,24,48);whole=d.day_contribution(curve,trades,funds,0,48)
  for k in ['marked_pnl','fees','slippage','funding']:self.assertEqual(a[k]+b[k],whole[k])
  self.assertEqual(a['fees'],1);self.assertEqual(b['fees'],1)

class MainIsolationTests(unittest.TestCase):
 def run_main(self,backtest_failure=False,st_failure=False):
  import tempfile,json
  from unittest.mock import patch
  with tempfile.TemporaryDirectory() as tmp:
   out=Path(tmp)/'out'
   p=dict(round_id='r',scheduled_utc='2026-10-19T07:03:00+00:00',files={'run/st_checkpoint.json':{}})
   result=dict(version=d.VERSION,asof_utc='2026-10-19T07:04:00+00:00',closed_data_through_utc='2026-10-19T07:00:00+00:00')
   bt=dict(results={},valid_end=d.day_window('2026-10-19')[1],desired_end=d.day_window('2026-10-19')[1])
   row=dict(round_id='r',scheduled_utc=p['scheduled_utc'],trigger_source='SCHEDULED_EXTERNALLY_VERIFIED',status='MATCH',st_research=dict(status='SIGNAL_MATCH_LEDGER_RECEIPT_VERIFIED'))
   with patch.object(sys,'argv',['daily','--date','2026-10-19','--round','x','--history-root','x','--output',str(out)]),patch.object(d,'verify_runtime',return_value={}),patch.object(d,'package',return_value=(p,'hash')),patch.object(d,'terminal_receipt',return_value={}),patch.object(d,'body',return_value=result),patch.object(d,'fixed_backtest',side_effect=ValueError('cost gap') if backtest_failure else None,return_value=bt),patch.object(d,'st_checkpoint_review',side_effect=ValueError('ST gap') if st_failure else None,return_value={'complete_day':True}),patch.object(d,'reconcile_round',return_value=row):
    d.main()
   return json.loads((out/'report.json').read_text())
 def test_cost_failure_keeps_st_and_hourly_checks(self):
  r=self.run_main(backtest_failure=True)
  self.assertEqual(r['status'],'BLOCKED_PARTIAL');self.assertTrue(r['st_research']['complete_day']);self.assertEqual(r['round_comparisons'][0]['status'],'MATCH')
 def test_st_failure_keeps_backtest_and_hourly_checks(self):
  r=self.run_main(st_failure=True)
  self.assertEqual(r['branches']['fixed_backtest']['status'],'COMPUTED');self.assertEqual(r['status'],'REVIEW_WITH_EVIDENCE_ISSUES');self.assertEqual(r['round_comparisons'][0]['status'],'MATCH')
 def test_runtime_mismatch_leaves_failure_bundle_and_never_calculates(self):
  import tempfile,json
  from unittest.mock import patch
  with tempfile.TemporaryDirectory() as tmp:
   out=Path(tmp)/'out'
   with patch.object(sys,'argv',['daily','--date','2026-10-18','--round','x','--history-root','x','--output',str(out)]),patch.object(d,'verify_runtime',side_effect=ValueError('locked hash mismatch')),patch.object(d,'fixed_backtest') as compute:
    self.assertEqual(d.main(),1);compute.assert_not_called()
   r=json.loads((out/'report.json').read_text());self.assertEqual(r['status'],'BLOCKED_PARTIAL');self.assertFalse(r['calculations_started']);d.package(out/'google-evidence.json')

class DueSlots(unittest.TestCase):
 def test_future_st_slots_are_pending_not_missing(self):
  start,end=d.day_window('2026-10-19');asof=int(d.datetime.datetime.fromisoformat('2026-10-19T07:10:00+00:00').timestamp()*1000)
  row=dict(scheduled_utc='2026-10-19T07:03:00+00:00',trigger_source='SCHEDULED_EXTERNALLY_VERIFIED')
  c=d.st_observation_coverage([row],start,end,asof)
  self.assertEqual(c['due_scheduled_slots'],1);self.assertEqual(c['completed_due_scheduled_slots'],1);self.assertEqual(c['future_scheduled_slots'],8);self.assertEqual(c['missing_scheduled_slots_utc_ms'],[])
  self.assertTrue(c['due_slots_complete']);self.assertFalse(c['calendar_day_full_st_observations'])
 def test_unobserved_due_slot_is_really_missing(self):
  start,end=d.day_window('2026-10-19');asof=int(d.datetime.datetime.fromisoformat('2026-10-19T08:10:00+00:00').timestamp()*1000)
  c=d.st_observation_coverage([],start,end,asof);self.assertEqual(len(c['missing_scheduled_slots_utc_ms']),2);self.assertEqual(c['future_scheduled_slots'],7)
