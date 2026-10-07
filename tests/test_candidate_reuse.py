"""CPU orchestration contracts for reusing immutable real-shadow evidence."""
import copy,importlib,json,tarfile,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from visual_lab.core import ProtocolError,load_config
from visual_lab.candidate_control import audit_shadow,pinned_health

ROOT=Path(__file__).resolve().parents[1]

class ReuseTests(unittest.TestCase):
    def setUp(self):
        self.m=importlib.import_module('tools.run_candidate_experiment');self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
        with tarfile.open(ROOT/'test_reports/candidate_41_44_evidence_20261007.tar.gz') as t:t.extractall(self.root,filter='data')
        self.blue=self.root/'41_intern_dual_shadow_blue';self.config=load_config(ROOT/'configs/default.json');self.health=pinned_health()
        proof=audit_shadow(self.blue,self.config,self.health)
        self.plan={'reused_shadows':[{'run_dir':str(self.blue),'color':'blue','files_sha256':proof['files_sha256']}],
            'runs':[{'mode':'shadow','color':'yellow','run_dir':'runs/45_yellow'},{'mode':'control','color':'blue','run_dir':'runs/46_blue'},{'mode':'control','color':'yellow','run_dir':'runs/47_yellow'}]}
    def tearDown(self):self.tmp.cleanup()
    def test_real_blue_reaudited_and_not_in_new_launches(self):
        reused=self.m.verify_reused_shadows(self.plan,self.config,self.health)
        self.assertEqual(len(reused),1);self.assertTrue(reused[0]['eligible']);self.assertEqual(reused[0]['summary']['shadow_reference_agreement'],7)
        self.assertEqual(self.m.admission_directories(self.plan),[self.blue,ROOT/'runs/45_yellow'])
        self.assertTrue(all(j['run_dir']!=str(self.blue) for j in self.plan['runs']))
    def test_changed_extra_file_cannot_be_reused_by_summary_claim(self):
        (self.blue/'unexpected.txt').write_text('changed')
        with self.assertRaises(ProtocolError):self.m.verify_reused_shadows(self.plan,self.config,self.health)
    def test_duplicate_color_or_relaunch_of_successful_shadow_refused(self):
        for edit in [lambda p:p['runs'][0].update(color='blue'),lambda p:p['runs'][0].update(run_dir=str(self.blue)),lambda p:p['reused_shadows'].append(copy.deepcopy(p['reused_shadows'][0]))]:
            plan=copy.deepcopy(self.plan);edit(plan)
            with self.assertRaises(ProtocolError):self.m.verify_reused_shadows(plan,self.config,self.health)
    def test_no_model_inference_or_scene_is_used_to_verify_saved_blue(self):
        with patch.object(self.m,'DecisionClient') as client,patch.object(self.m.subprocess,'Popen') as process:
            self.m.verify_reused_shadows(self.plan,self.config,self.health)
        client.assert_not_called();process.assert_not_called()
    def test_existing_two_new_shadows_remain_supported(self):
        plan={'runs':[{'mode':'shadow','color':color,'run_dir':'runs/'+color} for color in ['blue','yellow']]}
        self.assertEqual(self.m.verify_reused_shadows(plan,self.config,self.health),[])
        self.assertEqual(self.m.admission_directories(plan),[ROOT/'runs/blue',ROOT/'runs/yellow'])
    def test_unsupported_color_or_changed_model_source_is_rejected(self):
        plan=copy.deepcopy(self.plan);plan['reused_shadows'][0]['color']='red'
        with self.assertRaises(ProtocolError):self.m.verify_reused_shadows(plan,self.config,self.health)
        with self.assertRaises(ProtocolError):self.m.verify_reused_shadows(self.plan,self.config,{**self.health,'temperature':1.0})

if __name__=='__main__':unittest.main()
