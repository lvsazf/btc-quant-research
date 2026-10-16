"""Offline preflight: verify exact research bundle and installed runtime before sampling."""
import hashlib,json,sys,platform,subprocess
from pathlib import Path
from importlib.metadata import version
ROOT=Path(__file__).resolve().parent

def verify_files(root,files):
 for relative,expected in files.items():
  p=root/relative
  if not p.is_file() or hashlib.sha256(p.read_bytes()).hexdigest()!=expected:
   raise ValueError('Runtime file missing or changed: '+relative)

def verify_runtime():
 manifest_path=ROOT/'runtime_manifest.json';m=json.loads(manifest_path.read_text())
 if str(ROOT)!=m['paths']['absolute_root']:raise ValueError('Research root drift: review restoration mapping first')
 repo=ROOT.parents[1]
 if ROOT.relative_to(repo).as_posix()!=m['paths']['repo_relative']:raise ValueError('Repository layout drift')
 # Do not resolve the venv executable symlink: its invocation path selects the venv.
 if str(Path(sys.executable).absolute())!=m['paths']['python_executable']:raise ValueError('Python executable drift')
 if platform.python_version()!=m['dependencies']['python']:raise ValueError('Python version drift')
 for package,expected in m['dependencies']['packages'].items():
  if version(package)!=expected:raise ValueError('Dependency version drift: '+package)
 import freqtrade
 if str(Path(freqtrade.__file__).resolve())!=m['paths']['freqtrade_module']:raise ValueError('Freqtrade import path drift')
 verify_files(ROOT,m['files'])
 subprocess.run(['git','merge-base','--is-ancestor',m['git_source_base'], 'HEAD'],cwd=repo,check=True,capture_output=True)
 head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=repo,text=True).strip()
 status=subprocess.check_output(['git','status','--porcelain'],cwd=repo,text=True).strip()
 return dict(status='VERIFIED_RESEARCH_ONLY',research_version=m['research_version'],runtime_lock_version=m['runtime_lock_version'],manifest_sha256=hashlib.sha256(manifest_path.read_bytes()).hexdigest(),actual_root=str(ROOT),python=sys.executable,freqtrade=freqtrade.__file__,git_head=head,git_status=status,git_source_base=m['git_source_base'],adopted=False)
if __name__=='__main__':print(json.dumps(verify_runtime(),indent=2))
