"""Offline audit/build of actual dual-view shadow/control evidence, no inference."""
import argparse,base64,html,json,statistics
from pathlib import Path
from PIL import Image
from visual_lab.audit import sha256_file,write_json
from visual_lab.candidate_control import audit_shadow,candidate_request,code_hashes,health_identity,pinned_health
from visual_lab.core import ACTIONS,judge_episode
from visual_lab.prompt_variants import verify_response

ROOT=Path(__file__).resolve().parents[1]
def verify_frozen_plan(archived_path,expected_path):
    plan=json.loads(Path(archived_path).read_text())
    assert plan==json.loads(Path(expected_path).read_text()),'Archived plan must match the explicitly selected frozen batch'
    return plan

def audit_reused(evidence,plan,life,config):
    records=[];originals=life.get('reused_shadows',[])
    assert len(originals)==len(plan.get('reused_shadows',[]))
    for planned,original in zip(plan.get('reused_shadows',[]),originals):
        record=audit_shadow(Path(evidence)/Path(planned['run_dir']).name,config,pinned_health())
        assert record['color']==planned['color'] and record['files_sha256']==planned['files_sha256']
        assert {k:v for k,v in record.items() if k!='directory'}=={k:v for k,v in original.items() if k!='directory'}
        records.append(record)
    return records

def verify_admission_timing(evidence,plan,life):
    ends=[r['ended_utc'] for r in life['runs'] if r['mode']=='shadow']
    for record in plan.get('reused_shadows',[]):
        events=Path(evidence)/Path(record['run_dir']).name/'events.jsonl'
        ends.append(max(json.loads(line)['utc'] for line in events.read_text().splitlines()))
    assert max(ends)<=min(r['started_utc'] for r in life['runs'] if r['mode']=='control')

def audit_recording(directory,manifest,summary,plan):
    assert manifest['recording_entry_sha256']==plan['source_sha256']['run_candidate_recording.py']
    interval=manifest['record_every'];config=manifest['config'];frames=sorted((directory/'frames').glob('frame_*.png'))
    assert type(interval) is int and interval>0
    count=summary['physics_updates']//interval-config['warmup_frames']//interval
    assert len(frames)==summary['recorded_frames']==count and count>0
    assert [p.name for p in frames]==[f'frame_{i:06d}.png' for i in range(count)]
    for path in frames:
        with Image.open(path) as image:
            assert list(image.size)==config['camera']['resolution'];image.verify()
    fps=1/(config['physics_dt']*interval)
    return {'frame_count':count,'fps':fps,'playback_seconds':count/fps,'api_waits_omitted':True,
        'files_sha256':{str(p.relative_to(directory)):sha256_file(p) for p in frames}}

def audit(evidence,output,report,plan_path=None):
    expected_path=plan_path or ROOT/'test_reports/candidate_control_plan_20261007.json'
    evidence=Path(evidence);plan_path=evidence/'experiment/plan.json';plan=json.loads(plan_path.read_text())
    life=json.loads((evidence/'experiment/lifecycle.json').read_text());config=json.loads((ROOT/'configs/default.json').read_text())
    assert life['plan_sha256']==sha256_file(plan_path)
    verify_frozen_plan(plan_path,expected_path)
    assert life['launch_environment']=={'OMNI_KIT_ALLOW_ROOT':'1','LD_LIBRARY_PATH':''}
    assert plan['control_authorized'] is True and plan['physical_hardware_authorized'] is False
    assert life['source_sha256']=={name:plan['source_sha256'][name] for name in life['source_sha256']}
    reused=audit_reused(evidence,plan,life,config)
    runs=[];shadow_checks=list(reused);latencies=[];new_calls=0
    for record in life['runs']:
        directory=evidence/Path(record['run_dir']).name
        if not (directory/'manifest.json').exists():
            assert record['service_count_after']==record['service_count_before']
            runs.append({**record,'offline_verified':False,'reason':'No episode artifacts'});continue
        manifest=json.loads((directory/'manifest.json').read_text());summary=json.loads((directory/'summary.json').read_text())
        assert manifest['mode']==record['mode'] and manifest['goal_color']==record['color'] and manifest['variant']==plan['variant']
        assert manifest['source_sha256']==code_hashes() and manifest['config']==config
        assert manifest['launch_environment']==life['launch_environment']
        assert health_identity(manifest['model_health'])==health_identity(pinned_health())==plan['model_identity']
        assert summary==record['summary'];events=[json.loads(line) for line in (directory/'events.jsonl').read_text().splitlines()]
        observations=[e for e in events if e['kind']=='paired_observation'];decisions=[e for e in events if e['kind']=='decision'];phases=[e for e in events if e['kind']=='phase_end']
        frozen={e['decision_id']:e for e in events if e['kind']=='api_frozen_state'};runtime=next((e for e in events if e['kind']=='runtime'),None)
        if observations:assert runtime is not None and runtime['simulation_device']=='cuda'
        assert summary['api_attempts']<=record['max_decisions'];new_calls+=summary['api_attempts'];rows=[]
        previous=None;previous_result=None
        for d in decisions:
            index=d['decision_id'];obs=next(e for e in observations if e['decision_id']==index);pngs=[];images=[]
            for view,asset in enumerate(obs['images'],1):
                path=directory/asset['path'];assert sha256_file(path)==asset['sha256']
                with Image.open(path) as image:assert list(image.size)==config['camera']['resolution']
                pngs.append(path.read_bytes());images.append({'path':asset['path'],'sha256':asset['sha256'],'png_base64':base64.b64encode(path.read_bytes()).decode()})
            req=json.loads((directory/f'requests/decision_{index:03d}.json').read_text());raw=json.loads((directory/f'responses/decision_{index:03d}.json').read_text())
            assert req==candidate_request(pngs,obs['model_state'],config,obs['goal_guidance'],record['color'])
            assert req['state']['previous_action']==previous and req['state']['previous_result']==previous_result
            parsed=verify_response(pngs,raw,manifest['model_health']);assert parsed.action==d['proposed_action']
            assert parsed.probabilities==d['probabilities'] and parsed.confidence==d['confidence']
            assert frozen[index]['physical_state_unchanged'] and frozen[index]['before']==frozen[index]['after']==obs['frozen_state']
            if record['mode']=='control':assert d['executed_action']==parsed.action and d['model_had_control'] is True
            else:assert d['executed_action']==('abort' if parsed.action=='abort' else ACTIONS[index-1]) and d['model_had_control'] is False
            assert d['service_count']==record['service_count_before']+index
            outcome=next((p for p in phases if p['decision_id']==index),None)
            if d['executed_action']=='abort':assert outcome is None
            else:
                assert outcome is not None and outcome['action']==d['executed_action'];previous=d['executed_action'];previous_result=outcome['status']
            latencies.append(d['http_latency_ms']);rows.append({'index':index,'proposed_action':parsed.action,'executed_action':d['executed_action'],
                'probabilities':parsed.probabilities,'confidence':parsed.confidence,'http_latency_ms':d['http_latency_ms'],'images':images,
                'request':req,'response':raw,'phase_outcome':outcome,'private_frozen_state':frozen[index]})
        assert [r['proposed_action'] for r in rows]==summary['proposed_actions']
        assert [r['executed_action'] for r in rows]==summary['executed_actions']
        assert record['service_count_after']-record['service_count_before']==summary['api_completed']
        if summary['complete']:
            assert record['process_returncode']==0 and summary['error'] is None and summary['strict_success'] is True
            assert len(rows)==summary['api_attempts']==summary['api_completed']
            assert phases[-1]['action']=='retract' and phases[-1]['status']=='reached'
            assert summary['physics_updates']==config['warmup_frames']+sum(p['frames'] for p in phases)+config['settle_frames']
            evaluated=judge_episode(summary['final_cube_position_m'],config,released=True,timed_out=False,termination_reason='completed')
            assert evaluated['strict_success'] is True
        gate=None
        if record['mode']=='shadow' and summary['complete'] and summary['shadow_reference_agreement']==7:
            gate=audit_shadow(directory,config,manifest['model_health']);shadow_checks.append(gate)
        runs.append({'mode':record['mode'],'color':record['color'],'run_dir':record['run_dir'],'summary':summary,'manifest':manifest,
            'runtime':runtime,'decisions':rows,'offline_verified':True,'shadow_admission_eligible':gate is not None})
        if manifest.get('record_every'):runs[-1]['recording']=audit_recording(directory,manifest,summary,plan)
    control_runs=[r for r in runs if r['mode']=='control'];shadow_runs=[r for r in runs if r['mode']=='shadow']
    if life['control_started']:
        proof_path=evidence/'experiment/admission.json';proof=json.loads(proof_path.read_text())
        assert life['admission_sha256']==sha256_file(proof_path) and len(shadow_checks)==2
        assert proof['source_sha256']==code_hashes() and proof['config']==config and proof['model_identity']==plan['model_identity']
        assert proof['eligible'] and {r['color'] for r in proof['runs']}=={'blue','yellow'}
        for original in proof['runs']:
            audited=next(r for r in shadow_checks if r['color']==original['color']);assert {k:v for k,v in original.items() if k!='directory'}=={k:v for k,v in audited.items() if k!='directory'}
        for r in control_runs:
            assert r['manifest']['admission']==proof and r['summary']['model_had_control'] is True
        verify_admission_timing(evidence,plan,life)
    else:assert not control_runs
    assert new_calls<=plan['max_prediction_calls'] and life['automatic_retries']==0
    if life.get('final_health'):assert life['final_health']['requests_completed']==new_calls
    payload={'kind':'real_gpu_intern_dual_shadow_and_conditional_control','complete':life['complete'],'new_model_predictions':new_calls,
        'shadow_launch_attempts':len(shadow_runs),'shadow_runs':sum(r.get('offline_verified',False) for r in shadow_runs),'control_runs':len(control_runs),'shadow_pair_eligible':len(shadow_checks)==2,
        'model_control_started':life['control_started'],'control_physical_successes':sum(r['summary']['complete'] and r['summary']['strict_success'] for r in control_runs),
        'offline_evidence_verified':True,'model_choice_executed_without_reselection':bool(control_runs),'lifecycle':life,'plan':plan,'runs':runs,
        'http_wait_median_ms':statistics.median(latencies) if latencies else None,'scope':'One known fixed Isaac scene; model selects existing skills, controller targets configured. Not perturbation recovery/generalization/hardware validation.',
        'model_service_loaded_on_gpu':bool(life.get('initial_health')),'isaac_scene_verified':any(r.get('runtime') for r in runs),
        'gpu_evidence_source':'Remote service and launcher logs; only episode runtime records, when present, support Isaac execution. This offline script does not generate GPU evidence.'}
    if reused:
        payload.update(reused_shadow_evidence=reused,reused_shadow_runs=len(reused),reused_model_predictions=sum(r['summary']['api_completed'] for r in reused),
            reused_is_not_new_inference=True)
    write_json(output,payload);render(payload,report);return payload

def render(payload,report):
    esc=lambda v:html.escape(json.dumps(v,ensure_ascii=False,indent=2))
    page=['<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta http-equiv="Content-Security-Policy" content="default-src \'none\'; img-src data:; style-src \'unsafe-inline\'; connect-src \'none\'"><title>Intern双视角：在线shadow与受限仿真接管</title><style>body{font:15px/1.7 system-ui;max-width:1200px;margin:24px auto;padding:0 20px;background:#101a20;color:#e2edf2}section{border:1px solid #354a55;padding:16px;margin:18px 0}.views{display:flex;flex-wrap:wrap;gap:10px}.views img{max-width:100%;width:540px}pre{white-space:pre-wrap;overflow-wrap:anywhere;font-size:12px}table{border-collapse:collapse;width:100%}td,th{padding:5px;border-bottom:1px solid #354a55;text-align:left}</style>',
        '<h1>Intern双视角：在线shadow与受限仿真接管</h1><p>固定Intern-Decision-4B、中文空间描述、两张同时视图。shadow由固定执行器推进；control由模型选择既有技能，低层目标仍来自配置。Jev排除。</p>',
        f'<p>真实新推理 {payload["new_model_predictions"]} 次；shadow {payload["shadow_runs"]} 回合；模型接管 {payload["control_runs"]} 回合；接管物理成功 {payload["control_physical_successes"]} 回合。</p>',
        '<p>只验证已观察的固定Isaac场景。不代表独立泛化、扰动恢复或实体机械臂安全。完整原输入、响应、八概率与审计帧保留，无归一化或重选choice。</p>']
    if payload.get('reused_shadow_evidence'):
        page.append(f'<p>另复用既有蓝色shadow：{payload["reused_model_predictions"]}次历史调用，未重跑、不计入新推理。逐文件哈希与原始响应已独立复核。</p>')
        page.append(f'<details><summary>复用蓝色41准入证据</summary><pre>{esc(payload["reused_shadow_evidence"])}</pre></details>')
    for run in payload['runs']:
        title=f'{run["mode"]} / {run["color"]}';summary=run.get('summary',{})
        page.append(f'<section><h2>{title}</h2><pre>{esc(summary)}</pre></section>')
        for row in run.get('decisions',[]):
            page.append(f'<section><h3>{title} / {row["index"]}：模型 {row["proposed_action"]} · 执行 {row["executed_action"]}</h3><div class="views">')
            for index,image in enumerate(row['images'],1):page.append(f'<img alt="{title} 状态{row["index"]} 同时视角{index}，实际模型输入" src="data:image/png;base64,{image["png_base64"]}">')
            page.append('</div><table><tr><th>八候选</th><th>原始模型概率</th></tr>')
            for action in ACTIONS:page.append(f'<tr><td>{action}</td><td>{repr(row["probabilities"][action])}</td></tr>')
            page.append('</table>')
            for detail_title,key in [('实际双图输入','request'),('原始服务响应','response'),('物理执行结果','phase_outcome'),('等待期间私有快照，仅作审计','private_frozen_state')]:page.append(f'<details><summary>{detail_title}</summary><pre>{esc(row[key])}</pre></details>')
            page.append('</section>')
    page.append(f'<details><summary>准入／进程／冻结计划</summary><pre>{esc({k:payload[k] for k in ["lifecycle","plan"]})}</pre></details></body></html>')
    report.write_text('\n'.join(page))

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ['evidence','output','report']:parser.add_argument('--'+name,type=Path,required=True)
    parser.add_argument('--plan-path',type=Path,help='Explicit immutable batch plan; defaults to original aborted batch')
    payload=audit(**vars(parser.parse_args()));print(json.dumps({k:v for k,v in payload.items() if k not in ['runs','lifecycle','plan']},ensure_ascii=False,indent=2))
