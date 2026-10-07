"""Real completed simulation evidence regression; never launches model/Isaac."""
import importlib.util,json,tarfile,tempfile,unittest
from pathlib import Path
from visual_lab.core import ProtocolError

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('candidate_45_auditor',ROOT/'test_reports/candidate_control_auditor_20261007.py')
auditor=importlib.util.module_from_spec(spec);spec.loader.exec_module(auditor)

class Candidate45EvidenceTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
        with tarfile.open(ROOT/'test_reports/candidate_45_47_evidence_20261007.tar.gz') as t:t.extractall(self.root/'evidence',filter='data')
    def tearDown(self):self.tmp.cleanup()
    def audit(self):
        return auditor.audit(self.root/'evidence',self.root/'audit.json',self.root/'report.html',plan_path=ROOT/'test_reports/candidate_45_47_plan_20261007.json')
    def test_actual_pair_admission_and_two_direct_choice_physical_successes(self):
        result=self.audit();self.assertTrue(result['complete']);self.assertTrue(result['shadow_pair_eligible'])
        self.assertEqual(result['new_model_predictions'],21);self.assertEqual(result['reused_model_predictions'],7)
        self.assertEqual(result['control_runs'],2);self.assertEqual(result['control_physical_successes'],2)
        self.assertEqual(result['lifecycle']['gpu_compute_after'],'');self.assertTrue(result['lifecycle']['own_processes_closed'])
        for run in result['runs']:
            self.assertEqual(len(run['decisions']),7);self.assertEqual(run['summary']['physics_updates'],776)
            for row in run['decisions']:self.assertEqual(row['proposed_action'],row['executed_action'])
        old=json.loads((ROOT/'test_reports/candidate_45_47_audit_20261007.json').read_text())
        old_dir=old['reused_shadow_evidence'][0]['directory'];new_dir=result['reused_shadow_evidence'][0]['directory']
        old['reused_shadow_evidence'][0]['directory']=new_dir;self.assertEqual(result,old)
        self.assertEqual((self.root/'report.html').read_text(),(ROOT/'docs/reports/candidate_45_47_20261007.html').read_text().replace(old_dir,new_dir))
        before=(self.root/'audit.json').read_bytes(),(self.root/'report.html').read_bytes();self.audit()
        self.assertEqual(before,((self.root/'audit.json').read_bytes(),(self.root/'report.html').read_bytes()))
    def test_control_response_cannot_be_reselected(self):
        path=self.root/'evidence/46_intern_dual_control_blue/responses/decision_006.json'
        response=json.loads(path.read_text());response['answers']['next_stage']['choice']='transport';path.write_text(json.dumps(response))
        with self.assertRaises((AssertionError,ProtocolError)):self.audit()
    def test_changed_admission_is_not_accepted(self):
        path=self.root/'evidence/experiment/admission.json';proof=json.loads(path.read_text());proof['eligible']=False;path.write_text(json.dumps(proof))
        with self.assertRaises(AssertionError):self.audit()
    def test_changed_control_view_is_rejected(self):
        path=self.root/'evidence/47_intern_dual_control_yellow/images/decision_001_view1.png';path.write_bytes(path.read_bytes()+b'changed')
        with self.assertRaises(AssertionError):self.audit()

if __name__=='__main__':unittest.main()
