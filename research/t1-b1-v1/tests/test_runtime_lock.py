"""Runtime drift prevention: missing guard, tampered source, and version drift must fail."""
import unittest, subprocess, sys, json, tempfile, shutil
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
class RuntimeLock(unittest.TestCase):
 def test_preflight_reports_loaded_identity(self):
  p=subprocess.run([sys.executable,str(ROOT/'runtime_guard.py')],capture_output=True,text=True)
  self.assertEqual(p.returncode,0,p.stderr)
  r=json.loads(p.stdout);self.assertEqual(r['status'],'VERIFIED_RESEARCH_ONLY');self.assertTrue(r['git_head']);self.assertEqual(r['actual_root'],str(ROOT))
 def test_tampered_manifest_file_rejected(self):
  self.assertTrue((ROOT/'runtime_guard.py').exists(),'runtime guard is missing')
  sys.path.insert(0,str(ROOT));from runtime_guard import verify_files
  with tempfile.TemporaryDirectory() as d:
   p=Path(d);(p/'x.py').write_text('changed')
   with self.assertRaises(ValueError):verify_files(p,{'x.py':'0'*64})
 def test_missing_file_rejected(self):
  self.assertTrue((ROOT/'runtime_guard.py').exists(),'runtime guard is missing')
  sys.path.insert(0,str(ROOT));from runtime_guard import verify_files
  with tempfile.TemporaryDirectory() as d:
   with self.assertRaises(ValueError):verify_files(Path(d),{'missing.py':'0'*64})
