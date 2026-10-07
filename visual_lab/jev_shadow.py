"""Live measured-state Jev shadow: fixed executor only, no model-control path."""
from __future__ import annotations
import copy,json,os,subprocess,time
from pathlib import Path
from .client import MAX_RESPONSE_BYTES,ModelAPIError
from .core import ACTIONS,ProtocolError,judge_episode,model_state
from .factorial import STATE_KEYS,goal_guidance
from .goal_binding import binding_request
from .prompt_variants import relative_state,ZH_SOURCE,ZH_WARNING
from .text_english import EN_INSTRUCTIONS,english_request
from .jev import JEV_MODEL,JEV_VALIDATION_POLICY,verify_jev_response

ONLINE_INSTRUCTIONS=EN_INSTRUCTIONS.replace('offline action suggestions','online shadow action suggestions')

def online_request(state,guidance,color):
    if color not in {'blue','yellow'}:raise ProtocolError('Unknown online goal color')
    clean={k:copy.deepcopy(state[k]) for k in STATE_KEYS}
    clean.update(task=f'将红色方块放入地面{"蓝色" if color=="blue" else "黄色"}方形轮廓线内部，然后释放它。',
        camera_views=[],goal_guidance={'source':ZH_SOURCE,'reference_warning':ZH_WARNING})
    relative_state(clean,guidance,'zh')
    request={'state':clean,'images':[],'questions':{'next_stage':{'type':'choice','instructions':'replaced by frozen English template','criteria':{a:a for a in ACTIONS}}}}
    result=english_request(binding_request(request,color),color)
    result['questions']['next_stage']['instructions']=ONLINE_INSTRUCTIONS
    return result

def control_gate(result):
    conditions={'complete':result.get('complete') is True,'executor_physical_success':result.get('strict_success') is True,
        'seven_valid_calls':result.get('api_completed')==result.get('api_attempts')==7,
        'seven_of_seven_agreement':result.get('shadow_reference_agreement')==7,
        'no_error':result.get('error') is None,'shadow_only':result.get('model_had_control') is False}
    return {'eligible':all(conditions.values()),'requirements':conditions,'policy':'7/7 online shadow plus completed successful fixed-executor episode; candidate only, never automatic control authorization'}

class ShadowProcessClient:
    """One-shot isolated model Python workers; Isaac never reads the private key."""
    def __init__(self,python,key_file,evidence,*,color,timeout=60):
        self.python=Path(python);self.key_file=Path(key_file);self.evidence=Path(evidence);self.color=color;self.timeout=timeout
        self.attempts=self.requests_completed=0;self._health=None;self.last_response=None
    def _invoke(self,operation,request=None):
        root=Path(__file__).resolve().parents[1]
        command=[str(self.python),str(root/'tools/jev_shadow_worker.py'),'--key-file',str(self.key_file),'--goal-color',self.color]
        if request is not None:command+=['--capture-dir',str(self.evidence/f'decision_{self.attempts:03d}')]
        env=dict(os.environ);env['LD_LIBRARY_PATH']=''
        for key in ['PYTHONPATH','PYTHONHOME']:env.pop(key,None)
        body=json.dumps({'op':operation,'request':request},ensure_ascii=False,allow_nan=False).encode()
        try:completed=subprocess.run(command,input=body,capture_output=True,timeout=self.timeout+10,env=env,cwd=root)
        except (OSError,subprocess.TimeoutExpired):raise ModelAPIError('Isolated Jev worker failed or timed out; no retry') from None
        if len(completed.stdout)>MAX_RESPONSE_BYTES:raise ModelAPIError('Isolated Jev worker response exceeds size limit')
        try:message=json.loads(completed.stdout)
        except (ValueError,UnicodeDecodeError):raise ModelAPIError('Isolated Jev worker returned invalid JSON; details omitted') from None
        if completed.returncode!=0 or not isinstance(message,dict) or message.get('ok') is not True:
            raise ModelAPIError('Isolated Jev worker rejected request; inspect safe HTTP evidence, no retry')
        return message
    def health(self,*,allow_mock=False):
        if allow_mock:raise ProtocolError('Online Jev shadow never allows mock')
        if self._health is None:self._health=self._invoke('health')['health']
        return {**self._health,'requests_completed':self.requests_completed,'http_prediction_attempts':self.attempts,
                'counter_scope':'This seven-call shadow client; one isolated worker per cloud request, not vendor-global count'}
    def predict(self,request):
        self.last_response=None
        if self.attempts>=7:raise ProtocolError('Online shadow seven-call budget exhausted')
        self.attempts+=1;start=time.perf_counter();raw=self._invoke('predict',request)['response'];self.last_response=copy.deepcopy(raw)
        verify_jev_response(raw);self.requests_completed+=1
        return raw,(time.perf_counter()-start)*1000

def run_shadow(scene,config,color,log,client):
    start=time.perf_counter();previous_action=previous_result=None;proposed=[];executed=[];attempts=completed=0
    error=None;reason='decision_limit';timed_out=released=False
    try:
        health=client.health(allow_mock=False)
        if (health.get('backend')!='jev' or health.get('model')!=JEV_MODEL or health.get('is_mock') is not False
                or health.get('validation_policy')!=JEV_VALIDATION_POLICY or not health.get('supports_text_only')):
            raise ProtocolError('Require pinned real text-only Jev with basic validation')
        log.event('model_health',health=health)
        target=scene.placement_tool_target()
        for index,action in enumerate(ACTIONS[:-1],1):
            png=scene.capture();scene.timeline.pause()
            state=model_state(scene.proprioception(),previous_action,previous_result)
            guidance=goal_guidance(config['target_position_m'],target,scene._controller_tool_world_position(),scene.scenario._tool_frame)
            request=online_request(state,guidance,color);before=scene.frozen_state()
            log.observation(index,png,state,scene.private_truth());log.request(index,request);attempts+=1
            try:raw,latency=client.predict(request)
            except Exception:
                if client.last_response is not None:log.response(index,client.last_response)
                raise
            log.response(index,raw);prediction=verify_jev_response(raw);completed+=1;proposed.append(prediction.action)
            after=scene.frozen_state()
            log.event('api_frozen_state',decision_id=index,before=before,after=after,physical_state_unchanged=before==after)
            if before!=after:raise ProtocolError('Physics changed while awaiting Jev; no motion authorized')
            log.event('decision',decision_id=index,mode='jev_online_shadow',proposed_action=prediction.action,executed_action=action,
                probabilities=prediction.probabilities,confidence=prediction.confidence,model=prediction.model,is_mock=False,http_latency_ms=latency,
                model_had_control=False,image_count_sent=0,validation_policy=JEV_VALIDATION_POLICY)
            executed.append(action);outcome=scene.execute(action);log.event('phase_end',decision_id=index,**outcome)
            print(f'[jev_shadow/{color}] {index}/7 proposed={prediction.action}; fixed_execute={action}',flush=True)
            previous_action,previous_result=action,outcome['status']
            if previous_result=='timeout':timed_out=True;reason='stage_timeout';break
            if action=='release':
                released=True;outcome=scene.execute('retract');log.event('phase_end',decision_id=None,automatic=True,**outcome)
                timed_out=outcome['status']=='timeout'
                if not timed_out:scene.settle()
                reason='retract_timeout' if timed_out else 'completed';break
        log.event('final_model_health',health=client.health(allow_mock=False))
    except Exception as exc:
        reason='model_api_error' if isinstance(exc,ModelAPIError) else 'protocol_error' if isinstance(exc,ProtocolError) else 'runtime_error'
        error=f'{type(exc).__name__}: {exc}';log.event('error',termination_reason=reason,error=error)
    truth=scene.private_truth();result=judge_episode(truth['cube_world_position_m'],config,released=released,timed_out=timed_out,termination_reason=reason)
    result.update(mode='jev_online_shadow',goal_color=color,complete=reason=='completed' and error is None and completed==7,
        api_attempts=attempts,api_completed=completed,num_decisions=attempts,proposed_actions=proposed,executed_actions=executed,
        shadow_reference_agreement=sum(a==b for a,b in zip(proposed,ACTIONS[:-1])),error=error,model_called=attempts>0,
        real_model_evaluated=completed>0,model_had_control=False,strict_success_is_executor_only=True,
        physics_updates=scene.frames,recorded_frames=scene.recorded_frames,wall_seconds=time.perf_counter()-start,
        model_input_source='Live proprioception + configured target + measured-joint FK, no image or object truth',
        validation_policy=JEV_VALIDATION_POLICY,end_to_end_visual_localization=False)
    result['control_gate']=control_gate(result);log.summary(result)
    return result
