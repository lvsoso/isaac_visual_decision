"""Offline saved zero-inference failure evidence, no new GPU simulation/inference."""
import importlib.util,json,tarfile,tempfile,unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('candidate_startup_audit',ROOT/'test_reports/candidate_control_auditor_20261007.py')
auditor=importlib.util.module_from_spec(spec);spec.loader.exec_module(auditor)

class StartupEvidenceTests(unittest.TestCase):
    def test_zero_prediction_no_scene_no_control_and_deterministic_report(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            with tarfile.open(ROOT/'test_reports/candidate_control_startup_evidence_20261007.tar.gz') as archive:archive.extractall(root/'evidence',filter='data')
            record=auditor.audit(root/'evidence',root/'audit.json',root/'report.html')
            self.assertFalse(record['complete']);self.assertEqual(record['new_model_predictions'],0)
            self.assertEqual(record['shadow_launch_attempts'],1);self.assertEqual(record['shadow_runs'],0)
            self.assertFalse(record['isaac_scene_verified']);self.assertFalse(record['model_control_started'])
            self.assertTrue(record['model_service_loaded_on_gpu']);self.assertEqual(record['control_runs'],0)
            self.assertEqual(record['lifecycle']['gpu_compute_after'],'')
            self.assertEqual((root/'audit.json').read_bytes(),(ROOT/'test_reports/candidate_control_startup_audit_20261007.json').read_bytes())
            self.assertEqual((root/'report.html').read_bytes(),(ROOT/'docs/reports/candidate_control_startup_20261007.html').read_bytes())

if __name__=='__main__':unittest.main()
