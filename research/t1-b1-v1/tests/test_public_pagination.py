import unittest
from unittest.mock import patch
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parents[1]))
import run_research as r
H=r.H

def fund(t):return {'fundingTime':str(t),'fundingRate':'0.0001','symbol':'BTCUSDT'}
def candle(t):return [str(t),'10','11','9','10','2']
class PublicPaginationTests(unittest.TestCase):
 def test_funding_pages_bridge_missing_six(self):
  self.assertTrue(hasattr(r,'complete_funding'),'funding paginator missing')
  first={'data':[fund(t*8*H) for t in range(6,106)]}
  with patch.object(r,'fetch',return_value={'data':[fund(t*8*H) for t in range(6)]}):
   out=r.complete_funding(Path('/tmp'),{},first,0,105*8*H)
  self.assertEqual(len(out['data']),106)
 def test_funding_conflict_rejected(self):
  self.assertTrue(hasattr(r,'complete_funding'),'funding paginator missing')
  first={'data':[fund(8*H)]};other=fund(8*H);other['fundingRate']='.2'
  with patch.object(r,'fetch',return_value={'data':[fund(0),other]}),self.assertRaises(ValueError):r.complete_funding(Path('/tmp'),{},first,0,8*H)
 def test_funding_missing_rejected(self):
  self.assertTrue(hasattr(r,'complete_funding'),'funding paginator missing')
  with patch.object(r,'fetch',return_value={'data':[]}),self.assertRaises(ValueError):r.complete_funding(Path('/tmp'),{},{'data':[fund(8*H)]},0,8*H)
 def test_candles_over_1000_hours(self):
  self.assertTrue(hasattr(r,'fetch_candle_window'),'candle paginator missing')
  def get(out,name,endpoint,p):return {'data':[candle(t) for t in range(p['startTime']+H,p['endTime']+1,H)]}
  with patch.object(r,'fetch',side_effect=get):out=r.fetch_candle_window(Path('/tmp'),'trade_h1',{},0,1100*H,'MARKET')
  self.assertEqual([int(x[0]) for x in out['data']],list(range(H,1101*H,H)))
 def test_candle_gap_rejected(self):
  self.assertTrue(hasattr(r,'fetch_candle_window'),'candle paginator missing')
  with patch.object(r,'fetch',return_value={'data':[candle(0),candle(2*H)]}),self.assertRaises(ValueError):r.fetch_candle_window(Path('/tmp'),'trade_h1',{},0,2*H,'MARKET')
 def test_empty_window_rejected(self):
  with self.assertRaisesRegex(ValueError,'Invalid H1 window'):r.fetch_candle_window(Path('/tmp'),'trade_h1',{},0,0,'MARKET')
 def test_retention_bound_explicit(self):
  self.assertTrue(hasattr(r,'fetch_candle_window'),'candle paginator missing')
  with self.assertRaisesRegex(ValueError,'83 days'):r.fetch_candle_window(Path('/tmp'),'trade_h1',{},0,84*24*H,'MARKET')
if __name__=='__main__':unittest.main()
