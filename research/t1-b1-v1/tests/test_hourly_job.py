import unittest,sys,tempfile,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
class HourlyJob(unittest.TestCase):
 def api(self):
  self.assertTrue((ROOT/'hourly_job.py').exists(),'hourly wrapper missing')
  import hourly_job
  return hourly_job
 def test_stable_unique_round(self):
  m=self.api();self.assertEqual(m.round_key('a','2026-10-16T07:03:00Z'),m.round_key('a','2026-10-16T15:03:00+08:00'));self.assertNotEqual(m.round_key('a','2026-10-16T07:03:00Z'),m.round_key('b','2026-10-16T07:03:00Z'))
 def test_duplicate_does_not_run(self):
  m=self.api()
  with tempfile.TemporaryDirectory() as d:
   p=Path(d);p.joinpath('state.json').write_text(json.dumps({'status':'COMPLETE'}))
   self.assertEqual(m.previous_run(p)['status'],'COMPLETE')
 def test_interruption_is_not_success(self):
  m=self.api()
  with tempfile.TemporaryDirectory() as d:
   p=Path(d);p.joinpath('state.json').write_text(json.dumps({'status':'RUNNING'}))
   self.assertEqual(m.previous_run(p)['status'],'INTERRUPTED')
 def test_missing_rules_not_actionable(self):
  m=self.api();r=m.decision({'adopted':False,'status':'RESEARCH_ONLY_NOT_ADOPTED','native_signal_checks':{}})
  self.assertEqual(r['decision'],'NO_EXECUTABLE_DECISION');self.assertFalse(r['actionable'])
 def test_failure_not_wait(self):
  m=self.api();r=m.decision({'status':'BLOCKED_RESEARCH_NO_SIGNAL'});self.assertEqual(r['decision'],'ERROR_NO_DECISION')
 def test_unexpected_adoption_rejected(self):
  m=self.api()
  with self.assertRaises(ValueError):m.decision({'adopted':True,'status':'RESEARCH_ONLY_NOT_ADOPTED'})
 def test_package_restore(self):
  m=self.api()
  with tempfile.TemporaryDirectory() as d:
   p=Path(d);(p/'x.json').write_text('{"simulation":"local test only"}')
   b=m.bundle_files({'x.json':p/'x.json'});self.assertEqual(b['x.json']['bytes'],len(b['x.json']['content'].encode()))
 def test_midrun_drift_rejected(self):
  m=self.api();self.assertTrue(hasattr(m,'check_runtime_identity'),'drift check missing')
  with self.assertRaises(ValueError):m.check_runtime_identity({'manifest_sha256':'a'},{'manifest_sha256':'b'})
 def test_concurrent_round_is_not_restarted(self):
  import fcntl,subprocess,datetime
  m=self.api()
  with tempfile.TemporaryDirectory() as d:
   t='2026-10-16T00:00:00Z';p=Path(d)/m.round_key('SIMULATION_LOCK_ONLY',t);p.mkdir()
   with (p/'run.lock').open('w') as f:
    fcntl.flock(f,fcntl.LOCK_EX|fcntl.LOCK_NB)
    r=subprocess.run([sys.executable,str(ROOT/'hourly_job.py'),'--task-id','SIMULATION_LOCK_ONLY','--scheduled-utc',t,'--storage-root',d,'--history-root',d],capture_output=True,text=True)
    self.assertEqual(json.loads(r.stdout)['status'],'ALREADY_RUNNING');self.assertFalse((p/'run').exists())
