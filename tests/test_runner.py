import json
import tempfile
import unittest
from pathlib import Path
from visual_lab.core import ACTIONS, load_config
from visual_lab.runner import run_episode
from visual_lab.audit import AuditLog
from visual_lab.client import ModelAPIError
from visual_lab.server import MockEngine
from tools.offline_smoke import SyntheticScene
from tools.make_report import build_report

ROOT=Path(__file__).resolve().parents[1]

class FakeClient:
    def __init__(self,choice=None,error=False): self.choice=choice; self.error=error
    def health(self,**kwargs): return {"is_mock":False,"test_fixture":True}
    def predict(self,request):
        if self.error: raise ModelAPIError("synthetic disconnect")
        r=MockEngine().predict(request)
        r["model"]="TEST-FIXTURE-ONLY"
        if self.choice:
            a=r["answers"]["next_stage"]
            a.update(choice=self.choice,probabilities={k:float(k==self.choice) for k in ACTIONS})
        return r,1.0

class RunnerTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.root=Path(self.temp.name)/"run"
        self.config=load_config(ROOT/"configs/default.json")
        self.log=AuditLog(self.root,{"config":self.config,"record_every":0,"synthetic_fixture":True})
        self.scene=SyntheticScene()
    def tearDown(self): self.log.close(); self.temp.cleanup()
    def test_baseline_no_model(self):
        r=run_episode(self.scene,self.config,"baseline",self.log)
        self.assertEqual(r["executed_actions"],list(ACTIONS[:-1]))
        self.assertTrue(r["strict_success"]); self.assertEqual(r["api_attempts"],0)
    def test_capture_does_not_move(self):
        r=run_episode(self.scene,self.config,"capture",self.log)
        self.assertEqual(self.scene.frames,0); self.assertFalse(r["model_called"])
    def test_shadow_does_not_execute_suggested_abort(self):
        r=run_episode(self.scene,self.config,"shadow",self.log,FakeClient("abort"))
        self.assertTrue(r["strict_success"])
        self.assertNotIn("abort",r["executed_actions"])
        self.assertEqual(r["proposed_actions"],["abort"]*7)
        self.assertFalse(r["model_had_control"])
    def test_visual_abort_does_not_retract(self):
        r=run_episode(self.scene,self.config,"visual",self.log,FakeClient("abort"))
        self.assertEqual(self.scene.frames,0)
        self.assertEqual(r["termination_reason"],"policy_abort")
    def test_decision_limit(self):
        self.config["max_decisions"]=3
        r=run_episode(self.scene,self.config,"visual",self.log,FakeClient("pre_grasp"))
        self.assertEqual(r["num_decisions"],3)
        self.assertEqual(r["termination_reason"],"decision_limit")
    def test_api_failure_stops_before_motion(self):
        r=run_episode(self.scene,self.config,"visual",self.log,FakeClient(error=True))
        self.assertEqual(r["termination_reason"],"model_api_error")
        self.assertEqual(self.scene.frames,0)
        self.assertEqual(r["api_completed"],0)
    def test_timeout_is_terminal(self):
        self.scene.execute=lambda action:{"action":action,"status":"timeout","frames":1}
        r=run_episode(self.scene,self.config,"baseline",self.log)
        self.assertTrue(r["timeout_occurred"])
        self.assertEqual(r["num_decisions"],1)
        self.assertEqual(r["termination_reason"],"stage_timeout")
    def test_automatic_retract_not_a_decision(self):
        r=run_episode(self.scene,self.config,"baseline",self.log)
        events=[json.loads(l) for l in (self.root/"events.jsonl").read_text().splitlines()]
        self.assertEqual(len([e for e in events if e["kind"]=="decision"]),7)
        retract=[e for e in events if e["kind"]=="phase_end" and e["action"]=="retract"]
        self.assertTrue(retract[0]["automatic"])
    def test_html_report_and_csv_generated(self):
        run_episode(self.scene,self.config,"baseline",self.log)
        report=build_report(self.root)
        self.assertTrue(report.exists())
        self.assertEqual(len((self.root/"decisions.csv").read_text().splitlines()),8)
    def test_run_directory_never_overwritten(self):
        with self.assertRaises(FileExistsError): AuditLog(self.root,{})

if __name__ == "__main__": unittest.main()
