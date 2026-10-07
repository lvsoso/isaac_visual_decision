"""Offline auditor plan selection contracts; no GPU, HTTP or robot execution."""
import importlib.util,json,tempfile,unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('candidate_plan_auditor',ROOT/'test_reports/candidate_control_auditor_20261007.py')
auditor=importlib.util.module_from_spec(spec);spec.loader.exec_module(auditor)

class FrozenPlanTests(unittest.TestCase):
    def test_explicit_new_plan_is_verified_without_replacing_old_plan(self):
        for name in ['candidate_control_plan_20261007.json','candidate_41_44_plan_20261007.json']:
            path=ROOT/'test_reports'/name
            self.assertEqual(auditor.verify_frozen_plan(path,path),json.loads(path.read_text()))
    def test_new_plan_cannot_be_reported_as_old_aborted_batch(self):
        with self.assertRaises(AssertionError):
            auditor.verify_frozen_plan(ROOT/'test_reports/candidate_41_44_plan_20261007.json',ROOT/'test_reports/candidate_control_plan_20261007.json')
    def test_changed_template_version_or_budget_is_rejected(self):
        expected=ROOT/'test_reports/candidate_41_44_plan_20261007.json'
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'plan.json';value=json.loads(expected.read_text());value['max_prediction_calls']=99;path.write_text(json.dumps(value))
            with self.assertRaises(AssertionError):auditor.verify_frozen_plan(path,expected)

if __name__=='__main__':unittest.main()
