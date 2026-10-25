import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parents[1]))
import daily_review as d
class MarkProvenanceTests(unittest.TestCase):
 def test_uppercase_or_unknown_cannot_enter_cost_ledger(self):
  validate=getattr(d,'validate_mark_source',None)
  self.assertIsNotNone(validate,'Cost ledger must validate mark request provenance')
  for url in ['https://api.bitget.com/api/v2/mix/market/candles?kLineType=MARK','https://evil.test/api/v2/mix/market/history-mark-candles','https://api.bitget.com/api/v2/mix/market/candles']:
   with self.assertRaises(ValueError):validate({'url':url,'http_status':200,'code':'00000'})
 def test_true_mark_endpoint_and_lowercase_pass(self):
  validate=getattr(d,'validate_mark_source',None)
  self.assertIsNotNone(validate)
  for url in ['https://api.bitget.com/api/v2/mix/market/history-mark-candles','https://api.bitget.com/api/v2/mix/market/candles?kLineType=mark']:
   validate({'url':url,'http_status':200,'code':'00000'})
