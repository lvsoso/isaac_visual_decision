"""Offline saved-evidence regression/tamper tests, not new GPU or API calls."""
import importlib.util,json,tarfile,tempfile,unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('shadow_evidence_auditor',ROOT/'test_reports/jev_online_shadow_auditor_20261007.py')
auditor=importlib.util.module_from_spec(spec);spec.loader.exec_module(auditor)

class ShadowEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name);self.evidence=self.root/'evidence'
        with tarfile.open(ROOT/'test_reports/jev_online_shadow_evidence_20261007.tar.gz') as archive:
            archive.extractall(self.evidence,filter='data')
    def tearDown(self):self.tmp.cleanup()
    def audit(self):
        return auditor.audit(self.evidence,ROOT/'test_reports/jev_shadow_plan_20261007.json',self.root/'report.json',self.root/'report.html')
    def change_json(self,path,mutate):
        data=json.loads(path.read_text());mutate(data);path.write_text(json.dumps(data))
    def test_fourteen_real_saved_calls_and_deterministic_offline_rebuild(self):
        p=self.audit();self.assertEqual(p['new_jev_verified_calls'],14);self.assertEqual(p['distinct_http_request_ids'],14)
        self.assertTrue(p['complete']);self.assertTrue(p['isaac_gpu_executed']);self.assertFalse(p['model_had_control']);self.assertFalse(p['whole_pair_control_eligible'])
        previous=json.loads((ROOT/'test_reports/jev_group_frozen_20261007.json').read_text())['requests']
        for run in p['runs']:
            self.assertEqual(run['agreement'],5);self.assertFalse(run['control_eligible']);self.assertTrue(run['summary']['strict_success'])
            self.assertEqual(run['summary']['physics_updates'],776)
            for row in run['decisions']:
                old=previous[f'{run["color"]}_images_0_decision_{row["index"]:03d}']
                self.assertEqual(row['request']['state'],old['state'])
                self.assertEqual(row['request']['questions']['next_stage']['instructions'],old['questions']['next_stage']['instructions'].replace('offline action suggestions','online shadow action suggestions'))
                self.assertEqual(row['request']['questions']['next_stage']['criteria'],old['questions']['next_stage']['criteria'])
        self.assertEqual((self.root/'report.json').read_bytes(),(ROOT/'test_reports/jev_online_shadow_20261007.json').read_bytes())
        self.assertEqual((self.root/'report.html').read_bytes(),(ROOT/'docs/reports/jev_online_shadow_20261007.html').read_bytes())
    def test_cube_truth_leak_in_model_request_is_rejected(self):
        self.change_json(self.evidence/'35_jev_shadow_blue/requests/decision_001.json',lambda p:p['state'].update(cube_world_position_m=[.5,0,.025]))
        with self.assertRaises(AssertionError):self.audit()
    def test_changed_official_answer_or_probability_is_rejected(self):
        self.change_json(self.evidence/'35_jev_shadow_blue/responses/decision_003.json',lambda p:p['answers']['next_stage'].update(choice='grasp'))
        with self.assertRaises(AssertionError):self.audit()
    def test_missing_gpu_runtime_evidence_is_rejected(self):
        path=self.evidence/'35_jev_shadow_blue/events.jsonl';rows=[json.loads(line) for line in path.read_text().splitlines()]
        path.write_text(''.join(json.dumps(r)+'\n' for r in rows if r['kind']!='runtime'))
        with self.assertRaises(AssertionError):self.audit()
    def test_six_of_seven_gate_or_false_eligibility_is_rejected(self):
        self.change_json(self.evidence/'35_jev_shadow_blue/summary.json',lambda p:p['control_gate'].update(eligible=True))
        with self.assertRaises(AssertionError):self.audit()
    def test_duplicate_http_request_id_is_rejected(self):
        first=json.loads((self.evidence/'35_jev_shadow_blue/http_evidence/decision_001/response_meta.json').read_text())
        self.change_json(self.evidence/'35_jev_shadow_blue/http_evidence/decision_002/response_meta.json',lambda p:p.update(request_id=first['request_id']))
        with self.assertRaises(AssertionError):self.audit()
    def test_snapshot_changed_while_waiting_is_rejected(self):
        path=self.evidence/'35_jev_shadow_blue/events.jsonl';rows=[json.loads(line) for line in path.read_text().splitlines()]
        next(r for r in rows if r['kind']=='api_frozen_state')['after']['physics_updates']+=1
        path.write_text(''.join(json.dumps(r)+'\n' for r in rows))
        with self.assertRaises(AssertionError):self.audit()

if __name__=='__main__':unittest.main()
