import datetime,json,os,socket,subprocess,sys,tarfile,time,traceback
from pathlib import Path
P=Path('/root/gpufree-share/isaac_visual_decision');OPS=Path('/root/gpufree-data/ivd-ops/20261006');prefix=OPS/'text_study_30_31';os.chdir(P);sys.path.insert(0,str(P))
from visual_lab.audit import write_json,sha256_file
from visual_lab.client import DecisionClient
from visual_lab.goal_binding import run_binding_replay,build_binding_report,binding_code_hashes
from tools.freeze_text_study import freeze_text_study,verify_study_request
source=P/'runs/25_static_paired_capture';reference=P/'runs/29_modality_aware_prompts';freeze=OPS/'text_study_42_frozen'
outputs={'zh':P/'runs/30_goal_name_binding','en':P/'runs/31_english_bound_intern'}
def utc():return datetime.datetime.now(datetime.timezone.utc).isoformat()
def cmd(args):return subprocess.run(args,check=True,capture_output=True,text=True).stdout.strip()
assert cmd(['git','status','--porcelain'])==''
assert cmd(['git','rev-parse','HEAD'])=='214dea0b8e4a60f2b8e4a61ceaa5a3df552b3322'
assert all(not p.exists() for p in outputs.values()) and not freeze.exists()
assert cmd(['nvidia-smi','--query-compute-apps=pid,process_name','--format=csv,noheader'])==''
with socket.socket() as s:assert s.connect_ex(('127.0.0.1',8766))!=0
review=json.loads((P/'test_reports/text_study_input_review_20261007.json').read_text());frozen=freeze_text_study(source,reference,freeze)
for k in ['requests','planned_order','request_sha256','wire_request_sha256','http_body_sha256','code_sha256','freeze_tool_sha256','reference_files_sha256','seed','count']:
 assert review[k]==frozen[k],k
for group in ['zh','en','jev']:
 for name,h in frozen['request_sha256'][group].items():assert sha256_file(freeze/group/'requests'/(name+'.json'))==h
 for name,h in frozen['wire_request_sha256'][group].items():assert sha256_file(freeze/group/'wire_requests'/(name+'.json'))==h
assert not Path(str(prefix)+'_lifecycle.json').exists()
args=['/root/gpufree-data/envs/ivd-model/bin/python','-u',str(P/'serve_model.py'),'--checkpoint','/root/gpufree-data/models/Intern-Decision-4B','--trust-model-code','--expected-inference-sha256','c904e2c67ca0775621a22375ee373d2ba30b52117cda870c6c9ef74143b29863','--device','cuda','--dtype','bfloat16','--max-length','8192','--host','127.0.0.1','--port','8766','--allow-text-only-ablation']
life={'started_utc':utc(),'implementation_commit':cmd(['git','rev-parse','HEAD']),'new_isaac_process_started':False,'model_had_control':False,'freeze_manifest_sha256':sha256_file(freeze/'manifest.json'),'preflight_sha256':sha256_file(P/'test_reports/text_study_input_review_20261007.json'),'gpu_before':cmd(['nvidia-smi','--query-gpu=name,memory.used','--format=csv,noheader']),'service_command':args,'complete':False,'groups':{}};service=None
try:
 with Path(str(prefix)+'_service.log').open('x') as log:
  service=subprocess.Popen(args,cwd=P,stdout=log,stderr=subprocess.STDOUT,env={**os.environ,'LD_LIBRARY_PATH':''});life['service_pid']=service.pid
  client=DecisionClient('http://127.0.0.1:8766/v1/decisions');deadline=time.monotonic()+180
  while True:
   assert service.poll() is None,'Own service exited'
   try:health=client.health();break
   except Exception:
    if time.monotonic()>deadline:raise
    time.sleep(1)
  assert health['requests_completed']==0;life['model_health']=health;write_json(Path(str(prefix)+'_preflight.json'),{**life,'ready_utc':utc()})
  predict=client.predict
  for group in ['zh','en']:
   planned=[j for j in frozen['planned_order'] if j['group']==group];calls=[0];output=outputs[group]
   def audited_predict(request):
    job=planned[calls[0]];verify_study_request(frozen,group,job['name'],request)
    if calls[0]==0:
     m=json.loads((output/'manifest.json').read_text());assert m['planned_request_sha256']==frozen['request_sha256'][group]
     assert [j['name'] for j in m['planned_order']]==[j['name'] for j in planned]
     assert binding_code_hashes()==frozen['code_sha256']
     for g in ['zh','en','jev']:
      for name,h in frozen['wire_request_sha256'][g].items():assert sha256_file(freeze/g/'wire_requests'/(name+'.json'))==h
     write_json(Path(str(prefix)+'_'+group+'_gate.json'),{'before_group_first_inference_utc':utc(),'all42_frozen_before_inference':True,'group_request_hashes_match':14,'freeze_manifest_sha256':sha256_file(freeze/'manifest.json'),'code_sha256':binding_code_hashes()})
    calls[0]+=1;return predict(request)
   client.predict=audited_predict;start=utc();result=run_binding_replay(source,reference,output,client,language=group)
   life['groups'][group]={'started_utc':start,'ended_utc':utc(),'complete':result['complete'],'api_completed':result['api_completed'],'error':result['error'],'http_prediction_attempts':calls[0]}
   assert result['complete'],result['error'];assert calls[0]==14
   build_binding_report(source,output,output/'report.html')
  life['complete']=True;assert client.health()['requests_completed']==28
except BaseException as e:
 life['wrapper_error']=f'{type(e).__name__}: {e}';traceback.print_exc()
finally:
 if service is not None:
  if service.poll() is None:
   service.terminate()
   try:service.wait(timeout=30)
   except subprocess.TimeoutExpired:service.kill();service.wait(timeout=10)
  life['own_service_stopped']=True;life['service_returncode']=service.returncode
 life['gpu_compute_processes_after']=cmd(['nvidia-smi','--query-compute-apps=pid,process_name','--format=csv,noheader']);life['ended_utc']=utc();write_json(Path(str(prefix)+'_lifecycle.json'),life)
 with tarfile.open(str(prefix)+'_evidence.tar.gz','w:gz') as archive:
  for output in outputs.values():
   if output.exists():archive.add(output,arcname=output.name)
  archive.add(freeze,arcname=freeze.name)
  for suffix in ['_preflight.json','_zh_gate.json','_en_gate.json','_lifecycle.json','_service.log']:
   path=Path(str(prefix)+suffix)
   if path.exists():archive.add(path,arcname=path.name)
 print(json.dumps(life,indent=2),flush=True)
 assert life['complete'] and 'wrapper_error' not in life
