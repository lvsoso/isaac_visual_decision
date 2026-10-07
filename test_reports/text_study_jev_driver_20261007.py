import datetime,json,sys
from pathlib import Path
ROOT=Path('/Users/Zhuanz/Documents/zb/share-2026-10-03/2/isaac_visual_decision');sys.path.insert(0,str(ROOT))
from visual_lab.audit import write_json,sha256_file
from visual_lab.goal_binding import run_binding_replay,build_binding_report,binding_code_hashes
from visual_lab.jev import JevClient
from tools.freeze_text_study import verify_study_request
folder=Path('/private/var/folders/38/gc519q3j3p96d90ybwr3whvm0000gq/T/opencode/ivd-text-study-os9yxtix');evidence=folder/'evidence';output=evidence/'32_english_bound_jev'
source=folder.parent/'ivd-static-evidence-t3lfk5gj/25_static_paired_capture';reference=folder.parent/'ivd-modality-evidence-eclfl849/29_modality_aware_prompts'
frozen=json.loads((ROOT/'test_reports/text_study_input_review_20261007.json').read_text());remote=json.loads((evidence/'text_study_42_frozen/manifest.json').read_text())
for k in ['requests','planned_order','http_body_sha256','code_sha256','request_sha256','wire_request_sha256']:assert remote[k]==frozen[k],k
life_remote=json.loads((evidence/'text_study_30_31_lifecycle.json').read_text());assert life_remote['complete'] and life_remote['own_service_stopped'] and life_remote['gpu_compute_processes_after']==''
for group,batch in [('zh','30_goal_name_binding'),('en','31_english_bound_intern')]:
 summary=json.loads((evidence/batch/'summary.json').read_text());assert summary['complete'] and summary['api_completed']==14
 for name,h in frozen['request_sha256'][group].items():assert sha256_file(evidence/batch/'requests'/(name+'.json'))==h
assert binding_code_hashes()==frozen['code_sha256'];assert not output.exists()
life={'started_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'model_had_control':False,'new_isaac_process_started':False,'api_completed':0,'complete':False,'preflight_sha256':sha256_file(ROOT/'test_reports/text_study_input_review_20261007.json'),'remote_gpu_groups_completed':28};client=None
try:
 client=JevClient(key_file='~/.ssh/ts.key');predict=client.predict;planned=[j for j in frozen['planned_order'] if j['group']=='jev'];calls=[0]
 def gated(request):
  job=planned[calls[0]];verify_study_request(frozen,'jev',job['name'],request)
  if calls[0]==0:
   m=json.loads((output/'manifest.json').read_text());assert m['planned_request_sha256']==frozen['request_sha256']['jev'];assert m['wire_request_sha256']==frozen['wire_request_sha256']['jev']
   assert [j['name'] for j in m['planned_order']]==[j['name'] for j in planned]
   write_json(evidence/'jev_32_gate.json',{'before_first_jev_inference_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'all42_frozen_before_first_intern_inference':True,'model':'jev-1.13.0','wire_requests_match':14,'preflight_sha256':life['preflight_sha256']})
  calls[0]+=1;return predict(request)
 client.predict=gated;result=run_binding_replay(source,reference,output,client,language='en');life.update(complete=result['complete'],api_completed=result['api_completed'],error=result['error'])
 assert result['complete'],result['error'];assert calls[0]==14;build_binding_report(source,output,output/'report.html')
finally:
 life['ended_utc']=datetime.datetime.now(datetime.timezone.utc).isoformat();life['http_prediction_attempts']=client.attempts if client else 0;write_json(evidence/'jev_32_lifecycle.json',life);print(json.dumps(life,indent=2))
