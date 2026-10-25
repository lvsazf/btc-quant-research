import unittest,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from daily_review import day_window,continuous_cost_end,day_contribution,merge_rows
class DailyTests(unittest.TestCase):
 def test_beijing_boundary(self):
  start,end=day_window('2026-10-16');self.assertEqual(end-start,86400000)
  import datetime
  self.assertEqual(datetime.datetime.fromtimestamp(start/1000,datetime.timezone.utc).isoformat(),'2026-10-15T16:00:00+00:00')
 def test_gap_stops_not_zero(self):
  h=3600000;self.assertEqual(continuous_cost_end([{'ts':0},{'ts':h}],{0:{}},{0:0.1}),h)
 def test_missing_funding_stops(self):self.assertEqual(continuous_cost_end([{'ts':0}],{0:{}},{}),0)
 def test_conflicting_history_rejected(self):
  with self.assertRaises(ValueError):merge_rows([{ 'ts':1,'close':2}], [{'ts':1,'close':3}])
 def test_no_daily_liquidation(self):
  c=[{'ts':1,'equity':1000},{'ts':2,'equity':1010},{'ts':3,'equity':1020}]
  t=[{'ts':3,'fee':4,'slippage':2,'reason':'terminal_liquidation'}]
  d=day_contribution(c,t,[],1,3);self.assertEqual(d['marked_pnl'],20);self.assertEqual(d['fees'],0)
 def test_missing_day_not_zero(self):self.assertIsNone(day_contribution([],[],[],1,3)['marked_pnl'])
 def test_candidate_requires_frozen_evidence_and_hash(self):
  # The arbitrary-candidate API was replaced by the frozen evidence registry.
  # Missing evidence and mismatched artifact hashes must still be rejected.
  from candidate_registry import validate_protocol,verify_refs
  import tempfile
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'candidate.py';p.write_text('')
   with self.assertRaisesRegex(ValueError,'protocol: missing'):
    validate_protocol({},Path(d),'2026-10-25T00:00:00Z')
   with self.assertRaisesRegex(ValueError,'artifact hash mismatch'):
    verify_refs([{'path':'candidate.py','sha256':'0'*64}],Path(d))
   verify_refs([{'path':'candidate.py','sha256':'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855'}],Path(d))
 def test_timestamp_not_scheduled_proof(self):
  from daily_review import trigger_source
  self.assertEqual(trigger_source({'round_id':'x','scheduled_utc':'2026-10-16T07:03:00Z'},[]),'UNKNOWN_NOT_INFERRED_FROM_TIMESTAMP')
 def test_invalid_ledger_not_complete(self):
  from daily_review import review_status
  self.assertEqual(review_status(['T1'],5,5),'INVALID_BACKTEST_PARTIAL')
 def test_evidence_issues_nonzero(self):
  from daily_review import review_status,exit_code
  for issue in ['INVALID_INPUT_ARCHIVES','REPLAY_MISMATCH_OR_UNSUPPORTED_VERSION']:
   status=review_status([],5,5,[issue]);self.assertEqual(status,'REVIEW_WITH_EVIDENCE_ISSUES');self.assertEqual(exit_code(status),2)
 def test_observations_not_inferred_from_backtest(self):
  from daily_review import observation_coverage
  self.assertFalse(observation_coverage([],0,86400000)['full_day_scheduled_observations'])
  rows=[dict(scheduled_utc=__import__('datetime').datetime.fromtimestamp((i*3600000+180000)/1000,__import__('datetime').timezone.utc).isoformat(),trigger_source='SCHEDULED_EXTERNALLY_VERIFIED') for i in range(24)]
  self.assertTrue(observation_coverage(rows,0,86400000)['full_day_scheduled_observations'])
 def test_terminal_receipt_required_and_bound(self):
  from daily_review import terminal_receipt
  import tempfile,json
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'archive.json'
   with self.assertRaises(ValueError):terminal_receipt(p,{'round_id':'x'},'hash')
   for state in [{'status':'FAILED'},{'status':'COMPLETE','round_id':'x','archive_sha256':'wrong'}]:
    (p.parent/'state.json').write_text(json.dumps(state))
    with self.assertRaises(ValueError):terminal_receipt(p,{'round_id':'x'},'hash')
   (p.parent/'state.json').write_text(json.dumps({'status':'COMPLETE','round_id':'x','archive_sha256':'hash'}))
   self.assertEqual(terminal_receipt(p,{'round_id':'x'},'hash')['state']['status'],'COMPLETE')
