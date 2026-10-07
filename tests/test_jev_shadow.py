"""CPU-only online shadow isolation contracts, never GPU/model quality evidence."""
import copy,importlib,io,json,subprocess,tempfile,unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock,patch
from tests.test_factorial import FactorialTests,FakeScene,ROOT
from visual_lab.audit import AuditLog
from visual_lab.client import ModelAPIError
from visual_lab.core import ACTIONS,ProtocolError,load_config,model_state
from visual_lab.factorial import goal_guidance
from visual_lab.jev import JEV_MODEL
from visual_lab.text_english import EN_INSTRUCTIONS,english_request
from visual_lab.goal_binding import binding_request
from visual_lab.image_ablation import image_request

def module():return importlib.import_module('visual_lab.jev_shadow')
def raw(choice='abort'):
    return {'model':JEV_MODEL,'answers':{'next_stage':{'type':'choice','choice':choice,'confidence':.55,'probabilities':{a:.125 for a in ACTIONS}}},'usage':{'input_tokens':100,'output_tokens':20},'synthetic_fixture':True}
class FakeClient:
    def __init__(self,choice='abort',fail=False):self.choice=choice;self.fail=fail;self.requests=[];self.last_response=None
    def health(self,**kwargs):return {'backend':'jev','model':JEV_MODEL,'is_mock':False,'supports_text_only':True,'validation_policy':'jev_sdk_basic_v1','requests_completed':len(self.requests),'http_prediction_attempts':len(self.requests)}
    def predict(self,request):
        self.requests.append(copy.deepcopy(request))
        if self.fail:raise ModelAPIError('CPU fixture disconnect')
        return raw(self.choice),1.0

class ShadowTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name);self.config=load_config(ROOT/'configs/default.json');self.scene=FakeScene()
        self.scene.capture=lambda:b'CPU-fixture-PNG-not-a-real-render';self.scene.recorded_frames=0
        self.log=AuditLog(self.root/'run',{'synthetic_fixture':True,'config':self.config});self.client=FakeClient()
    def tearDown(self):self.log.close();self.tmp.cleanup()
    def test_factory_matches_previous_english_except_truthful_online_context(self):
        fixture=FactorialTests();fixture.setUp()
        for color in ['blue','yellow']:
            old=english_request(binding_request(image_request(fixture.pngs[color],fixture.state,fixture.views,fixture.guidance,{'color':color,'views':0},prompt_policy='modality_aware_v1'),color),color)
            expected=copy.deepcopy(old);expected['questions']['next_stage']['instructions']=EN_INSTRUCTIONS.replace('offline action suggestions','online shadow action suggestions')
            actual=module().online_request(fixture.state,fixture.guidance,color);self.assertEqual(actual,expected)
            dirty=copy.deepcopy(fixture.state);dirty.update(cube_world_position_m=[99]*3,holding=True,expected_action='release',decision_id=7)
            self.assertEqual(module().online_request(dirty,fixture.guidance,color),actual);self.assertEqual(actual['images'],[]);self.assertEqual(actual['state']['camera_views'],[])
    def test_suggested_abort_never_controls_arm_and_fixed_success_is_not_model_success(self):
        result=module().run_shadow(self.scene,self.config,'blue',self.log,self.client)
        self.assertEqual(self.scene.actions,list(ACTIONS[:-1])+['retract']);self.assertEqual(result['api_completed'],7)
        self.assertEqual(result['proposed_actions'],['abort']*7);self.assertFalse(result['model_had_control']);self.assertTrue(result['strict_success_is_executor_only'])
        self.assertFalse(result['control_gate']['eligible']);self.assertEqual(result['shadow_reference_agreement'],0)
        for request in self.client.requests:
            self.assertNotIn('cube_world_position_m',request['state']);self.assertNotIn('expected_action',request['state']);self.assertEqual(request['images'],[])
    def test_api_failure_stops_before_any_motion_without_baseline_fallback(self):
        result=module().run_shadow(self.scene,self.config,'blue',self.log,FakeClient(fail=True))
        self.assertEqual(self.scene.actions,[]);self.assertEqual(result['api_attempts'],1);self.assertEqual(result['api_completed'],0)
        self.assertEqual(result['termination_reason'],'model_api_error');self.assertFalse(result['control_gate']['eligible'])
    def test_state_change_during_api_stops_before_action(self):
        original=self.client.predict
        def dirty(req):self.scene.frames+=1;return original(req)
        self.client.predict=dirty;result=module().run_shadow(self.scene,self.config,'blue',self.log,self.client)
        self.assertEqual(self.scene.actions,[]);self.assertEqual(result['termination_reason'],'protocol_error');self.assertFalse(result['control_gate']['eligible'])
    def test_timeout_is_terminal_and_no_retract(self):
        self.scene.fail_action='grasp';result=module().run_shadow(self.scene,self.config,'yellow',self.log,self.client)
        self.assertEqual(self.scene.actions,['pre_grasp','approach','grasp']);self.assertEqual(result['api_completed'],3);self.assertFalse(result['complete']);self.assertFalse(result['control_gate']['eligible'])
    def test_wrong_backend_or_mock_health_prevents_movement(self):
        for changes in [{'is_mock':True},{'model':'jev-latest'},{'validation_policy':'strict'},{'backend':'intern'}]:
            client=FakeClient();health=client.health();health.update(changes);client.health=lambda **kw:health
            with tempfile.TemporaryDirectory(dir=self.root) as folder:
                log=AuditLog(Path(folder)/'log',{'synthetic_fixture':True});result=module().run_shadow(self.scene,self.config,'blue',log,client);log.close()
            self.assertEqual(self.scene.actions,[]);self.assertFalse(result['complete'])
    def test_only_complete_physical_shadow_seven_of_seven_is_eligible(self):
        result={'complete':True,'strict_success':True,'error':None,'api_attempts':7,'api_completed':7,'shadow_reference_agreement':7,'model_had_control':False}
        self.assertTrue(module().control_gate(result)['eligible'])
        for key,value in [('shadow_reference_agreement',6),('strict_success',False),('complete',False),('api_completed',6),('api_attempts',8),('error','failure'),('model_had_control',True)]:
            dirty=dict(result);dirty[key]=value;self.assertFalse(module().control_gate(dirty)['eligible'])
    def test_isolated_subprocess_environment_and_budget_without_real_worker(self):
        client=module().ShadowProcessClient(Path('/fixture/python'),Path('/fixture/key'),self.root/'http',color='blue',timeout=60)
        payload=SimpleNamespace(returncode=0,stdout=json.dumps({'ok':True,'health':FakeClient().health()}).encode(),stderr=b'')
        with patch.object(module().subprocess,'run',return_value=payload) as call,patch.dict(module().os.environ,{'LD_LIBRARY_PATH':'Isaac-libraries','PYTHONPATH':'Isaac-python','PYTHONHOME':'Isaac-home'}):
            self.assertEqual(client.health()['model'],JEV_MODEL);client.health();self.assertEqual(call.call_count,1)
            env=call.call_args.kwargs['env'];self.assertEqual(env['LD_LIBRARY_PATH'],'');self.assertNotIn('PYTHONPATH',env);self.assertNotIn('PYTHONHOME',env)
        request=module().online_request(model_state(self.scene.proprioception(),None,None),goal_guidance(self.config['target_position_m'],self.scene.placement_tool_target(),self.scene._controller_tool_world_position(),'tool0'),'blue')
        with patch.object(module().subprocess,'run',return_value=SimpleNamespace(returncode=0,stdout=json.dumps({'ok':True,'response':raw()}).encode(),stderr=b'')) as call:
            for i in range(7):client.predict(request)
            with self.assertRaises(ProtocolError):client.predict(request)
            self.assertEqual(call.call_count,7);self.assertEqual(client.health()['requests_completed'],7)
    def test_worker_timeout_or_invalid_output_is_safe_and_not_retried(self):
        for value in [subprocess.TimeoutExpired('fixture',1),SimpleNamespace(returncode=2,stdout=b'{"ok":false,"error_class":"ModelAPIError"}',stderr=b'private'),SimpleNamespace(returncode=0,stdout=b'bad JSON',stderr=b'private')]:
            client=module().ShadowProcessClient(Path('/fixture/python'),Path('/fixture/key'),self.root/'http',color='blue',timeout=60)
            kwargs={'side_effect':value} if isinstance(value,Exception) else {'return_value':value}
            with patch.object(module().subprocess,'run',**kwargs) as call,self.assertRaises(ModelAPIError) as raised:client.health()
            self.assertNotIn('private',str(raised.exception));call.assert_called_once()

if __name__=='__main__':unittest.main()
