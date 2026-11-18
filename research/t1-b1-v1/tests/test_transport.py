import unittest,tempfile,pathlib,sys,json,time
from unittest.mock import patch
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]))
import requests,run_research as rr
class TransportTests(unittest.TestCase):
 def response(self,status=200,body=b'{"code":"00000","data":{}}'):
  r=requests.Response();r.status_code=status;r.url='https://api.bitget.com/api/v2/public/time';r._content=body;return r
 def test_timeout_then_success_retains_attempts(self):
  with tempfile.TemporaryDirectory() as t,patch.object(rr,'session_get',side_effect=[requests.ReadTimeout('secret-password'),self.response()]):
   try: result=rr.fetch(pathlib.Path(t),'time','/api/v2/public/time',{})
   except requests.ReadTimeout:self.fail('bounded retry missing')
   self.assertEqual(result['code'],'00000');files=list(pathlib.Path(t).glob('*.attempt*.json'));self.assertEqual(len(files),2);self.assertNotIn('secret-password',''.join(p.read_text() for p in files))
 def test_exhaustion_records_two_errors(self):
  with tempfile.TemporaryDirectory() as t,patch.object(rr,'session_get',side_effect=requests.ReadTimeout('secret-password')):
   with self.assertRaises(requests.ReadTimeout):rr.fetch(pathlib.Path(t),'time','/api/v2/public/time',{})
   self.assertEqual(len(list(pathlib.Path(t).glob('*.attempt*.json'))),2);self.assertFalse((pathlib.Path(t)/'time.json').exists())
 def test_received_errors_not_retried(self):
  for status,body in [(403,b'{}'),(429,b'{}'),(200,b'{"code":"40000"}'),(200,b'not-json')]:
   with self.subTest(status=status,body=body),tempfile.TemporaryDirectory() as t,patch.object(rr,'session_get',return_value=self.response(status,body)) as get:
    with self.assertRaises(RuntimeError):rr.fetch(pathlib.Path(t),'time','/api/v2/public/time',{})
    self.assertEqual(get.call_count,1);self.assertEqual((pathlib.Path(t)/'time.json').read_bytes(),body)
 def test_tls_not_retried(self):
  with tempfile.TemporaryDirectory() as t,patch.object(rr,'session_get',side_effect=requests.exceptions.SSLError('private')) as get:
   with self.assertRaises(requests.exceptions.SSLError):rr.fetch(pathlib.Path(t),'time','/api/v2/public/time',{})
   self.assertEqual(get.call_count,1);self.assertEqual(len(list(pathlib.Path(t).glob('*.attempt*.json'))),1)
 def test_response_attached_error_not_retried(self):
  e=requests.ReadTimeout('private',response=self.response(403))
  with tempfile.TemporaryDirectory() as t,patch.object(rr,'session_get',side_effect=e) as get:
   with self.assertRaises(requests.ReadTimeout):rr.fetch(pathlib.Path(t),'time','/api/v2/public/time',{})
   self.assertEqual(get.call_count,1)
   receipt=json.loads(next(pathlib.Path(t).glob('*.attempt*.json')).read_text());self.assertTrue(receipt['response_received']);self.assertEqual(receipt['http_status'],403)
 def test_freshness_unchanged(self):
  now=int(time.time()*1000)
  for stamp in [now-61000,now+5000]:
   with self.assertRaises(ValueError):rr.check_fresh({'data':{'serverTime':stamp}},{'data':[{'ts':stamp}]})
class BudgetTests(unittest.TestCase):
 def tearDown(self):
  import public_transport as pt
  pt._DEADLINE=None
 def test_expired_budget_records_failure_without_request(self):
  import public_transport as pt
  with tempfile.TemporaryDirectory() as t,patch.object(pt,'_DEADLINE',time.monotonic()-1),patch.object(rr,'session_get') as get:
   with self.assertRaises(TimeoutError):rr.fetch(pathlib.Path(t),'time','/api/v2/public/time',{})
   self.assertEqual(get.call_count,0);self.assertEqual(len(list(pathlib.Path(t).glob('*.attempt*.json'))),1)
 def test_budget_prevents_retry_after_failure(self):
  import public_transport as pt
  with tempfile.TemporaryDirectory() as t,patch.object(pt,'_DEADLINE',time.monotonic()+31.5),patch.object(rr,'session_get',side_effect=requests.ReadTimeout('private')) as get:
   with self.assertRaises(requests.ReadTimeout):rr.fetch(pathlib.Path(t),'time','/api/v2/public/time',{})
   self.assertEqual(get.call_count,1)
 def test_proxy_policy_error_not_retried(self):
  with tempfile.TemporaryDirectory() as t,patch.object(rr,'session_get',side_effect=requests.exceptions.ProxyError('403 denied')) as get:
   with self.assertRaises(requests.exceptions.ProxyError):rr.fetch(pathlib.Path(t),'time','/api/v2/public/time',{})
   self.assertEqual(get.call_count,1)
 def test_attempt_receipts_do_not_match_pagination_page_names(self):
  with tempfile.TemporaryDirectory() as t,patch.object(rr,'session_get',return_value=TransportTests().response()):
   rr.fetch(pathlib.Path(t),'mark_h1_page_2','/api/v2/public/time',{})
   pages=[p.name for p in pathlib.Path(t).iterdir() if p.name.startswith('mark_h1_page_') and not p.name.endswith('.metadata.json')]
   self.assertEqual(pages,['mark_h1_page_2.json'])
 def test_body_timeout_after_headers_not_retried_and_recorded(self):
  class Broken:
   status_code=200
   @property
   def content(self):raise requests.ConnectionError('body private')
  with tempfile.TemporaryDirectory() as t,patch.object(rr,'session_get',return_value=Broken()) as get:
   with self.assertRaises(requests.ConnectionError):rr.fetch(pathlib.Path(t),'time','/api/v2/public/time',{})
   self.assertEqual(get.call_count,1);r=json.loads(next(pathlib.Path(t).glob('*.attempt*.json')).read_text());self.assertEqual(r.get('error_stage'),'RESPONSE_BODY_READ');self.assertTrue(r['response_received'])
 def test_success_after_budget_rejected(self):
  import public_transport as pt
  def late(*a,**kw):pt._DEADLINE=time.monotonic()-1;return TransportTests().response()
  with tempfile.TemporaryDirectory() as t,patch.object(rr,'session_get',side_effect=late):
   with self.assertRaises(TimeoutError):rr.fetch(pathlib.Path(t),'time','/api/v2/public/time',{})
 def test_parallel_names_preserve_separate_receipts(self):
  from concurrent.futures import ThreadPoolExecutor
  r=TransportTests().response()
  with tempfile.TemporaryDirectory() as t,patch.object(rr,'session_get',return_value=r):
   with ThreadPoolExecutor(max_workers=3) as pool:list(pool.map(lambda n:rr.fetch(pathlib.Path(t),n,'/api/v2/public/time',{}),['a','b','c']))
   self.assertEqual(len(list(pathlib.Path(t).glob('*.attempt*.json'))),3)
if __name__=='__main__':unittest.main()
