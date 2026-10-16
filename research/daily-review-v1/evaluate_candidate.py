"""Explicit isolated candidate evaluation only. Never updates adopted/hourly rules."""
import argparse,hashlib,importlib.util,json,sys
from pathlib import Path
from daily_review import daily_states,simulate,write,sha

def validate_spec(spec,code):
 for key in ['version','hypothesis','evidence','falsification','validation_plan','code_sha256']:
  if not spec.get(key):raise ValueError('Candidate frozen protocol missing '+key)
 if spec['code_sha256']!=sha(code.read_bytes()):raise ValueError('Candidate code hash mismatch')
 if spec.get('adopted') is not False:raise ValueError('Candidate must remain unadopted')

def main():
 ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--inputs',type=Path,required=True);ap.add_argument('--inputs-sha256',required=True);ap.add_argument('--candidate',type=Path,required=True);ap.add_argument('--protocol',type=Path,required=True);ap.add_argument('--output',type=Path,required=True);a=ap.parse_args()
 raw=a.inputs.read_bytes()
 if sha(raw)!=a.inputs_sha256:raise ValueError('Validation input drift')
 spec=json.loads(a.protocol.read_text());validate_spec(spec,a.candidate)
 a.output.mkdir(parents=True,exist_ok=False)
 data=json.loads(raw);bars=data['bars'];bs=data['ledger_bars'];rates={int(k):v for k,v in data['funding'].items()};marks={int(k):v for k,v in data['marks'].items()}
 loader=importlib.util.spec_from_file_location('isolated_candidate',a.candidate);module=importlib.util.module_from_spec(loader);loader.loader.exec_module(module)
 # Candidate contract: desired_states(full_closed_H1_history) -> {available_ms: bool}.
 state=module.desired_states(bars)
 if any(type(k)!=int or type(v)!=bool for k,v in state.items()):raise ValueError('Candidate must emit timestamp/bool states')
 # Necessary diagnostic causality check; not a full proof or blind validation.
 for fraction in [.5,.75,.9]:
  prefix=bars[:int(len(bars)*fraction)];cut=prefix[-1]['ts']+3600000
  if module.desired_states(prefix)!={k:v for k,v in state.items() if k<=cut}:raise ValueError('Candidate prefix causality mismatch')
 states,_=daily_states(bars);states['CANDIDATE']=state;results=[]
 for label,slip,delay in [('base',.0002,0),('slip5bp',.0005,0),('delay1h',.0002,1),('stress_both',.0005,1)]:
  for name in ['CASH','HOLD','T1','B1','CANDIDATE']:
   result,*_=simulate(bs,name,states,rates,marks,slip,delay,a.output/label/name);results.append(dict(scenario=label,**result))
 report=dict(status='UNADOPTED_CANDIDATE_DIAGNOSTIC',protocol=spec,input_sha256=a.inputs_sha256,results=results,not_blind_out_of_sample=True,not_native_order_ledger=True,decision='NO_AUTOMATIC_ADOPTION',acceptance='Compare all fixed scenarios and frozen falsification; preserve failures, no selecting best scenario or changing hourly version')
 write(a.output/'report.json',report)
 (a.output/'candidate.py').write_bytes(a.candidate.read_bytes());write(a.output/'protocol.json',spec)
 print(json.dumps(dict(status=report['status'],output=str(a.output))))
if __name__=='__main__':main()
