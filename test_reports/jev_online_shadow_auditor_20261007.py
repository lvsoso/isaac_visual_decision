"""Offline audit and self-contained evidence page; never call a model or Isaac."""
import argparse,base64,hashlib,html,json,re,statistics
from pathlib import Path
from PIL import Image
from visual_lab.audit import sha256_file,write_json
from visual_lab.core import ACTIONS,judge_episode
from visual_lab.jev import JEV_MODEL,jev_payload,verify_jev_response
from visual_lab.jev_shadow import ONLINE_INSTRUCTIONS,control_gate
from visual_lab.text_english import EN_CRITERIA
from visual_lab.prompt_variants import position_cm

def audit(evidence,plan_path,output,report):
    plan=json.loads(plan_path.read_text());life=json.loads((evidence/'jev_shadow_20261007_lifecycle.json').read_text())
    assert life['plan_sha256']==sha256_file(plan_path)
    assert life['launch_environment']=={'OMNI_KIT_ALLOW_ROOT':'1','LD_LIBRARY_PATH':''}
    runs=[];all_decisions=[];request_ids=set()
    for recorded in life['runs']:
        directory=evidence/Path(recorded['run_dir']).name
        if not (directory/'summary.json').exists():
            runs.append({'color':recorded['color'],'complete':False,'reason':'No episode summary','control_eligible':False});continue
        summary=json.loads((directory/'summary.json').read_text());manifest=json.loads((directory/'manifest.json').read_text())
        assert manifest['kind']=='jev_online_shadow' and manifest['model_had_control'] is False
        assert manifest['source_sha256']==plan['source_sha256']
        config_path=Path(__file__).resolve().parents[1]/'configs/default.json'
        assert sha256_file(config_path)==plan['config_sha256']
        assert manifest['config']==json.loads(config_path.read_text())
        assert manifest['worker_python']==plan['worker_python'] and manifest['worker_ld_library_path']==''
        events=[json.loads(line) for line in (directory/'events.jsonl').read_text().splitlines() if line.strip()]
        observations={r['decision_id']:r for r in events if r['kind']=='observation'}
        decisions=[r for r in events if r['kind']=='decision'];frozen={r['decision_id']:r for r in events if r['kind']=='api_frozen_state'}
        phase=[r for r in events if r['kind']=='phase_end'];runtime=next((r for r in events if r['kind']=='runtime'),None)
        if runtime is not None:
            assert runtime['simulation_device']=='cuda' and runtime['active_gpu']==0
            assert runtime['physics_pose_sync']['fabric_enabled'] is False and runtime['physics_pose_sync']['update_to_usd'] is True and runtime['physics_pose_sync']['suppress_readback'] is False
        rows=[]
        for d in decisions:
            index=d['decision_id'];obs=observations[index];png=directory/obs['image'];request_path=directory/'requests'/f'decision_{index:03d}.json';response_path=directory/'responses'/f'decision_{index:03d}.json';http=directory/'http_evidence'/f'decision_{index:03d}'
            request=json.loads(request_path.read_text());response=json.loads(response_path.read_text());raw_body=(http/'response.body').read_bytes();wire_body=(http/'request.body').read_bytes();meta=json.loads((http/'response_meta.json').read_text())
            assert sha256_file(png)==obs['image_sha256'];image=Image.open(png);assert list(image.size)==manifest['config']['camera']['resolution'];assert image.mode in ['RGB','RGBA']
            assert request['images']==request['state']['camera_views']==[]
            assert set(request['state'])=={'task','observation','previous_action','previous_result','ee_reference','finger_joint_position_rad','gripper_command_reference_rad','limitations','camera_views','ee_position_description','goal_guidance'}
            assert set(request['state']['goal_guidance'])=={'source','controller_tool_frame','spatial_description','reference_warning'}
            assert request['state']['task']==f'Place the red cube inside the {recorded["color"]} square ground outline, then release it.'
            assert request['questions']=={'next_stage':{'type':'choice','instructions':ONLINE_INSTRUCTIONS,'criteria':EN_CRITERIA}}
            assert not re.search(r'[\u4e00-\u9fff]',json.dumps(request,ensure_ascii=False))
            assert request['state']['ee_position_description']=='Finger-link world position approximately '+position_cm(obs['model_state']['ee_world_position_m'])+' cm; not the grasp or cube center.'
            assert request['state']['previous_action']==(None if index==1 else ACTIONS[index-2]);assert request['state']['previous_result']==(None if index==1 else 'reached')
            assert request['state']['finger_joint_position_rad']==obs['model_state']['finger_joint_position_rad']
            assert json.loads(wire_body)==jev_payload(request);assert json.loads(raw_body)==response
            marker=json.loads((http/'CALL_STARTED.json').read_text());assert marker['request_body_sha256']==sha256_file(http/'request.body') and marker['automatic_retries']==0
            assert meta['status_code']==200 and meta['saved_before_business_validation'] and meta['body_sha256']==sha256_file(http/'response.body')
            assert meta['request_id'] and meta['request_id'] not in request_ids
            request_ids.add(meta['request_id'])
            parsed=verify_jev_response(response);assert parsed.action==d['proposed_action'] and parsed.probabilities==d['probabilities'] and parsed.confidence==d['confidence']
            assert d['executed_action']==ACTIONS[index-1] and d['model_had_control'] is False and d['image_count_sent']==0
            snapshot=frozen[index];assert snapshot['physical_state_unchanged'] and snapshot['before']==snapshot['after']
            rows.append({'index':index,'expected_and_executed_action':d['executed_action'],'proposed_action':d['proposed_action'],
                'probabilities':d['probabilities'],'confidence':d['confidence'],'http_latency_ms':d['http_latency_ms'],
                'request':request,'response':response,'actual_wire_body_text':wire_body.decode(),'raw_http_body_text':raw_body.decode(),'http_meta':meta,
                'png_sha256':sha256_file(png),'image_sent_to_model':False,'png_base64_audit_only':base64.b64encode(png.read_bytes()).decode(),
                'physical_state_unchanged':True,'private_physical_snapshot':snapshot,'phase_outcome':next(r for r in phase if r['decision_id']==index)})
        if summary.get('complete'):
            assert runtime is not None and summary['error'] is None
            assert recorded['process_returncode']==0 and summary['model_had_control'] is False and summary['strict_success_is_executor_only'] is True
            assert len(decisions)==len(rows)==summary['api_attempts']==summary['api_completed']==7
            assert summary['executed_actions']==list(ACTIONS[:-1]);assert [r['action'] for r in phase]==list(ACTIONS[:-1])+['retract']
            assert all(r['status']=='reached' for r in phase)
            assert summary['physics_updates']>=manifest['config']['warmup_frames']+manifest['config']['settle_frames']+sum(r['frames'] for r in phase)
            expected=judge_episode(summary['final_cube_position_m'],manifest['config'],released=True,timed_out=False,termination_reason='completed')
            assert expected['strict_success']==summary['strict_success'] and expected['strict_success'] is True
            agreement=sum(r['proposed_action']==r['expected_and_executed_action'] for r in rows);assert agreement==summary['shadow_reference_agreement']
            assert summary['control_gate']==control_gate(summary)
        else:agreement=sum(r['proposed_action']==r['expected_and_executed_action'] for r in rows)
        run={'color':recorded['color'],'complete':summary.get('complete',False),'summary':summary,'manifest':manifest,'runtime':runtime,
             'agreement':agreement,'num_verified_decisions':len(rows),'control_eligible':summary.get('complete',False) and summary.get('control_gate',{}).get('eligible',False),
             'decisions':rows,'private_evaluation_separate_from_model_input':True}
        runs.append(run);all_decisions.extend(rows)
    complete=life['complete'] and len(runs)==2 and all(r['complete'] for r in runs)
    payload={'kind':'real_isaac_gpu_jev_online_shadow_audit','complete':complete,'independently_verified':True,'runs':runs,'lifecycle':life,
        'new_jev_verified_calls':len(all_decisions),'cloud_model_version':JEV_MODEL,'model_had_control':False,'isaac_gpu_executed':any(r.get('runtime') for r in runs),
        'isaac_physical_success_is_fixed_executor_only':True,'whole_pair_control_eligible':complete and all(r['control_eligible'] for r in runs),
        'max_jev_predictions_authorized':14,'automatic_retries':0,'plan_sha256':sha256_file(plan_path),'criteria_unchanged_from_offline':True,
        'distinct_http_request_ids':len(request_ids),
        'offline_to_online_context_wording_change_frozen':True,'wall_latency_median_ms':statistics.median(r['http_latency_ms'] for r in all_decisions) if all_decisions else None,
        'source_and_live_geometry_verification_scope':'Frozen source computes target/FK guidance from current measured joints; audit verifies actual serialized inputs, raw responses, finger-position rendering, executed phases, paused-state invariance and final private cube score. It does not independently rerun kinematics from saved joint arrays.',
        'scope':'Shadow suggestions only; fixed executor controls every action. Not autonomous task success or modelcontrol authorization.'}
    write_json(output,payload)
    esc=lambda v:html.escape(json.dumps(v,ensure_ascii=False,indent=2))
    page=['<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta http-equiv="Content-Security-Policy" content="default-src \'none\'; img-src data:; style-src \'unsafe-inline\'; connect-src \'none\'"><title>Jev真实Isaac在线影子验证</title><style>body{font:15px/1.7 system-ui;background:#0d1518;color:#e1e9ec;max-width:1150px;margin:28px auto;padding:0 22px}section{border:1px solid #32454c;padding:18px;margin:20px 0}img{max-width:100%;width:640px}pre{white-space:pre-wrap;overflow-wrap:anywhere;font-size:12px}table{border-collapse:collapse;width:100%}th,td{border-bottom:1px solid #32454c;text-align:left;padding:8px}.scroll{overflow:auto}</style>',
          '<h1>Jev真实Isaac在线影子验证</h1><p>相机图像仅供审计，未送给Jev。模型只建议，机械臂始终由固定执行器控制。7/7只是后续接管候选门槛，不是已验证模型自主抓放。</p>',
          f'<p>新验证调用：{len(all_decisions)}；整体候选资格：{payload["whole_pair_control_eligible"]}；模型实际接管：False</p>']
    for r in runs:
        page.append(f'<section><h2>{r["color"]}：{r.get("agreement",0)}/7 · 接管候选资格 {r["control_eligible"]}</h2><pre>{esc(r.get("summary",r))}</pre></section>')
        for row in r.get('decisions',[]):
            page.append(f'<section><h3>{r["color"]} / 状态 {row["index"]} · 建议 {row["proposed_action"]} / 实际固定动作 {row["expected_and_executed_action"]}</h3><p>真实Isaac审计帧，未送模型</p><img alt="真实Isaac审计帧，非模型输入" src="data:image/png;base64,{row["png_base64_audit_only"]}"><div class="scroll"><table><tr><th>候选</th><th>原始返回概率</th></tr>')
            for action in ACTIONS:page.append(f'<tr><td>{action}</td><td>{repr(row["probabilities"][action])}</td></tr>')
            page.append('</table></div>')
            for title,key in [('实际无图输入','request'),('原始HTTP响应正文','raw_http_body_text'),('HTTP状态／request ID／哈希','http_meta'),('固定执行阶段结果','phase_outcome')]:page.append(f'<details><summary>{title}</summary><pre>{esc(row[key])}</pre></details>')
            page.append('</section>')
    page.append(f'<details><summary>冻结与进程生命周期</summary><pre>{esc(life)}</pre></details></body></html>')
    report.write_text('\n'.join(page));return payload

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ['evidence','plan_path','output','report']:parser.add_argument('--'+name.replace('_','-'),type=Path,required=True)
    args=parser.parse_args();p=audit(**vars(args));print(json.dumps({'complete':p['complete'],'new_calls':p['new_jev_verified_calls'],'whole_pair_control_eligible':p['whole_pair_control_eligible'],'runs':[{k:r.get(k) for k in ['color','agreement','control_eligible']} for r in p['runs']]},ensure_ascii=False,indent=2))
