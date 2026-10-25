import sys,unittest,copy,random
from pathlib import Path
P=Path(__file__).resolve().parents[1];sys.path.insert(0,str(P))
from st_engine import simulate
from st_indicators import H
sys.path.insert(0,'/workspace/shared/btc-quant-worktree/research/t1-b1-v1/reference/st-approved')
import engine as old
class Continuous(unittest.TestCase):
 def dataset(self):
  rng=random.Random(9);bs=[];v=100
  for i in range(240):
   o=v+rng.uniform(-3,3);v=max(30,o+rng.uniform(-4,4));bs.append(dict(ts=i*H,open=o,high=max(o,v)+2,low=min(o,v)-2,close=v))
  fs={i*H:dict(atr=3,daily_long=True,entry_a=i%13==0,exit_a=i%23==0) for i in range(240)}
  funding={i*H:.0001 for i in range(0,241,8)};marks={b['ts']:dict(b) for b in bs};marks[240*H]=dict(open=bs[-1]['close'])
  return bs,fs,funding,marks
 def test_original_default_exact(self):
  bs,fs,f,m=self.dataset()
  for slip in (.0002,.0005):
   for delay in (0,1):self.assertEqual(old.simulate(bs,fs,'A',f,m,slip,delay),simulate(bs,fs,'A',f,m,slip,delay))
 def test_chunk_equals_whole(self):
  bs,fs,f,m=self.dataset();full=simulate(bs,fs,'A',f,m,continuous=True)
  prev=None
  for b in bs:prev=simulate([b],fs,'A',f,m,continuous=True,previous=prev)[-1]
  self.assertEqual(full[-1],prev)
 def test_boundary_is_idempotent_and_chunk_equivalent(self):
  bs,fs,f,m=self.dataset();whole=simulate(bs,fs,'A',f,m,continuous=True)
  prev=None
  for b in bs:
   stub=dict(b,high=b['open'],low=b['open'],close=b['open'])
   prev=simulate([stub],fs,'A',f,m,continuous=True,previous=prev,boundary_only=True)[-1]
   prev=simulate([stub],fs,'A',f,m,continuous=True,previous=prev,boundary_only=True)[-1]
   prev=simulate([b],fs,'A',f,m,continuous=True,previous=prev)[-1]
  self.assertEqual(whole[-1],prev)
 def test_matches_original_preterminal(self):
  bs,fs,f,m=self.dataset();orig=old.simulate(bs,fs,'A',f,m);cont=simulate(bs,fs,'A',f,m,continuous=True)
  self.assertEqual(orig[1],cont[1]);self.assertEqual([x for x in orig[2] if x['reason']!='TERMINAL'],cont[2]);self.assertEqual([x for x in orig[3] if x['ts']<240*H],cont[3]);self.assertEqual([x for x in orig[4] if not x['terminal']],cont[4])
 def test_gap_rejected(self):
  bs,fs,f,m=self.dataset();p=simulate(bs[:2],fs,'A',f,m,continuous=True)[-1]
  with self.assertRaises(ValueError):simulate(bs[3:4],fs,'A',f,m,continuous=True,previous=p)
if __name__=='__main__':unittest.main()
