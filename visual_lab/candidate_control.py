"""Pinned Chinese dual-view live shadow and user-authorized gated skill control."""
from __future__ import annotations
import copy,json,time
from pathlib import Path
from .audit import sha256_file,write_json
from .client import ModelAPIError
from .core import ACTIONS,ProtocolError,judge_episode,model_state
from .factorial import GOAL_COLORS,camera_configs,goal_guidance,view_metadata
from .prompt_variants import STABLE_HEALTH_KEYS,prompt_request,verify_response

ROOT=Path(__file__).resolve().parents[1]
CONTROL_MAX_DECISIONS=10
VARIANT='zh_named_relative'

def code_hashes():
    return {str(p.relative_to(ROOT)):sha256_file(p) for p in
        [ROOT/'run_candidate.py',ROOT/'serve_model.py',*sorted((ROOT/'visual_lab').glob('*.py'))]}

def pinned_health():
    return json.loads((ROOT/'test_reports/gpu_modality_prompts_20261006.json').read_text())['manifest']['model_health']

def health_identity(health):
    return {key:copy.deepcopy(health.get(key)) for key in STABLE_HEALTH_KEYS}

def check_health(health):
    if (health.get('busy') or health.get('status')!='ok' or health.get('bridge_schema')!=1
            or not health.get('supports_images') or health_identity(health)!=health_identity(pinned_health())):
        raise ProtocolError('Require idle pinned official Intern CUDA/BF16 dual-view source and calibration')
    if type(health.get('requests_completed')) is not int:
        raise ProtocolError('Require an integer service inference counter')
    return health

def candidate_request(pngs,state,config,guidance,color):
    return prompt_request(pngs,state,view_metadata(config),guidance,{'variant':VARIANT,'color':color})

def run_candidate(scene,cameras,config,color,mode,log,client,*,admission=None):
    if mode not in {'shadow','control'} or color not in GOAL_COLORS:
        raise ProtocolError('Only pinned blue/yellow shadow or control is supported')
    start=time.perf_counter();previous_action=previous_result=None
    attempts=completed=0;proposed=[];executed=[];timed_out=released=had_control=False
    error=None;reason='decision_limit'
    limit=7 if mode=='shadow' else CONTROL_MAX_DECISIONS
    try:
        health=check_health(client.health(allow_mock=False));initial_count=health['requests_completed']
        log.event('model_health',health=health)
        if mode=='control':
            if admission is None:raise ProtocolError('Two real online seven-of-seven shadow runs required')
            proof=validate_admission(Path(admission),config,health)
            log.event('admission_verified',proof=proof);had_control=True
        target=scene.placement_tool_target()
        for index in range(1,limit+1):
            scene.timeline.pause();pngs=scene.capture_views(cameras)
            if len(pngs)!=2:raise ProtocolError('Exactly two live simultaneous views required')
            before=scene.frozen_state();state=model_state(scene.proprioception(),previous_action,previous_result)
            guidance=goal_guidance(config['target_position_m'],target,scene._controller_tool_world_position(),scene.scenario._tool_frame)
            request=candidate_request(pngs,state,config,guidance,color)
            images=[]
            for view,png in enumerate(pngs,1):
                path=log.root/'images'/f'decision_{index:03d}_view{view}.png';path.write_bytes(png)
                images.append({'path':str(path.relative_to(log.root)),'sha256':sha256_file(path)})
            log.event('paired_observation',decision_id=index,images=images,model_state=state,goal_guidance=guidance,
                private_ground_truth=scene.private_truth(),frozen_state=before)
            log.request(index,request);attempts+=1
            raw,ms=client.predict(request);log.response(index,raw)
            prediction=verify_response(pngs,raw,health);completed+=1;proposed.append(prediction.action)
            after=scene.frozen_state();log.event('api_frozen_state',decision_id=index,before=before,after=after,physical_state_unchanged=before==after)
            if before!=after:raise ProtocolError('Physics changed during model wait; no motion authorized')
            current=check_health(client.health(allow_mock=False))
            if current['requests_completed']!=initial_count+completed:
                raise ProtocolError('Unexpected service inference count; no concurrent inference or retry allowed')
            action=prediction.action if mode=='control' or prediction.action=='abort' else ACTIONS[index-1]
            log.event('decision',decision_id=index,mode='intern_dual_'+mode,proposed_action=prediction.action,
                executed_action=action,probabilities=prediction.probabilities,confidence=prediction.confidence,model=prediction.model,
                is_mock=False,http_latency_ms=ms,model_had_control=had_control,image_count_sent=2,service_count=current['requests_completed'])
            print(f'[{mode}/{color}] {index}/{limit} proposed={prediction.action}; execute={action}',flush=True)
            executed.append(action)
            if action=='abort':reason='policy_abort';break
            outcome=scene.execute(action);log.event('phase_end',decision_id=index,**outcome)
            previous_action,previous_result=action,outcome['status']
            if previous_result=='timeout':timed_out=True;reason='stage_timeout';break
            if action=='release':
                released=True;outcome=scene.execute('retract');log.event('phase_end',decision_id=None,automatic=True,**outcome)
                timed_out=outcome['status']=='timeout'
                if not timed_out:scene.settle()
                reason='retract_timeout' if timed_out else 'completed';break
        final=check_health(client.health(allow_mock=False))
        if final['requests_completed']!=initial_count+completed:raise ProtocolError('Final service counter changed')
        log.event('final_model_health',health=final)
    except KeyboardInterrupt:reason='user_interrupt';error='KeyboardInterrupt';log.event('error',error=error,termination_reason=reason)
    except Exception as exc:
        reason='model_api_error' if isinstance(exc,ModelAPIError) else 'protocol_error' if isinstance(exc,ProtocolError) else 'runtime_error'
        error=f'{type(exc).__name__}: {exc}';log.event('error',error=error,termination_reason=reason)
    result=judge_episode(scene.private_truth()['cube_world_position_m'],config,released=released,timed_out=timed_out,termination_reason=reason)
    result.update(mode='intern_dual_'+mode,goal_color=color,prompt_variant=VARIANT,complete=reason=='completed' and error is None,
        api_attempts=attempts,api_completed=completed,proposed_actions=proposed,executed_actions=executed,error=error,
        model_had_control=had_control,model_called=attempts>0,strict_success_is_executor_only=mode=='shadow',
        shadow_reference_agreement=sum(a==b for a,b in zip(proposed,ACTIONS[:-1])) if mode=='shadow' else None,
        max_decisions=limit,physics_updates=scene.frames,recorded_frames=scene.recorded_frames,wall_seconds=time.perf_counter()-start,
        controller_target_source='existing configured skill targets; model only chooses skills',end_to_end_visual_localization=False)
    log.summary(result);return result

def require(condition,message):
    if not condition:raise ProtocolError(message)

def audit_shadow(directory,config,health):
    """Rebuild exact inputs and validate saved responses, runtime, physical score and phases."""
    directory=Path(directory).resolve();read=lambda n:json.loads((directory/n).read_text())
    manifest=read('manifest.json')
    require(not manifest.get('synthetic_fixture') and manifest.get('kind')=='intern_dual_live', 'Real live-shadow manifest required')
    summary=read('summary.json')
    require(manifest.get('mode')=='shadow' and manifest.get('variant')==VARIANT,'Wrong admission mode or variant')
    require(manifest.get('config')==config and manifest.get('source_sha256')==code_hashes(),'Shadow config/source differs')
    require(manifest.get('cameras')==camera_configs(config),'Shadow camera configuration differs')
    color=manifest.get('goal_color');require(color in GOAL_COLORS,'Unknown shadow color')
    require(health_identity(manifest.get('model_health',{}))==health_identity(health),'Shadow model source differs')
    require(summary.get('complete') is True and summary.get('strict_success') is True and summary.get('error') is None
        and summary.get('model_had_control') is False and summary.get('shadow_reference_agreement')==7
        and summary.get('api_attempts')==summary.get('api_completed')==7,'Shadow must be complete, physical success, seven valid calls and seven-of-seven')
    events=[json.loads(line) for line in (directory/'events.jsonl').read_text().splitlines()]
    runtime=[e for e in events if e['kind']=='runtime']
    require(len(runtime)==1 and runtime[0].get('simulation_device')=='cuda' and runtime[0].get('active_gpu')==0,'Real Isaac CUDA runtime evidence required')
    sync=runtime[0].get('physics_pose_sync',{})
    require(sync.get('update_to_usd') is True and sync.get('fabric_enabled') is False and sync.get('suppress_readback') is False,'Physics pose readback required')
    observations=[e for e in events if e['kind']=='paired_observation'];decisions=[e for e in events if e['kind']=='decision']
    frozen=[e for e in events if e['kind']=='api_frozen_state'];phases=[e for e in events if e['kind']=='phase_end']
    require(len(observations)==len(decisions)==len(frozen)==7,'Need seven observation/response/decision/freeze records')
    require([p['action'] for p in phases]==list(ACTIONS[:-1])+['retract'] and all(p['status']=='reached' for p in phases),'Fixed phases must complete')
    require(all(type(p.get('frames')) is int and p['frames']>0 for p in phases),'Positive real physics frames required')
    require(summary.get('physics_updates')==config['warmup_frames']+sum(p['frames'] for p in phases)+config['settle_frames'],'Final physics accounting differs')
    require(summary['proposed_actions']==summary['executed_actions']==list(ACTIONS[:-1]),'Saved summary choices differ')
    headers=[e['health'] for e in events if e['kind'] in {'model_health','final_model_health'}]
    require(len(headers)==2 and all(health_identity(h)==health_identity(health) for h in headers),'Stable health records required')
    require(headers[1]['requests_completed']-headers[0]['requests_completed']==7,'Need exactly seven service inferences')
    from PIL import Image
    for index,(obs,d,snapshot) in enumerate(zip(observations,decisions,frozen),1):
        require(obs['decision_id']==d['decision_id']==snapshot['decision_id']==index,'Observation order mismatch')
        require(obs['frozen_state']['physics_updates']==config['warmup_frames']+sum(p['frames'] for p in phases[:index-1]),'Live state must follow completed physical phases')
        require(obs['model_state']['previous_action']==(None if index==1 else ACTIONS[index-2]) and obs['model_state']['previous_result']==(None if index==1 else 'reached'),'Live previous-action context differs')
        pngs=[]
        require(len(obs['images'])==2,'Two images required')
        for view,asset in enumerate(obs['images'],1):
            path=directory/'images'/f'decision_{index:03d}_view{view}.png'
            require(asset['path']==str(path.relative_to(directory)) and sha256_file(path)==asset['sha256'],'Ordered PNG hash mismatch')
            with Image.open(path) as image:require(list(image.size)==config['camera']['resolution'],'Wrong rendered image size')
            pngs.append(path.read_bytes())
        request=read(f'requests/decision_{index:03d}.json');raw=read(f'responses/decision_{index:03d}.json')
        require(not raw.get('synthetic_fixture'),'Synthetic response forbidden')
        require(request==candidate_request(pngs,obs['model_state'],config,obs['goal_guidance'],color),'Saved input does not match pinned live factory')
        parsed=verify_response(pngs,raw,health)
        require(parsed.action==d['proposed_action']==d['executed_action']==ACTIONS[index-1] and d.get('model_had_control') is False,'Shadow choice mismatch')
        require(parsed.probabilities==d['probabilities'] and parsed.confidence==d['confidence'],'Raw official values differ')
        require(snapshot['physical_state_unchanged'] and snapshot['before']==snapshot['after']==obs['frozen_state'],'Physics moved during inference')
        require(d['service_count']==headers[0]['requests_completed']+index,'Service call sequence differs')
    expected=judge_episode(summary['final_cube_position_m'],config,released=True,timed_out=False,termination_reason='completed')
    require(expected['strict_success'] is True,'Final private physical score failed')
    files={str(p.relative_to(directory)):sha256_file(p) for p in sorted(directory.rglob('*')) if p.is_file()}
    return {'color':color,'directory':str(directory),'eligible':True,'files_sha256':files,'summary':summary}

def write_admission(directories,output,config,health):
    require(len(directories)==2,'Exactly two live shadows required')
    check_health(health);runs=[audit_shadow(p,config,health) for p in directories]
    require({r['color'] for r in runs}==set(GOAL_COLORS),'Both blue and yellow required')
    proof={'kind':'intern_dual_shadow_admission','eligible':True,'config':config,'source_sha256':code_hashes(),
        'model_identity':health_identity(health),'runs':runs,'policy':'Both real online shadows seven-of-seven plus complete fixed physical success; user authorizes one control run per color only'}
    output=Path(output);require(not output.exists(),'Do not overwrite admission');write_json(output,proof);return proof

def validate_admission(path,config,health):
    check_health(health);proof=json.loads(Path(path).read_text())
    require(proof.get('kind')=='intern_dual_shadow_admission' and proof.get('eligible') is True,'Wrong admission file')
    require(proof.get('config')==config and proof.get('source_sha256')==code_hashes() and proof.get('model_identity')==health_identity(health),'Admission config/source/model changed')
    require(len(proof.get('runs',[]))==2,'Two admission runs required')
    verified=[audit_shadow(r['directory'],config,health) for r in proof['runs']]
    require(verified==proof['runs'] and {r['color'] for r in verified}==set(GOAL_COLORS),'Admission evidence changed or color missing')
    return proof
