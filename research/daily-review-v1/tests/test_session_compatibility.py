import copy,json,shutil,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).parents[1]))
import daily_review as d
class SessionCompatibility(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.base=Path(self.tmp.name)/'base';shutil.copytree(d.BASE,self.base,ignore=shutil.ignore_patterns('__pycache__'))
  self.required=['run_research.py','rules.py','signal_report.py','user_data/strategies/FrozenDailyResearch.py']
  ref=self.base/'reference/session-approved';ref.mkdir(parents=True,exist_ok=True)
  saved=self.base/'reference/session-approved'
  self.old=(saved/'run_research.py.txt').read_bytes();self.manifest=(saved/'runtime_manifest.json').read_bytes();(ref/'run_research.py.txt').write_bytes(self.old)
  self.new=self.old+b'\n# isolated session-only compatibility fixture\n';(self.base/'run_research.py').write_bytes(self.new)
  self.tr=dict(new_run_research_sha256=d.sha(self.new),previous_run_research_sha256=d.sha(self.old),previous_source_path='reference/session-approved/run_research.py.txt',allowed_old_pairs=[dict(source_sha256=d.sha(self.old),manifest_sha256=d.sha(self.manifest))]+json.loads((self.base/'transport_compatibility.json').read_text())['allowed_old_pairs'])
  (self.base/'session_compatibility.json').write_text(json.dumps(self.tr));self.patch=patch.object(d,'BASE',self.base);self.patch.start()
 def tearDown(self):self.patch.stop();self.tmp.cleanup()
 def archive(self):
  files={}
  for n in self.required:
   b=self.old if n=='run_research.py' else (self.base/n).read_bytes();files['source/'+n]=dict(content=b.decode(),sha256=d.sha(b))
  files['source/runtime_manifest.json']=dict(content=self.manifest.decode(),sha256=d.sha(self.manifest));return dict(files=files)
 def test_exact_immediate_predecessor(self):
  self.assertEqual(d.replay_compatibility(self.archive(),self.required)['status'],'KNOWN_SESSION_TRANSPORT_ONLY')
 def test_old_chain_retained(self):
  p=self.archive();b=(self.base/'reference/st-approved/run_research_v3.txt').read_bytes().replace(b"kLineType='mark'",b"kLineType='MARK'");p['files']['source/run_research.py']=dict(content=b.decode(),sha256=d.sha(b));m=(Path(__file__).parent/'fixtures/runtime_v3_before_mark_fix.json').read_bytes();p['files']['source/runtime_manifest.json']=dict(content=m.decode(),sha256=d.sha(m));x=d.replay_compatibility(p,self.required);self.assertEqual(x['status'],'KNOWN_SESSION_TRANSPORT_ONLY');self.assertEqual(x['proof']['prior_compatibility']['status'],'KNOWN_BOUNDED_TRANSPORT_ONLY')
 def test_unknown_pair_rejected(self):
  p=self.archive();f=p['files']['source/runtime_manifest.json'];f['content']+='\n';f['sha256']=d.sha(f['content'].encode());self.assertEqual(d.replay_compatibility(p,self.required)['status'],'UNSUPPORTED')
 def test_wrong_reference_rejected(self):
  (self.base/'reference/session-approved/run_research.py.txt').write_bytes(self.old+b'\n');self.assertEqual(d.replay_compatibility(self.archive(),self.required)['status'],'UNSUPPORTED')
 def test_native_drift_rejected(self):
  b=self.new.replace(b'def native_signals(',b'def native_signals( ',1);(self.base/'run_research.py').write_bytes(b);self.tr['new_run_research_sha256']=d.sha(b);(self.base/'session_compatibility.json').write_text(json.dumps(self.tr));self.assertEqual(d.replay_compatibility(self.archive(),self.required)['status'],'UNSUPPORTED')
 def test_economic_drift_rejected(self):
  p=self.archive();f=p['files']['source/rules.py'];f['content']+='\n# changed';f['sha256']=d.sha(f['content'].encode());self.assertEqual(d.replay_compatibility(p,self.required)['status'],'UNSUPPORTED')
 def test_embedded_digest_rejected(self):
  p=self.archive();p['files']['source/run_research.py']['sha256']='0'*64;self.assertEqual(d.replay_compatibility(p,self.required)['status'],'UNSUPPORTED')
