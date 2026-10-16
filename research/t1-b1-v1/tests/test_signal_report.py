import unittest,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from test_integration import bars
from run_research import native_signals
class SignalReport(unittest.TestCase):
 def report(self,frame,name):
  self.assertTrue((ROOT/'signal_report.py').exists(),'structured signal reporter missing')
  from signal_report import describe_signal
  return describe_signal(frame,name)
 def test_repeat_long_is_wait_not_new_entry(self):
  f,_=native_signals(bars(),'T1');r=self.report(f,'T1')
  self.assertEqual(r['event'],'WAIT');self.assertEqual(r['native_flags']['enter_long'],1);self.assertIsNone(r['execution']['quantity'])
 def test_new_long_transition(self):
  f,_=native_signals(bars(),'T1');i=next(i for i in range(1,len(f)) if f.iloc[i].research_long_at_close and not f.iloc[i-1].research_long_at_close)
  r=self.report(f.iloc[:i+1],'T1');self.assertEqual(r['event'],'INITIALIZED_LONG');self.assertIsNotNone(r['indicators']['research_sma50'])
 def test_insufficient_data_no_signal(self):
  f,_=native_signals(bars(10),'B1');r=self.report(f,'B1');self.assertEqual(r['event'],'INSUFFICIENT_DATA')

 def test_exit_transition_from_native_flags(self):
  b=bars(65)
  for x in b[60*24:]:
   x.update(open=80,close=80,high=81,low=79)
  f,_=native_signals(b,'T1');i=next(i for i in range(1,len(f)) if f.iloc[i-1].research_long_at_close and not f.iloc[i].research_long_at_close)
  r=self.report(f.iloc[:i+1],'T1');self.assertEqual(r['event'],'EXIT_LONG_TRANSITION');self.assertEqual(r['native_flags']['exit_long'],1);self.assertIsNotNone(r['tags']['exit'])
