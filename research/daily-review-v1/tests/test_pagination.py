import copy,json,sys,unittest
from pathlib import Path
from urllib.parse import urlencode
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import daily_review as d

def entry(x):
 s=json.dumps(x);return dict(content=s,sha256=d.sha(s.encode()),bytes=len(s.encode()))
def fixture(name='trade_h1'):
 p={'files':{}};raw={};rows=[]
 for i,t in enumerate([3600000,7200000],1):
  n=name+('' if i==1 else '_page_'+str(i))+'.json'
  row={'fundingTime':str(t),'fundingRate':'0.01'} if name=='history_funding' else [str(t),'1','2','1','2','4']
  rows.append(row)
  b={'code':'00000','data':[row]};e=entry(b);p['files']['run/raw/'+n]=e;raw[n]=e['sha256']
  q=dict(symbol='BTCUSDT',productType='USDT-FUTURES',granularity='1H',startTime=t-3600000,endTime=t,kLineType='mark' if name=='mark_h1' else 'MARKET')
  endpoint='history-fund-rate' if name=='history_funding' else 'candles'
  m=entry(dict(url='https://api.bitget.com/api/v2/mix/market/'+endpoint+'?'+urlencode(q),http_status=200,code='00000',sha256=e['sha256']))
  mn=n[:-5]+'.metadata.json';p['files']['run/raw/'+mn]=m;raw[mn]=m['sha256']
 p['files']['run/public_window.json']=entry(dict(kind='DERIVED_PAGINATED_PUBLIC_WINDOW_V1',raw_pages=raw,bodies={name:{'data':rows}}))
 return p,rows
class PaginationTests(unittest.TestCase):
 def test_two_pages_all_types(self):
  for name in ['trade_h1','mark_h1','history_funding']:
   p,rows=fixture(name);self.assertEqual(d.public_data(p,name),rows)
 def test_legacy_unchanged(self):
  p,rows=fixture();del p['files']['run/public_window.json'];self.assertEqual(d.public_data(p,'trade_h1'),rows[:1])
 def test_derived_tamper(self):
  p,_=fixture();w=d.body(p,'run/public_window.json');w['bodies']['trade_h1']['data'][0][4]='99';p['files']['run/public_window.json']=entry(w)
  with self.assertRaisesRegex(ValueError,'Derived pagination mismatch'):d.public_data(p,'trade_h1')
 def test_raw_tamper(self):
  p,_=fixture();p['files']['run/raw/trade_h1.json']['content']='{}'
  with self.assertRaisesRegex(ValueError,'digest mismatch'):d.public_data(p,'trade_h1')
 def test_metadata_missing(self):
  p,_=fixture();w=d.body(p,'run/public_window.json');del w['raw_pages']['trade_h1_page_2.metadata.json'];p['files']['run/public_window.json']=entry(w)
  with self.assertRaisesRegex(ValueError,'Missing raw pagination'):d.public_data(p,'trade_h1')
 def test_wrong_mark_rejected(self):
  p,_=fixture('mark_h1');n='mark_h1_page_2.metadata.json';m=d.body(p,'run/raw/'+n);m['url']=m['url'].replace('kLineType=mark','kLineType=MARK');e=entry(m);p['files']['run/raw/'+n]=e;w=d.body(p,'run/public_window.json');w['raw_pages'][n]=e['sha256'];p['files']['run/public_window.json']=entry(w)
  with self.assertRaisesRegex(ValueError,'Unverified historical mark'):d.public_data(p,'mark_h1')
 def test_candle_start_is_exclusive(self):
  p,rows=fixture();n='trade_h1_page_2.json';b=d.body(p,'run/raw/'+n);b['data'].insert(0,rows[0]);e=entry(b);p['files']['run/raw/'+n]=e;mn=n[:-5]+'.metadata.json';m=d.body(p,'run/raw/'+mn);m['sha256']=e['sha256'];me=entry(m);p['files']['run/raw/'+mn]=me;w=d.body(p,'run/public_window.json');w['raw_pages'][n]=e['sha256'];w['raw_pages'][mn]=me['sha256'];p['files']['run/public_window.json']=entry(w)
  self.assertEqual(d.public_data(p,'trade_h1'),rows)
 def test_exact_pre_pagination_pair(self):
  tr=json.loads((d.BASE/'pagination_compatibility.json').read_text())
  old=(d.BASE/tr['previous_source_path']).read_bytes()
  manifest_path=Path(__file__).parent/'fixtures/runtime_before_pagination.json'
  raw=manifest_path.read_bytes()
  names=['run_research.py','rules.py','signal_report.py','user_data/strategies/FrozenDailyResearch.py']
  p={'files':{}}
  for n in names:
   b=old if n=='run_research.py' else (d.BASE/n).read_bytes()
   p['files']['source/'+n]=dict(content=b.decode(),sha256=d.sha(b))
  p['files']['source/runtime_manifest.json']=dict(content=raw.decode(),sha256=d.sha(raw))
  self.assertEqual(d.replay_compatibility(p,names)['status'],'KNOWN_PAGINATION_FETCH_ONLY')
  p['files']['source/runtime_manifest.json']['content']+=' '
  self.assertEqual(d.replay_compatibility(p,names)['status'],'UNSUPPORTED')
