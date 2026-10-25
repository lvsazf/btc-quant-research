import copy,sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from research_execution import describe_execution
class ResearchExecution(unittest.TestCase):
 def st(self,event='INITIALIZED'):
  return dict(event=event,desired_state='LONG',previous_state=None if event=='INITIALIZED' else 'LONG',incremental_orders=[],research_quantity=.007,research_stop=81106.5,signal_available_utc='2026-10-19T07:00:00+00:00',close=82800.4,lower=81719.4,supertrend_up=True)
 def cp(self):
  return {'ledger':{'q':.007,'stop':81106.5,'position':{'entry_time':1792364400000,'entry_signal_time':1792364400000,'entry_raw':81737.8,'entry_fill':81754.14756,'q':.007,'initial_stop':81106.5,'planned_risk':5.331}}}
 def test_initialization_not_entry(self):
  r=describe_execution('ST',self.st(),self.cp());self.assertEqual(r['action'],'INITIALIZE_RESEARCH_POSITION');self.assertFalse(r['new_entry']);self.assertEqual(r['new_orders'],[]);self.assertEqual(r['position']['entry_price'],81754.14756);self.assertIsNone(r['manual_execution']['entry_deadline'])
 def test_wait_no_new_order(self):
  r=describe_execution('ST',self.st('WAIT'),self.cp());self.assertEqual(r['action'],'MAINTAIN_LONG');self.assertFalse(r['new_entry'])
 def test_multiple_events_preserved(self):
  s=self.st('TRANSITIONS');s['incremental_orders']=[{'side':'sell','reason':'STOP_INTRABAR'},{'side':'buy','reason':'ENTRY'}]
  r=describe_execution('ST',s,self.cp());self.assertEqual(r['action'],'MULTIPLE_RESEARCH_EVENTS');self.assertEqual(r['new_orders'],s['incremental_orders']);self.assertTrue(r['new_entry'])
 def test_daily_missing_not_zero(self):
  s={'event':'WAIT','target_state':'LONG','previous_target_state':'LONG'};r=describe_execution('T1',s);self.assertIsNone(r['position']);self.assertEqual(r['action'],'MAINTAIN_LONG');self.assertIsNone(r['quantity']);self.assertIn('SMA50',r['exit_rule'])
 def test_unknown_not_wait(self):
  r=describe_execution('T1',{'event':'INSUFFICIENT_DATA'});self.assertEqual(r['action'],'UNKNOWN');self.assertFalse(r['new_entry'])
 def test_missing_checkpoint_not_invented(self):
  r=describe_execution('ST',self.st());self.assertIsNone(r['position']);self.assertIn('checkpoint',r['missing_research_fields'][0])
 def test_input_immutable(self):
  s=self.st();c=self.cp();old=copy.deepcopy((s,c));describe_execution('ST',s,c);self.assertEqual((s,c),old)
 def test_initialization_suppresses_historical_orders(self):
  s=self.st();s['incremental_orders']=[{'side':'buy'}];r=describe_execution('ST',s,self.cp());self.assertEqual(r['new_order_details'],[]);self.assertFalse(r['new_entry'])
 def test_checkpoint_mismatch_rejected(self):
  c=self.cp();c['ledger']['q']=.02
  with self.assertRaises(ValueError):describe_execution('ST',self.st(),c)
 def test_new_entry_details(self):
  s=self.st('ENTER');s['incremental_orders']=[{'side':'buy','ts':1792364400000,'signal_time':1792364400000,'fill':81754.14756,'q':.007,'stop':81106.5}]
  r=describe_execution('ST',s,self.cp());self.assertTrue(r['new_entry']);self.assertEqual(r['new_order_details'][0]['research_execution_price'],81754.14756);self.assertEqual(r['new_order_details'][0]['execution_time_utc'],'2026-10-18T23:00:00+00:00')

 def test_intrabar_stop_time_not_invented(self):
  s=self.st('EXIT');s['incremental_orders']=[{'side':'sell','reason':'STOP_INTRABAR','ts':1792331999999}]
  r=describe_execution('ST',s,self.cp());o=r['new_order_details'][0];self.assertIsNone(o['execution_time_utc']);self.assertIsNotNone(o['ledger_time_utc']);self.assertIsNone(o['signal_time_utc']);self.assertEqual(o['possible_execution_interval_start_utc'],'2026-10-18T13:00:00+00:00');self.assertEqual(o['possible_execution_interval_end_utc'],'2026-10-18T14:00:00+00:00')
