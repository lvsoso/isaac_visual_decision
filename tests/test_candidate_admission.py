"""Fabricated CPU gate fixtures to exercise audit, NOT genuine GPU admission evidence."""
import copy,importlib,json,tempfile,unittest
from pathlib import Path
from tests.test_factorial import FakeScene,ROOT
from tests.test_candidate_control import FixtureClient
from visual_lab.audit import AuditLog,write_json
from visual_lab.core import ProtocolError,load_config
from visual_lab.factorial import GOAL_COLORS,camera_configs
from visual_lab.png import encode_rgb_bytes

class AdmissionTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name);self.m=importlib.import_module('visual_lab.candidate_control')
        self.config=load_config(ROOT/'configs/default.json');self.paths=[];self.health=self.m.pinned_health()
        for color in GOAL_COLORS:
            client=FixtureClient();scene=FakeScene();scene.recorded_frames=0;scene.frames=120
            execute=scene.execute
            def phase(action,execute=execute):return {**execute(action),'frames':1}
            scene.execute=phase;scene.settle=lambda scene=scene:setattr(scene,'frames',scene.frames+120)
            scene.capture_views=lambda cameras:[encode_rgb_bytes(640,480,bytes([20,30,150])*640*480)]*2
            predict=client.predict
            def response(request,predict=predict):raw,ms=predict(request);raw.pop('synthetic_fixture');return raw,ms
            client.predict=response;path=self.root/color;self.paths.append(path)
            # Deliberately fabricated runtime metadata only to test file contracts.
            log=AuditLog(path,{'kind':'intern_dual_live','mode':'shadow','variant':self.m.VARIANT,'goal_color':color,
                'config':self.config,'cameras':camera_configs(self.config),'source_sha256':self.m.code_hashes(),'model_health':self.health})
            log.event('runtime',simulation_device='cuda',active_gpu=0,physics_pose_sync={'update_to_usd':True,'fabric_enabled':False,'suppress_readback':False})
            try:self.m.run_candidate(scene,[1,2],self.config,color,'shadow',log,client)
            finally:log.close()
    def tearDown(self):self.tmp.cleanup()
    def proof(self):return self.m.write_admission(self.paths,self.root/'proof.json',self.config,self.health)
    def change(self,path,edit):data=json.loads(path.read_text());edit(data);write_json(path,data)
    def test_pair_evidence_rebuilt_and_hashes_pinned(self):
        expected=self.proof();self.assertEqual({r['color'] for r in expected['runs']},{'blue','yellow'})
        self.assertEqual(expected,self.m.validate_admission(self.root/'proof.json',self.config,self.health))
        with self.assertRaises(ProtocolError):self.proof()
    def test_summary_claim_cannot_override_six_of_seven(self):
        self.change(self.paths[0]/'responses/decision_001.json',lambda p:p['answers']['next_stage'].update(choice='abort'))
        with self.assertRaises(ProtocolError):self.proof()
    def test_false_runtime_or_synthetic_marker_cannot_pass(self):
        self.change(self.paths[0]/'manifest.json',lambda p:p.update(synthetic_fixture=True))
        with self.assertRaises(ProtocolError):self.proof()
    def test_configuration_or_source_change_refused(self):
        self.proof();config=copy.deepcopy(self.config);config['target_position_m'][0]=.7
        with self.assertRaises(ProtocolError):self.m.validate_admission(self.root/'proof.json',config,self.health)
    def test_post_admission_event_tamper_refused(self):
        self.proof();path=self.paths[0]/'events.jsonl';path.write_text(path.read_text()+'{"kind":"injected"}\n')
        with self.assertRaises(ProtocolError):self.m.validate_admission(self.root/'proof.json',self.config,self.health)
    def test_duplicate_color_and_mock_service_refused(self):
        with self.assertRaises(ProtocolError):self.m.write_admission([self.paths[0]]*2,self.root/'proof.json',self.config,self.health)
        with self.assertRaises(ProtocolError):self.m.write_admission(self.paths,self.root/'proof.json',self.config,{**self.health,'is_mock':True})
    def test_png_byte_and_service_counter_tamper_refused(self):
        path=self.paths[0]/'images/decision_001_view1.png';path.write_bytes(path.read_bytes()+b'extra')
        with self.assertRaises(ProtocolError):self.proof()

if __name__=='__main__':unittest.main()
