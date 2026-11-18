import concurrent.futures,pathlib,sys,tempfile,threading,unittest
from unittest.mock import patch
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]))
import public_transport as pt
import requests
URL='https://api.bitget.com/api/v2/public/time'
class FakeResponse:
 status_code=200
 content=b'{"code":"00000"}'
 def __init__(self):self.closed=False
 def close(self):self.closed=True
 def json(self):return {'code':'00000'}
class FakeSession:
 def __init__(self):self.calls=[];self.closed=False;self.fail=None
 def get(self,url,**kwargs):
  self.calls.append((url,kwargs))
  if self.fail:raise self.fail
  return FakeResponse()
 def close(self):self.closed=True
class SessionTests(unittest.TestCase):
 def manager(self):
  self.assertTrue(hasattr(pt,'ThreadLocalSessions'),'thread-local session manager missing')
  made=[]
  def factory():s=FakeSession();made.append(s);return s
  return pt.ThreadLocalSessions(factory),made
 def test_same_thread_reuses(self):
  m,made=self.manager();m.get(URL);m.get(URL);self.assertEqual(len(made),1);self.assertEqual(len(made[0].calls),2);m.close_all()
 def test_workers_use_distinct_sessions_and_close_after_join(self):
  m,made=self.manager();barrier=threading.Barrier(3)
  def worker(_):m.get(URL);barrier.wait();m.get(URL)
  with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:list(pool.map(worker,range(3)))
  self.assertEqual(len(made),3);self.assertTrue(all(len(s.calls)==2 and not s.closed for s in made));m.close_all();self.assertTrue(all(s.closed for s in made))
 def test_close_all_idempotent_and_fresh_next_run(self):
  m,made=self.manager();m.get(URL);m.close_all();m.close_all();m.get(URL);self.assertEqual(len(made),2);self.assertTrue(made[0].closed);self.assertFalse(made[1].closed);m.close_all()
 def test_failure_discards_and_next_call_reconnects_without_internal_retry(self):
  m,made=self.manager();m.get(URL);made[0].fail=requests.ReadTimeout('failure')
  with self.assertRaises(requests.ReadTimeout):m.get(URL)
  self.assertEqual(len(made),1);self.assertTrue(made[0].closed);m.get(URL);self.assertEqual(len(made),2);m.close_all()
 def test_official_https_only_and_no_proxy_or_tls_override(self):
  m,made=self.manager()
  for url in ['http://api.bitget.com/a','https://evil.com/a','https://api.bitget.com.evil.com/a','https://u:p@api.bitget.com/a','https://api.bitget.com:444/a']:
   with self.assertRaises(ValueError):m.get(url)
  for kwargs in [{'verify':False},{'proxies':{}},{'allow_redirects':True},{'auth':('u','p')}]:
   with self.assertRaises(ValueError):m.get(URL,**kwargs)
  self.assertEqual(made,[])
 def test_redirects_disabled(self):
  m,made=self.manager();m.get(URL,timeout=30,stream=True);self.assertFalse(made[0].calls[0][1]['allow_redirects']);m.close_all()
 def test_default_proxy_tls_and_adapter_retry_settings_unchanged(self):
  self.assertTrue(hasattr(pt,'ThreadLocalSessions'))
  real=requests.Session()
  with patch.object(real,'get',return_value=FakeResponse()):
   m=pt.ThreadLocalSessions(lambda:real);m.get(URL)
  self.assertTrue(real.trust_env);self.assertTrue(real.verify);self.assertEqual(real.proxies,{});self.assertEqual(real.adapters['https://'].max_retries.total,0);m.close_all()
 def test_body_failure_closes_response_without_retry(self):
  class Broken(FakeResponse):
   @property
   def content(self):raise requests.ConnectionError('body')
  r=Broken()
  with tempfile.TemporaryDirectory() as t,patch.object(pt.requests,'get',return_value=r) as get:
   with self.assertRaises(requests.ConnectionError):pt.attempt_get(pathlib.Path(t),'x',URL,{},get)
   self.assertTrue(r.closed);self.assertEqual(get.call_count,1)
 def test_attached_response_exception_closes(self):
  r=FakeResponse()
  with tempfile.TemporaryDirectory() as t,patch.object(pt.requests,'get',side_effect=requests.ReadTimeout(response=r)) as get:
   with self.assertRaises(requests.ReadTimeout):pt.attempt_get(pathlib.Path(t),'x',URL,{},get)
   self.assertTrue(r.closed);self.assertEqual(get.call_count,1)
 def test_receipt_write_failure_closes_received_response(self):
  r=FakeResponse()
  with tempfile.TemporaryDirectory() as t,patch.object(pathlib.Path,'write_text',side_effect=OSError('disk')),patch.object(pt.requests,'get',return_value=r) as get:
   with self.assertRaises(OSError):pt.attempt_get(pathlib.Path(t),'x',URL,{},get)
   self.assertTrue(r.closed)
 def test_bounded_retry_uses_fresh_session_and_public_cleanup(self):
  made=[]
  def factory():
   s=FakeSession()
   if not made:s.fail=requests.ReadTimeout('connect')
   made.append(s);return s
  m=pt.ThreadLocalSessions(factory)
  with tempfile.TemporaryDirectory() as t,patch.object(pt,'_SESSIONS',m),patch.object(pt.time,'sleep'):
   r=pt.attempt_get(pathlib.Path(t),'x',URL,{},pt.session_get)
   self.assertEqual(r.status_code,200);self.assertEqual(len(made),2);self.assertTrue(made[0].closed);self.assertFalse(made[1].closed)
   pt.close_sessions();self.assertTrue(made[1].closed);r.close()
 def test_budget_after_response_closes_and_discards(self):
  r=FakeResponse();m,made=self.manager();m.get(URL)
  def late(*args,**kwargs):pt._DEADLINE=pt.time.monotonic()-1;return r
  with tempfile.TemporaryDirectory() as t,patch.object(pt,'_SESSIONS',m),patch.object(pt,'_DEADLINE',None):
   with self.assertRaises(TimeoutError):pt.attempt_get(pathlib.Path(t),'x',URL,{},late)
   self.assertTrue(r.closed);self.assertTrue(made[0].closed)
if __name__=='__main__':unittest.main()
