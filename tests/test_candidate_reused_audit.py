"""Saved original-blue audit-counting tests; no inference, simulation or motion."""
import copy,importlib.util,json,tarfile,tempfile,unittest
from pathlib import Path
from visual_lab.core import load_config
from visual_lab.candidate_control import audit_shadow,pinned_health

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('candidate_reused_audit',ROOT/'test_reports/candidate_control_auditor_20261007.py')
auditor=importlib.util.module_from_spec(spec);spec.loader.exec_module(auditor)

class ReusedAuditTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
        with tarfile.open(ROOT/'test_reports/candidate_41_44_evidence_20261007.tar.gz') as t:t.extractall(self.root,filter='data')
        self.config=load_config(ROOT/'configs/default.json');self.plan=json.loads((ROOT/'test_reports/candidate_45_47_plan_20261007.json').read_text())
        proof=audit_shadow(self.root/'41_intern_dual_shadow_blue',self.config,pinned_health());proof['directory']='/original/remote/runs/41_intern_dual_shadow_blue'
        self.life={'reused_shadows':[proof]}
    def tearDown(self):self.tmp.cleanup()
    def test_reused_blue_verified_separately_from_new_prediction_counts(self):
        records=auditor.audit_reused(self.root,self.plan,self.life,self.config)
        self.assertEqual(len(records),1);self.assertTrue(records[0]['eligible']);self.assertEqual(records[0]['summary']['api_completed'],7)
        self.assertEqual(records[0]['color'],'blue')
    def test_changed_archived_blue_files_are_not_accepted(self):
        (self.root/'41_intern_dual_shadow_blue/extra').write_text('tampered')
        with self.assertRaises(AssertionError):auditor.audit_reused(self.root,self.plan,self.life,self.config)
    def test_lifecycle_cannot_relabel_or_replace_reused_source(self):
        self.life['reused_shadows'][0]['color']='yellow'
        with self.assertRaises(AssertionError):auditor.audit_reused(self.root,self.plan,self.life,self.config)
    def test_original_nonreuse_report_path_is_unchanged(self):
        self.assertEqual(auditor.audit_reused(self.root,{}, {},self.config),[])

if __name__=='__main__':unittest.main()
