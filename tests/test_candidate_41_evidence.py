"""Saved real blue-shadow evidence tests; do not run Isaac or a model."""
import importlib.util,json,tarfile,tempfile,unittest
from pathlib import Path
from visual_lab.core import ProtocolError,load_config
from visual_lab.candidate_control import audit_shadow,pinned_health

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('candidate_41_auditor',ROOT/'test_reports/candidate_control_auditor_20261007.py')
auditor=importlib.util.module_from_spec(spec);spec.loader.exec_module(auditor)

class Candidate41EvidenceTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
        with tarfile.open(ROOT/'test_reports/candidate_41_44_evidence_20261007.tar.gz') as archive:archive.extractall(self.root/'evidence',filter='data')
        self.blue=self.root/'evidence/41_intern_dual_shadow_blue'
    def tearDown(self):self.tmp.cleanup()
    def test_blue_real_seven_of_seven_not_pair_admission_or_control(self):
        proof=audit_shadow(self.blue,load_config(ROOT/'configs/default.json'),pinned_health())
        self.assertTrue(proof['eligible']);self.assertEqual(proof['summary']['shadow_reference_agreement'],7)
        self.assertEqual(proof['summary']['physics_updates'],776);self.assertFalse(proof['summary']['model_had_control'])
        record=auditor.audit(self.root/'evidence',self.root/'audit.json',self.root/'report.html',plan_path=ROOT/'test_reports/candidate_41_44_plan_20261007.json')
        self.assertEqual(record['new_model_predictions'],7);self.assertFalse(record['complete']);self.assertFalse(record['shadow_pair_eligible']);self.assertEqual(record['control_runs'],0)
        self.assertEqual((self.root/'audit.json').read_bytes(),(ROOT/'test_reports/candidate_41_44_audit_20261007.json').read_bytes())
        self.assertEqual((self.root/'report.html').read_bytes(),(ROOT/'docs/reports/candidate_41_44_20261007.html').read_bytes())
    def test_tied_lower_choice_is_official_not_reselected(self):
        response=json.loads((self.blue/'responses/decision_006.json').read_text());answer=response['answers']['next_stage']
        self.assertEqual(answer['choice'],'lower');self.assertEqual(answer['probabilities']['lower'],answer['probabilities']['transport'])
        self.assertEqual(answer['probabilities']['lower'],max(answer['probabilities'].values()))
    def test_changed_saved_request_is_rejected(self):
        path=self.blue/'requests/decision_001.json';request=json.loads(path.read_text());request['state']['holding']=True;path.write_text(json.dumps(request))
        with self.assertRaises(ProtocolError):audit_shadow(self.blue,load_config(ROOT/'configs/default.json'),pinned_health())
    def test_summary_claim_cannot_make_six_of_seven_eligible(self):
        path=self.blue/'responses/decision_006.json';response=json.loads(path.read_text());response['answers']['next_stage']['choice']='transport';path.write_text(json.dumps(response))
        with self.assertRaises(ProtocolError):audit_shadow(self.blue,load_config(ROOT/'configs/default.json'),pinned_health())

if __name__=='__main__':unittest.main()
