"""Single scheduled research observation. No scheduler, account or notification client."""
import argparse,datetime,fcntl,hashlib,json,os,signal,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parent
UTC=datetime.timezone.utc

def now():return datetime.datetime.now(UTC).isoformat()
def save(path,value):
 temp=path.with_suffix(path.suffix+'.tmp');temp.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n');os.replace(temp,path)
def canonical(t):
 d=datetime.datetime.fromisoformat(t.replace('Z','+00:00'))
 if d.tzinfo is None:raise ValueError('Scheduled time requires timezone')
 return d.astimezone(UTC).isoformat()
def round_key(task,scheduled):return hashlib.sha256((task+'|'+canonical(scheduled)).encode()).hexdigest()[:24]
def previous_run(folder):
 p=folder/'state.json'
 if not p.exists():return None
 s=json.loads(p.read_text())
 if s['status']=='RUNNING':
  s.update(status='INTERRUPTED',discovered_utc=now(),error='Previous attempt ended without terminal receipt; no automatic resampling');save(p,s)
 return s

def decision(result, st_checkpoint=None):
 if result.get('status')!='RESEARCH_ONLY_NOT_ADOPTED':return dict(decision='ERROR_NO_DECISION',actionable=False,reasons=['Sampling/calculation incomplete'],signals={})
 if result.get('adopted') is not False:raise ValueError('This entrypoint cannot authorize adopted execution rules')
 signals={k:v['signal_report'] for k,v in result.get('native_signal_checks',{}).items()}
 if result.get('st_research'):signals['ST']=result['st_research']
 from research_execution import describe_execution
 research_execution={k:describe_execution(k,v,st_checkpoint if k=='ST' else None) for k,v in signals.items()}
 return dict(decision='NO_EXECUTABLE_DECISION',actionable=False,reasons=['T1/B1 not adopted; ST approved for independent research tracking, not economically validated or account execution','Account capital/holdings and executable risk contract are not verified'],signals=signals,research_execution=research_execution,research_results_available=bool(signals),account_execution_eligibility='NOT_AUTHORIZED',quantity=None,stoploss=None,target=None,entry_deadline=None)

def check_runtime_identity(before,after):
 if before['manifest_sha256']!=after['manifest_sha256']:raise ValueError('Runtime changed during observation; no decision publication')

def bundle_files(files):
 out={}
 for name,p in files.items():
  b=p.read_bytes();out[name]=dict(sha256=hashlib.sha256(b).hexdigest(),bytes=len(b),encoding='utf-8',content=b.decode('utf-8'))
 return out

def main():
 ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--task-id',required=True);ap.add_argument('--scheduled-utc',required=True);ap.add_argument('--storage-root',type=Path,required=True);ap.add_argument('--history-root',type=Path,required=True);ap.add_argument('--manual-validation',action='store_true');a=ap.parse_args()
 scheduled=canonical(a.scheduled_utc);key=round_key(a.task_id,scheduled)
 # Reject future invocation; late invocations retain actual times and never backfill.
 if datetime.datetime.fromisoformat(scheduled)>datetime.datetime.now(UTC)+datetime.timedelta(seconds=5):raise ValueError('Scheduled time is in the future')
 a.storage_root.mkdir(parents=True,exist_ok=True);folder=a.storage_root/key;folder.mkdir(exist_ok=True)
 with (a.storage_root/('task-'+hashlib.sha256(a.task_id.encode()).hexdigest()[:16]+'.lock')).open('a') as tasklock, (folder/'run.lock').open('a') as lock:
  try:
   fcntl.flock(tasklock,fcntl.LOCK_EX|fcntl.LOCK_NB)
   fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
  except BlockingIOError:print(json.dumps({'round_id':key,'status':'ALREADY_RUNNING'}));return
  old=previous_run(folder)
  if old:print(json.dumps({'round_id':key,'status':'DUPLICATE_NOT_RUN','existing':old,'folder':str(folder)}));return
  state=dict(round_id=key,attempt_id=key+'-01',task_id=a.task_id,scheduled_utc=scheduled,started_utc=now(),status='RUNNING',stage='PREFLIGHT',manual_validation=a.manual_validation,google_sync='PENDING_NOT_ATTEMPTED',notification='NOT_SUBMITTED',events=[])
  def stage(name):
   state['stage']=name;state['events'].append({'stage':name,'utc':now()});save(folder/'state.json',state)
  def interrupted(signum,frame):raise InterruptedError('Process interrupted')
  signal.signal(signal.SIGTERM,interrupted);signal.signal(signal.SIGINT,interrupted)
  stage('PREFLIGHT')
  try:
   from runtime_guard import verify_runtime
   runtime=verify_runtime();save(folder/'runtime.json',runtime);state['st_version']='ST_H1_LO_V1_CONTINUOUS_RESEARCH_20261019'
   stage('PRESERVE_INPUTS')
   blobs=a.storage_root/'inputs';blobs.mkdir(exist_ok=True);inputs={}
   for spec in json.loads((ROOT/'historical_inputs.json').read_text())+json.loads((ROOT/'historical_cost_inputs.json').read_text()):
    data=(a.history_root/spec['relative_path']).read_bytes();digest=hashlib.sha256(data).hexdigest()
    if digest!=spec['sha256']:raise ValueError('Historical input drift')
    target=blobs/(digest+'.csv')
    try:
     with target.open('xb') as f:f.write(data)
    except FileExistsError:
     if hashlib.sha256(target.read_bytes()).hexdigest()!=digest:raise ValueError('Stored input blob drift')
    inputs['historical-inputs/'+spec['relative_path']]=target
   save(folder/'input_index.json',{k:{'path':str(v),'sha256':hashlib.sha256(v.read_bytes()).hexdigest()} for k,v in inputs.items()})
   stage('SAMPLE_AND_CALCULATE')
   command=[sys.executable,str(ROOT/'run_research.py'),'current','--history-root',str(a.history_root),'--output',str(folder/'run')]
   from st_runtime import load_previous
   previous=load_previous(a.storage_root,a.task_id,scheduled,key)
   if previous:
    save(folder/'st_previous.json',previous);command += ['--st-previous',str(folder/'st_previous.json')]
   with (folder/'execution.log').open('w') as log:
    p=subprocess.run(command,stdout=log,stderr=subprocess.STDOUT,timeout=240)
   if p.returncode:raise RuntimeError('Research subprocess failed; exit='+str(p.returncode))
   result=json.loads((folder/'run/result.json').read_text());stage('VALIDATE_RESULT')
   if result.get('status')!='RESEARCH_ONLY_NOT_ADOPTED':raise ValueError('Result incomplete')
   if not result.get('freshness') or any(not x.get('ready') for x in result['native_signal_checks'].values()):raise ValueError('Freshness or rule readiness missing')
   if set(result['native_signal_checks'])!={'T1','B1'}:raise ValueError('Missing frozen strategy result')
   if result.get('st_research',{}).get('status')!='RESEARCH_TRACKING_NOT_ECONOMICALLY_VALIDATED':raise ValueError('ST research result missing')
   checkpoint=json.loads((folder/'run/st_checkpoint.json').read_text())
   d=decision(result,checkpoint)
   ticker=json.loads((folder/'run/raw/ticker_final.json').read_text())
   metadata=json.loads((folder/'run/raw/ticker_final.metadata.json').read_text())
   from signal_advice import build_advice, read_previous_decision
   d['signal_advice']=build_advice(d['signals'],ticker,metadata,result['asof_utc'],a.task_id,read_previous_decision(previous),checkpoint)
   save(folder/'decision.json',d)
   tick=ticker['data'][0]
   summary={'decision_and_reasons':d,'market':{'asof_utc':result['asof_utc'],'closed_through_utc':result['closed_data_through_utc'],'last':tick.get('lastPr'),'bid':tick.get('bidPr'),'ask':tick.get('askPr'),'mark':tick.get('markPrice'),'source':'Bitget public','not_a_fresh_quote_after_asof':True},'signal_basis':{'version':result['version'],'runtime':runtime,'source':'T1/B1: Freqtrade native strategy dataframe; ST: independent research signal and continuous cost ledger','signals':d['signals'],'original_observation_gaps':['Independent OI not integrated','Original multiperiod/weekly/monthly and macro observation supplement not implemented by this wrapper','Original candidate and notification lifecycle remain external']}}
   check_runtime_identity(runtime,result['runtime'])
   check_runtime_identity(runtime,verify_runtime())
   save(folder/'summary.json',summary);stage('PACKAGE')
   save(folder/'lifecycle.json',dict(state,packaging_status='IN_PROGRESS; final archive receipt is external to avoid recursive hash'))
   files=dict(inputs)
   for p in sorted((folder/'run').rglob('*.json')):files['run/'+str(p.relative_to(folder/'run'))]=p
   for name in ['runtime.json','input_index.json','decision.json','summary.json','lifecycle.json']:files[name]=folder/name
   manifest=json.loads((ROOT/'runtime_manifest.json').read_text())
   for name in manifest['files']:files['source/'+name]=ROOT/name
   files['source/runtime_manifest.json']=ROOT/'runtime_manifest.json'
   package={'kind':'MANUAL_RESEARCH_VALIDATION' if a.manual_validation else 'HOURLY_RESEARCH_OBSERVATION','round_id':key,'scheduled_utc':scheduled,'actual_asof_utc':result['asof_utc'],'adopted':False,'files':bundle_files(files)}
   if hashlib.sha256(package['files']['source/runtime_manifest.json']['content'].encode()).hexdigest()!=runtime['manifest_sha256']:raise ValueError('Packaged manifest drift')
   for name,digest in manifest['files'].items():
    if package['files']['source/'+name]['sha256']!=digest:raise ValueError('Packaged source drift: '+name)
   save(folder/'google-evidence.json',package)
   # Read back every packaged byte/hash before considering calculation complete.
   check=json.loads((folder/'google-evidence.json').read_text())
   for spec in check['files'].values():
    b=spec['content'].encode();assert len(b)==spec['bytes'] and hashlib.sha256(b).hexdigest()==spec['sha256']
   state.update(status='COMPLETE',completed_utc=now(),archive_sha256=hashlib.sha256((folder/'google-evidence.json').read_bytes()).hexdigest(),file_count=len(check['files']),decision=d['decision'])
   stage('COMPLETE')
  except BaseException as e:
   state.update(status='INTERRUPTED' if isinstance(e,(KeyboardInterrupt,InterruptedError)) else 'FAILED',completed_utc=now(),error=type(e).__name__+': '+str(e),decision='ERROR_NO_DECISION');save(folder/'state.json',state)
   # Terminal errors are retained locally; no normal summary or notification is emitted.
   print(json.dumps({'round_id':key,'status':state['status'],'folder':str(folder)}));raise
  print(json.dumps({'round_id':key,'status':state['status'],'folder':str(folder),'summary':str(folder/'summary.json'),'archive':str(folder/'google-evidence.json'),'archive_sha256':state['archive_sha256']},ensure_ascii=False))
if __name__=='__main__':main()
