"""Bounded public GET transport only. No signal, account or scheduler behavior."""
import datetime,json,time,threading
from urllib.parse import urlsplit
from contextlib import suppress
import requests

def _close(response):
 if response is not None:
  with suppress(Exception):response.close()

class ThreadLocalSessions:
 """One Session per worker. Call close_all only after all workers have joined."""
 def __init__(self,factory=None):
  self._factory=factory or requests.Session
  self._local=threading.local();self._lock=threading.Lock();self._sessions=[]
 def get(self,url,**kwargs):
  parsed=urlsplit(url)
  if parsed.scheme!='https' or parsed.netloc!='api.bitget.com' or parsed.fragment:
   raise ValueError('Only official HTTPS public endpoint is allowed')
  if any(k in kwargs for k in ('proxies','verify','cert','auth','allow_redirects')):
   raise ValueError('Transport security and proxy settings cannot be overridden')
  session=getattr(self._local,'session',None)
  if session is None:
   session=self._factory();self._local.session=session
   with self._lock:self._sessions.append(session)
  try:return session.get(url,allow_redirects=False,**kwargs)
  except Exception:
   self.discard_current();raise
 def discard_current(self):
  session=getattr(self._local,'session',None)
  if session is not None:
   self._local.session=None
   with self._lock:
    if session in self._sessions:self._sessions.remove(session)
   _close(session)
 def close_all(self):
  # Lifecycle contract: caller has joined ThreadPoolExecutor before this method.
  with self._lock:
   sessions=self._sessions;self._sessions=[];self._local=threading.local()
  for session in sessions:_close(session)

_SESSIONS=ThreadLocalSessions()

def session_get(url,**kwargs):return _SESSIONS.get(url,**kwargs)
def close_sessions():_SESSIONS.close_all()

_DEADLINE=None

def set_deadline(seconds=210):
 global _DEADLINE
 _DEADLINE=time.monotonic()+seconds

def attempt_get(out,name,url,params,get):
 for attempt in (1,2):
  remaining=float('inf') if _DEADLINE is None else _DEADLINE-time.monotonic()
  start=datetime.datetime.now(datetime.timezone.utc);tick=time.monotonic()
  receipt={'url':url,'params':params,'attempt':attempt,'requested_utc':start.isoformat(),'http_status':None,'code':None,'response_received':False}
  if remaining<31:
   receipt.update(error_class='TimeoutError',error_stage='BUDGET_EXHAUSTED',elapsed_seconds=0,received_utc=start.isoformat())
   (out/('__attempt__'+name+'.attempt'+str(attempt)+'.json')).write_text(json.dumps(receipt,indent=2)+'\n')
   raise TimeoutError('Public transport budget exhausted before request')
  try:
   response=get(url,params=params,timeout=30,stream=True)
  except requests.RequestException as exc:
   try:
    if exc.response is not None:receipt.update(response_received=True,http_status=exc.response.status_code)
    receipt.update(error_class=type(exc).__name__,error_stage='TRANSPORT_NO_RESPONSE' if exc.response is None else 'EXCEPTION_WITH_RESPONSE',elapsed_seconds=time.monotonic()-tick,received_utc=datetime.datetime.now(datetime.timezone.utc).isoformat())
    # No exception repr or proxy URLs: they may contain credentials.
    (out/('__attempt__'+name+'.attempt'+str(attempt)+'.json')).write_text(json.dumps(receipt,indent=2)+'\n')
   finally:
    _close(exc.response);_SESSIONS.discard_current()
   retry=isinstance(exc,(requests.Timeout,requests.ConnectionError)) and not isinstance(exc,(requests.exceptions.SSLError,requests.exceptions.ProxyError)) and exc.response is None
   if not retry or attempt==2:raise
   if _DEADLINE is not None and _DEADLINE-time.monotonic()<32:raise
   time.sleep(1)
  else:
   try:
    receipt.update(http_status=response.status_code,response_received=True)
    try:
     # stream=True makes header receipt explicit; body failures are never retried.
     response.content
    except requests.RequestException as exc:
     receipt.update(error_class=type(exc).__name__,error_stage='RESPONSE_BODY_READ',elapsed_seconds=time.monotonic()-tick,received_utc=datetime.datetime.now(datetime.timezone.utc).isoformat())
     (out/('__attempt__'+name+'.attempt'+str(attempt)+'.json')).write_text(json.dumps(receipt,indent=2)+'\n')
     raise
    if _DEADLINE is not None and time.monotonic()>_DEADLINE:
     receipt.update(error_class='TimeoutError',error_stage='BUDGET_EXCEEDED_AFTER_RESPONSE',elapsed_seconds=time.monotonic()-tick,received_utc=datetime.datetime.now(datetime.timezone.utc).isoformat())
     (out/('__attempt__'+name+'.attempt'+str(attempt)+'.json')).write_text(json.dumps(receipt,indent=2)+'\n')
     raise TimeoutError('Public transport budget exceeded after response')
    receipt.update(http_status=response.status_code,response_received=True,elapsed_seconds=time.monotonic()-tick,received_utc=datetime.datetime.now(datetime.timezone.utc).isoformat())
    try:receipt['code']=response.json().get('code')
    except (ValueError,AttributeError):pass
    (out/('__attempt__'+name+'.attempt'+str(attempt)+'.json')).write_text(json.dumps(receipt,indent=2)+'\n')
    return response
   except Exception:
    _close(response);_SESSIONS.discard_current();raise
