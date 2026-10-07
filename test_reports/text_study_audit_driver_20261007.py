import copy,datetime,hashlib,json,re,statistics,sys
from pathlib import Path
from visual_lab.audit import write_json,sha256_file
from visual_lab.core import ACTIONS
from visual_lab.image_ablation import verify_image_response
from visual_lab.jev import verify_jev_response
from tools.freeze_text_study import body_sha256
ROOT=Path('/Users/Zhuanz/Documents/zb/share-2026-10-03/2/isaac_visual_decision');folder=Path('/private/var/folders/38/gc519q3j3p96d90ybwr3whvm0000gq/T/opencode/ivd-text-study-os9yxtix');E=folder/'evidence';review=json.loads((ROOT/'test_reports/text_study_input_review_20261007.json').read_text());remote=json.loads((E/'text_study_30_31_lifecycle.json').read_text());vendor=json.loads((E/'jev_32_lifecycle.json').read_text());frozen=json.loads((E/'text_study_42_frozen/manifest.json').read_text())
assert remote['complete'] and not vendor['complete'] and vendor['api_completed']==0 and vendor['http_prediction_attempts']==1
assert remote['own_service_stopped'] and remote['gpu_compute_processes_after']=='' and not remote['new_isaac_process_started'] and not vendor['new_isaac_process_started']
assert frozen['frozen_utc']<remote['groups']['zh']['started_utc'] and review['frozen_utc']<frozen['frozen_utc']<vendor['started_utc']
for k in ['requests','planned_order','http_body_sha256','code_sha256','request_sha256','wire_request_sha256']:assert frozen[k]==review[k]
groups={};paths={'zh':'30_goal_name_binding','en':'31_english_bound_intern'};artifact_hashes={};num=lambda t:re.findall(r'[-+]?\d+(?:\.\d+)?',t)
for g,batch in paths.items():
 p=E/batch;m=json.loads((p/'manifest.json').read_text());s=json.loads((p/'summary.json').read_text());final=json.loads((p/'final_health.json').read_text());assert s['complete'] and s['api_completed']==len(s['decisions'])==14 and s['error'] is None
 assert not s['mock_backend'] and not s['model_had_control'];assert final['requests_completed']-m['model_health']['requests_completed']==14
 if g!='jev':assert m['model_health']['device']=='cuda' and m['model_health']['dtype']=='bfloat16' and m['model_health']['temperature']==1.99241824
 assert [r['name'] for r in s['decisions']]==[j['name'] for j in review['planned_order'] if j['group']==g];requests={};responses={}
 for r in s['decisions']:
  n=r['name'];request_path=p/'requests'/(n+'.json');response_path=p/'responses'/(n+'.json');q=json.loads(request_path.read_text());raw=json.loads(response_path.read_text());assert sha256_file(request_path)==r['request_sha256']==review['request_sha256'][g][n];assert sha256_file(response_path)==r['response_sha256'];assert q==review['requests'][g][n] and q['images']==q['state']['camera_views']==[]
  assert set(q)=={'state','images','questions'} and tuple(q['questions']['next_stage']['criteria'])==ACTIONS
  wire=q if g!='jev' else json.loads((p/'wire_requests'/(n+'.json')).read_text());assert body_sha256(wire)==review['http_body_sha256'][g][n]
  parsed=verify_image_response([],raw,m['model_health']) if g!='jev' else verify_jev_response(raw);assert parsed.action==r['proposed_action'] and parsed.probabilities==r['probabilities'] and parsed.confidence==r['confidence']
  assert r['top_probability_ties']==[a for a in ACTIONS if parsed.probabilities[a]==max(parsed.probabilities.values())]
  old=m['reference']['requests'][n]
  if g=='zh':
   prefix='task中的'+('蓝色' if r['cell'].startswith('blue') else '黄色')+'方形轮廓线就是本goal_guidance中配置的地面框；“内部”指该轮廓线围成的地面区域。';restored=copy.deepcopy(q);description=restored['state']['goal_guidance']['spatial_description'];assert description==prefix+old['state']['goal_guidance']['spatial_description'];restored['state']['goal_guidance']['spatial_description']=old['state']['goal_guidance']['spatial_description'];assert restored==old
  else:
   assert not re.search(r'[\u4e00-\u9fff]',json.dumps(q,ensure_ascii=False))
   for k in ['previous_action','previous_result','finger_joint_position_rad','gripper_command_reference_rad','camera_views']:assert q['state'][k]==old['state'][k]
   for k in ['ee_position_description']:assert num(q['state'][k])==num(old['state'][k])
   assert num(q['state']['goal_guidance']['spatial_description'])==num(old['state']['goal_guidance']['spatial_description'])
  if g=='jev':
   assert set(wire)=={'model','state','questions'} and wire['model']=='jev-1.13.0' and wire['state']==q['state'] and wire['questions']==q['questions'];assert raw['model']=='jev-1.13.0';assert q==groups['en']['requests'][n]
  requests[n]=q;responses[n]=raw
 for path in p.rglob('*'):
  if path.is_file():artifact_hashes[str(path.relative_to(E))]=sha256_file(path)
 groups[g]={'manifest':m,'summary':s,'final_health':final,'requests':requests,'responses':responses,'mean_http_latency_ms':statistics.mean(r['http_latency_ms'] for r in s['decisions']),'mean_reference_probability':statistics.mean(r['probabilities'][r['expected_action']] for r in s['decisions'])}
comparisons=[]
for factor,lo,hi in [('binding','old','zh'),('language','zh','en')]:
 for c in ['blue','yellow']:
  stages=[]
  for j in range(1,8):
   name=f'{c}_images_0_decision_{j:03d}';a=next(r for r in (groups['zh']['manifest']['reference']['rows'] if lo=='old' else groups[lo]['summary']['decisions']) if r['name']==name);b=next(r for r in groups[hi]['summary']['decisions'] if r['name']==name);expected=a['expected_action'];assert expected==b['expected_action'];stages.append({'stage':j,'expected':expected,'low_choice':a['proposed_action'],'high_choice':b['proposed_action'],'low_reference_probability':a['probabilities'][expected],'high_reference_probability':b['probabilities'][expected],'delta':b['probabilities'][expected]-a['probabilities'][expected]})
  comparisons.append({'factor':factor,'color':c,'low':lo,'high':hi,'low_agreement':sum(r['low_choice']==r['expected'] for r in stages),'high_agreement':sum(r['high_choice']==r['expected'] for r in stages),'mean_reference_probability_delta':statistics.mean(r['delta'] for r in stages),'stages':stages})
for path in E.glob('*.json'):artifact_hashes[path.name]=sha256_file(path)
halted=E/'32_english_bound_jev';halt_summary=json.loads((halted/'summary.json').read_text());assert not halt_summary['complete'] and halt_summary['api_completed']==0 and halt_summary['decisions']==[]
assert list((halted/'responses').glob('*.json'))==[]
for name,h in review['request_sha256']['jev'].items():
 assert sha256_file(halted/'requests'/(name+'.json'))==h
 q=json.loads((halted/'requests'/(name+'.json')).read_text());wire=json.loads((halted/'wire_requests'/(name+'.json')).read_text())
 assert q==groups['en']['requests'][name] and body_sha256(wire)==review['http_body_sha256']['jev'][name]
for path in halted.rglob('*'):
 if path.is_file():artifact_hashes[str(path.relative_to(E))]=sha256_file(path)
first=next(j for j in review['planned_order'] if j['group']=='jev');first_wire=json.loads((halted/'wire_requests'/(first['name']+'.json')).read_text())
write_json(ROOT/'test_reports/jev_first_request_20261007.json',first_wire)
failure={'complete':False,'inference_attempts':1,'validated_decisions':0,'first_job':first,'error':halt_summary['error'],'raw_response_retained':False,'probability_values':None,'usage':None,'response_model':None,'cause_detail':'Original JSON not recoverable: pre-fix JevClient verified before runner persistence. Cannot distinguish invalid API probability data from client/API compatibility without original body. No normalization, prompt edit or retry.','lifecycle':vendor,'gate':json.loads((E/'jev_32_gate.json').read_text()),'first_request_sha256':sha256_file(ROOT/'test_reports/jev_first_request_20261007.json')}
write_json(ROOT/'test_reports/jev_failure_20261007.json',failure)
record={'complete':False,'partial_evidence_verified':True,'planned_count':42,'verified_new_inferences':28,'intern_cuda_bf16_count':28,'jev_http_prediction_attempts':1,'jev_validated_decisions':0,'unattempted_jev_requests':13,'intern_no_image_audit_count':28,'english_preplanned_identical_state_questions_count':14,'chinese_single_field_only_count':14,'all28_completed_preflight_request_and_body_hashes_match':True,'all14_jev_planned_input_hashes_match':True,'automatic_retries':0,'mock_responses':0,'new_isaac_process_started':False,'model_had_control':False,'implementation_commit':remote['implementation_commit'],'remote_evidence_bundle_sha256':sha256_file(folder/'remote_evidence.tar.gz'),'remote_lifecycle':remote,'jev_lifecycle':vendor,'jev_failure':failure,'freeze_manifest':frozen,'groups':groups,'comparisons':comparisons,'artifact_sha256':artifact_hashes,'limitations':['28new valid suggestions on14correlated frozen scene/color states, not autonomous success/generalization.','No Jev model comparison or probability/calibration/latency/price scoring; first invalid response lost before archival.','No new Isaac GPU physics/rendering verification; original25capture reused.','No new request to recover missing Jev body; safe response-retention code fixed AFTER halted batch, CPU-only verification.','Prompt IDs retain20261006 convention, actual inference times2026-10-07UTC.']}
write_json(ROOT/'test_reports/gpu_text_study_partial_20261007.json',record);print(json.dumps({'comparisons':comparisons,'jev_failure':failure,'latencies':{g:d['mean_http_latency_ms'] for g,d in groups.items()}},ensure_ascii=False,indent=2))
