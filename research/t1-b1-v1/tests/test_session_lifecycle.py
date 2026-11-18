import unittest,sys,pathlib
from unittest.mock import patch
ROOT=pathlib.Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
import run_research as r
class Lifecycle(unittest.TestCase):
 def test_main_closes_sessions_after_success(self):
  with patch.object(r,'_main',create=True) as work,patch.object(r,'close_sessions',create=True) as close:
   with patch.object(sys,'argv',['test','--help']):
    try:r.main()
    except SystemExit:pass
   work.assert_called_once();close.assert_called_once()
 def test_main_closes_sessions_after_failure(self):
  with patch.object(r,'_main',create=True,side_effect=RuntimeError('sentinel')),patch.object(r,'close_sessions',create=True) as close:
   with patch.object(sys,'argv',['test','--help']):
    try:r.main()
    except SystemExit:pass
    except RuntimeError as e:self.assertEqual(str(e),'sentinel')
   close.assert_called_once()

 def test_fetch_closes_response_if_write_fails(self):
  from unittest.mock import Mock
  response=Mock(content=b"{}")
  with patch.object(r,'attempt_get',return_value=response),patch.object(r,'session_get',create=True):
   with self.assertRaises(FileNotFoundError):r.fetch(pathlib.Path('/nonexistent/no-write'),'x','/api/v2/public/time',{})
  response.close.assert_called_once()

class RealResponseLifecycle(unittest.TestCase):
 def test_real_responses_preserve_wire_bytes_and_close_on_all_fetch_outcomes(self):
  import io,json,hashlib,tempfile,requests
  import public_transport as transport
  cases=[
   (200,b'{ "code" : "00000", "requestTime": 123, "data": {"x":1} }\r\n',True),
   (403,b'{"code":"403","msg":"Forbidden"}\n',False),
   (200,b'{"code":"40001","msg":"provider rejected"}',False),
   (200,b'not json\r\n',False),
   (302,b'<html>redirect</html>',False),
  ]
  for status,payload,accepted in cases:
   with self.subTest(status=status,payload=payload),tempfile.TemporaryDirectory() as td:
    response=requests.Response();response.status_code=status
    response.url='https://api.bitget.com/api/v2/public/time'
    response.raw=io.BytesIO(payload);response.headers['Content-Type']='application/json'
    out=pathlib.Path(td)
    with patch.object(transport,'_DEADLINE',None),patch.object(r,'session_get',return_value=response) as get,patch.object(response,'close',wraps=response.close) as close,patch.object(requests.Session,'request',side_effect=AssertionError('Network forbidden')):
     if accepted:self.assertEqual(r.fetch(out,'probe','/api/v2/public/time',{}),json.loads(payload))
     else:
      with self.assertRaisesRegex(RuntimeError,'Invalid public data: probe'):
       r.fetch(out,'probe','/api/v2/public/time',{})
     get.assert_called_once_with(response.url,params={},timeout=30,stream=True)
     close.assert_called_once()
    self.assertEqual((out/'probe.json').read_bytes(),payload)
    meta=json.loads((out/'probe.metadata.json').read_text())
    self.assertEqual(meta['sha256'],hashlib.sha256(payload).hexdigest())
    self.assertEqual(meta['http_status'],status)
    self.assertEqual(meta['url'],response.url)
    self.assertEqual(set(meta),{'url','http_status','code','server_requestTime','requested_utc','received_utc','requested_beijing','received_beijing','sha256'})
    attempt=json.loads((out/'__attempt__probe.attempt1.json').read_text())
    self.assertTrue(attempt['response_received']);self.assertEqual(attempt['http_status'],status)
    self.assertFalse((out/'__attempt__probe.attempt2.json').exists())
