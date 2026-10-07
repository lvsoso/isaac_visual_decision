"""CPU fixtures for gated dual-view control; never real model/GPU evidence."""
import copy,hashlib,importlib,io,json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from PIL import Image
from tests.test_factorial import FakeScene,ROOT
from visual_lab.audit import AuditLog
from visual_lab.client import ModelAPIError
from visual_lab.core import ACTIONS,ProtocolError,load_config,model_state
from visual_lab.factorial import GOAL_COLORS,goal_guidance,view_metadata
from visual_lab.prompt_variants import prompt_request

def module():return importlib.import_module('visual_lab.candidate_control')

class FixtureClient:
    def __init__(self,actions=None):self.actions=list(actions or ACTIONS[:-1]);self.calls=[];self.fail=False
    def health(self,**kwargs):
        return {**module().pinned_health(),'requests_completed':len(self.calls),'busy':False}
    def predict(self,request):
        import base64
        index=len(self.calls);self.calls.append(copy.deepcopy(request))
        if self.fail:raise ModelAPIError('CPU disconnect')
        choice=self.actions[min(index,len(self.actions)-1)];pngs=[base64.b64decode(i['data']) for i in request['images']]
        return {'model':'Intern-Decision-4B','answers':{'next_stage':{'type':'choice','choice':choice,'confidence':.8,'probabilities':{a:.93 if a==choice else .01 for a in ACTIONS}}},
            'calibration':{'temperature':self.health()['temperature']},
            '_bridge':{'is_mock':False,'image_count':2,'image_sha256s':[hashlib.sha256(p).hexdigest() for p in pngs],'inference_py_sha256':self.health()['inference_py_sha256']},
            '_vision_audit':{'input_tokens':2500,'image_grid_thw':[[1,2,2]]*2,'normalized_rgb_sha256s':[hashlib.sha256(Image.open(io.BytesIO(p)).convert('RGB').tobytes()).hexdigest() for p in pngs]},'synthetic_fixture':True},1.

class CandidateTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name);self.config=load_config(ROOT/'configs/default.json')
        self.scene=FakeScene();self.scene.set_goal_color(GOAL_COLORS['blue']);self.scene.recorded_frames=0
        self.client=FixtureClient();self.log=AuditLog(self.root/'run',{'synthetic_fixture':True})
    def tearDown(self):self.log.close();self.tmp.cleanup()
    def run_episode(self,mode='shadow',admission=None):
        return module().run_candidate(self.scene,[object(),object()],self.config,'blue',mode,self.log,self.client,admission=admission)
    def test_prompt_is_exact_original_zh_named_relative_without_labels(self):
        state=model_state(self.scene.proprioception(),None,None);guidance=goal_guidance(self.config['target_position_m'],self.scene.placement_tool_target(),self.scene._controller_tool_world_position(),'tool0');pngs=self.scene.capture_views([1,2])
        expected=prompt_request(pngs,state,view_metadata(self.config),guidance,{'variant':'zh_named_relative','color':'blue'})
        self.assertEqual(module().candidate_request(pngs,state,self.config,guidance,'blue'),expected)
        state.update(holding=True,expected_action='release',decision_id=7);self.assertEqual(module().candidate_request(pngs,state,self.config,guidance,'blue'),expected)
    def test_shadow_fixed_actions_and_seven_valid_calls(self):
        r=self.run_episode();self.assertEqual(self.scene.actions,list(ACTIONS[:-1])+['retract']);self.assertTrue(r['complete']);self.assertEqual(r['shadow_reference_agreement'],7);self.assertFalse(r['model_had_control'])
    def test_shadow_wrong_suggestion_does_not_control(self):
        self.client.actions=['lift']*7;r=self.run_episode();self.assertEqual(self.scene.actions,list(ACTIONS[:-1])+['retract']);self.assertEqual(r['shadow_reference_agreement'],1)
    def test_abort_stops_even_shadow_no_retract_or_extra_physics(self):
        self.client.actions=['abort'];r=self.run_episode();self.assertEqual(self.scene.actions,[]);self.assertEqual(r['termination_reason'],'policy_abort');self.assertFalse(r['complete'])
    def test_control_without_admission_never_calls_or_moves(self):
        r=self.run_episode('control');self.assertEqual(self.scene.actions,[]);self.assertEqual(self.client.calls,[]);self.assertEqual(r['termination_reason'],'protocol_error')
    def test_control_executes_model_choice_not_reference_sequence(self):
        self.client.actions=['lift','release']
        with patch.object(module(),'validate_admission',return_value={'eligible':True}):r=self.run_episode('control',self.root/'proof.json')
        self.assertEqual(self.scene.actions,['lift','release','retract']);self.assertEqual(r['executed_actions'],['lift','release']);self.assertTrue(r['model_had_control'])
    def test_control_repeat_budget_is_terminal_no_baseline_fallback(self):
        self.client.actions=['lift']
        with patch.object(module(),'validate_admission',return_value={'eligible':True}):r=self.run_episode('control',self.root/'proof.json')
        self.assertEqual(len(self.client.calls),module().CONTROL_MAX_DECISIONS);self.assertEqual(self.scene.actions,['lift']*module().CONTROL_MAX_DECISIONS);self.assertFalse(r['complete']);self.assertEqual(r['termination_reason'],'decision_limit')
    def test_api_error_timeout_and_bad_vision_stop_before_next_motion(self):
        self.client.fail=True;r=self.run_episode();self.assertEqual(self.scene.actions,[]);self.assertEqual(r['api_attempts'],1);self.assertEqual(r['termination_reason'],'model_api_error')
    def test_physics_changed_during_wait_stops_before_motion(self):
        old=self.client.predict
        def dirty(req):self.scene.frames+=1;return old(req)
        self.client.predict=dirty;r=self.run_episode();self.assertEqual(self.scene.actions,[]);self.assertEqual(r['termination_reason'],'protocol_error')
    def test_phase_timeout_stops_without_retract(self):
        self.scene.fail_action='grasp';r=self.run_episode();self.assertEqual(self.scene.actions,['pre_grasp','approach','grasp']);self.assertEqual(r['termination_reason'],'stage_timeout')
    def test_wrong_provenance_health_refused(self):
        old=self.client.health;self.client.health=lambda **kw:{**old(),'temperature':1.0}
        r=self.run_episode();self.assertEqual(self.scene.actions,[]);self.assertEqual(self.client.calls,[]);self.assertEqual(r['termination_reason'],'protocol_error')
    def test_tampered_vision_response_archived_but_not_executed(self):
        old=self.client.predict
        def bad(req):raw,ms=old(req);raw['_vision_audit']['normalized_rgb_sha256s'][0]='bad';return raw,ms
        self.client.predict=bad;r=self.run_episode();self.assertEqual(self.scene.actions,[]);self.assertTrue((self.log.root/'responses/decision_001.json').exists());self.assertEqual(r['termination_reason'],'protocol_error')
    def test_service_counter_change_refused_before_next_motion(self):
        old=self.client.health;self.client.health=lambda **kw:{**old(),'requests_completed':len(self.client.calls)*2}
        r=self.run_episode();self.assertEqual(self.scene.actions,[]);self.assertEqual(r['termination_reason'],'protocol_error')
    def test_gate_cannot_accept_synthetic_or_summary_only_success(self):
        with self.assertRaises(ProtocolError):module().audit_shadow(self.log.root,self.config,module().pinned_health())
    def test_pair_gate_rejects_single_color_and_bad_config(self):
        with self.assertRaises(ProtocolError):module().write_admission([self.log.root],self.root/'proof.json',self.config,module().pinned_health())
        with self.assertRaises((ProtocolError,FileNotFoundError)):module().validate_admission(self.root/'missing',self.config,module().pinned_health())

if __name__=='__main__':unittest.main()
