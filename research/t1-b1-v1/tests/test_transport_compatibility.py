import unittest,sys,pathlib,json,copy
ROOT=pathlib.Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT),str(ROOT.parent/'daily-review-v1')]
import daily_review as d
class Compatibility(unittest.TestCase):
 def fixture(self):
  p=json.loads(pathlib.Path('/workspace/scratch/53a27f12d2db/btc-runtime/cloud-recovery-validation-20261116/checkpoint-inputs/raw.json').read_text())
  return p,['run_research.py','rules.py','signal_report.py','user_data/strategies/FrozenDailyResearch.py']
 def test_exact_original_archive_remains_supported(self):
  p,required=self.fixture();self.assertNotEqual(d.replay_compatibility(p,required)['status'],'UNSUPPORTED')
 def test_unknown_manifest_rejected(self):
  p,required=self.fixture();p['files']['source/runtime_manifest.json']['content']+=' ';p['files']['source/runtime_manifest.json']['sha256']=d.sha(p['files']['source/runtime_manifest.json']['content'].encode());self.assertEqual(d.replay_compatibility(p,required)['status'],'UNSUPPORTED')
 def test_economic_drift_rejected(self):
  p,required=self.fixture();p['files']['source/rules.py']['content']+=' ';p['files']['source/rules.py']['sha256']=d.sha(p['files']['source/rules.py']['content'].encode());self.assertEqual(d.replay_compatibility(p,required)['status'],'UNSUPPORTED')
if __name__=='__main__':unittest.main()
