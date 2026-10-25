import unittest,sys,json,hashlib,tempfile
from pathlib import Path
P=Path(__file__).resolve().parents[1];sys.path.insert(0,str(P))
from st_signals import supertrend
from st_runtime import load_previous,day_contribution
class Contract(unittest.TestCase):
 def test_supertrend_verbatim(self):
  old=(P/'reference/st-approved/public_candidates.py').read_text();new=(P/'st_signals.py').read_text()
  self.assertEqual(old[old.index('def supertrend('):old.index('\ndef features(')],new[new.index('def supertrend('):new.index('\ndef features(')])
 def test_no_repeat_after_stop(self):
  from st_engine import simulate
  from st_indicators import H
  bs=[dict(ts=i*H,open=100,high=101,low=90 if i==0 else 99,close=100) for i in range(3)]
  fs={i*H:dict(atr=2,daily_long=True,entry_a=i==0,exit_a=False) for i in range(3)}
  r=simulate(bs,fs,'A',{},continuous=True)
  self.assertEqual([o['reason'] for o in r[2]],['ENTRY','STOP_INTRABAR']);self.assertEqual(r[-1]['q'],0)
 def test_funding_before_stop_gap(self):
  from st_engine import simulate
  from st_indicators import H
  bs=[dict(ts=0,open=100,high=101,low=99,close=100),dict(ts=H,open=90,high=91,low=89,close=90)]
  fs={0:dict(atr=2,daily_long=True,entry_a=True)}
  r=simulate(bs,fs,'A',{H:.001},continuous=True)
  self.assertEqual(r[2][1]['reason'],'STOP_GAP');self.assertEqual(len(r[3]),1);self.assertGreater(r[3][0]['paid'],0)
 def test_day_excludes_end_open_fees(self):
  c={'ledger':{'curve':[dict(ts=0,equity=1000),dict(ts=24,equity=1005)],'orders':[dict(ts=0,fee=1,slippage=2),dict(ts=24,fee=9,slippage=9)],'fundlog':[dict(ts=0,paid=3),dict(ts=24,paid=8)]}}
  r=day_contribution(c,0,24);self.assertEqual((r['marked_pnl'],r['fees'],r['funding']),(5,1,3))
 def test_missing_day_not_zero(self):self.assertIsNone(day_contribution({'ledger':{'curve':[]}},0,1)['marked_pnl'])
 def test_prior_invalid_archive_rejected(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'r';(p/'run').mkdir(parents=True);(p/'run/st_checkpoint.json').write_text('{}');(p/'google-evidence.json').write_text('{}');(p/'state.json').write_text(json.dumps(dict(task_id='t',round_id='r',status='COMPLETE',scheduled_utc='2026-01-01',archive_sha256='wrong')))
   with self.assertRaises(ValueError):load_previous(Path(d),'t','2026-01-02')
if __name__=='__main__':unittest.main()
