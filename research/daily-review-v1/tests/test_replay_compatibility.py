import unittest,sys,copy
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parents[1]))
import daily_review as d
class ReplayCompatibility(unittest.TestCase):
 def fixture(self):
  names=['run_research.py','rules.py','signal_report.py','user_data/strategies/FrozenDailyResearch.py']
  files={}
  for n in names:
   raw=(d.BASE/'reference/st-approved/run_research_v3.txt').read_bytes() if n=='run_research.py' else (d.BASE/n).read_bytes()
   if n=='run_research.py':raw=raw.replace(b"kLineType='mark'",b"kLineType='MARK'")
   files['source/'+n]=dict(content=raw.decode(),sha256=d.sha(raw))
  raw=(Path(__file__).parent/'fixtures/runtime_v3_before_mark_fix.json').read_bytes()
  files['source/runtime_manifest.json']=dict(content=raw.decode(),sha256=d.sha(raw))
  return dict(files=files),names
 def test_known_only_fetch_diff_allowed(self):
  p,n=self.fixture();x=d.replay_compatibility(p,n)
  self.assertIn(x['status'],('KNOWN_MARK_FETCH_ONLY','KNOWN_ST_RESEARCH_EXTENSION'));self.assertEqual(x['changed_files'],['run_research.py'])
 def test_unknown_run_hash_rejected(self):
  p,n=self.fixture();x=p['files']['source/run_research.py'];x['content']+='\n# unknown\n';x['sha256']=d.sha(x['content'].encode())
  self.assertEqual(d.replay_compatibility(p,n)['status'],'UNSUPPORTED')
 def test_other_strategy_change_rejected(self):
  p,n=self.fixture();x=p['files']['source/user_data/strategies/FrozenDailyResearch.py'];x['content']+='\n# unknown\n';x['sha256']=d.sha(x['content'].encode())
  self.assertEqual(d.replay_compatibility(p,n)['status'],'UNSUPPORTED')
 def test_embedded_digest_mismatch_rejected(self):
  p,n=self.fixture();p['files']['source/run_research.py']['content']+='\n'
  self.assertEqual(d.replay_compatibility(p,n)['status'],'UNSUPPORTED')
 def test_signal_mismatch_not_waived(self):
  self.assertEqual(d.replay_match_status({'T1':{'matches':False},'B1':{'matches':True}}),'MISMATCH')
  self.assertEqual(d.replay_match_status({'T1':{'matches':True},'B1':{'matches':True}}),'MATCH')

 def test_unknown_manifest_rejected(self):
  p,n=self.fixture();x=p['files']['source/runtime_manifest.json'];x['content']+='\n';x['sha256']=d.sha(x['content'].encode())
  self.assertEqual(d.replay_compatibility(p,n)['status'],'UNSUPPORTED')
