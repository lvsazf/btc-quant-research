"""Load byte-identical frozen research reference, validating content before use."""
import hashlib,importlib.util,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parent
MANIFEST=json.loads((ROOT/'reference_manifest.json').read_text())
for row in MANIFEST['frozen_references']:
 if hashlib.sha256((ROOT/row['path']).read_bytes()).hexdigest()!=row['sha256']:
  raise RuntimeError('Frozen research source mismatch: '+row['path'])
# Reference run.py imports its sibling core ledger as engine; prevent unrelated
# sys.modules['engine'] from silently changing constants/helpers in this process.
core=ROOT/'reference/btc-core-tactical-20261016/engine.py'
spec=importlib.util.spec_from_file_location('engine',core);engine=importlib.util.module_from_spec(spec)
previous=sys.modules.get('engine');sys.modules['engine']=engine;spec.loader.exec_module(engine)
ref=ROOT/'reference/btc-trend-breakout-20261016/run.py'
spec=importlib.util.spec_from_file_location('_t1b1_frozen_reference',ref);reference=importlib.util.module_from_spec(spec)
spec.loader.exec_module(reference)
if previous is not None:sys.modules['engine']=previous
else:sys.modules.pop('engine',None)
daily_states=reference.daily_states
simulate=reference.simulate
load_csv=reference.load_csv
H=reference.H
VERSION=MANIFEST['research_version']

def validate_bars(bars):
 if not bars or any(b['ts']%H for b in bars):raise ValueError('Invalid hourly timestamps')
 if any(b['ts']-a['ts']!=H for a,b in zip(bars,bars[1:])):raise ValueError('Missing/duplicate/nonordered H1')
 for b in bars:
  if not 0<b['low']<=min(b['open'],b['close'])<=max(b['open'],b['close'])<=b['high']:raise ValueError('Invalid OHLC')
 return bars
