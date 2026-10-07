"""Synthetic offline presentation contract, no model/Isaac evidence."""
import importlib.util,tempfile,unittest
from pathlib import Path
from visual_lab.core import ACTIONS

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('candidate_report_labels',ROOT/'test_reports/candidate_control_auditor_20261007.py')
auditor=importlib.util.module_from_spec(spec);spec.loader.exec_module(auditor)

class ReportLabelTests(unittest.TestCase):
    def test_run_label_does_not_become_last_details_label_on_second_stage(self):
        rows=[{'index':i,'proposed_action':'lift','executed_action':'lift','images':[],'probabilities':{a:.125 for a in ACTIONS},'request':{},'response':{},'phase_outcome':{},'private_frozen_state':{}} for i in [1,2]]
        payload={'new_model_predictions':2,'shadow_runs':1,'control_runs':0,'control_physical_successes':0,'runs':[{'mode':'shadow','color':'blue','summary':{},'decisions':rows}],'lifecycle':{},'plan':{}}
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'report.html';auditor.render(payload,path);text=path.read_text()
            self.assertIn('<h3>shadow / blue / 1：',text);self.assertIn('<h3>shadow / blue / 2：',text)

if __name__=='__main__':unittest.main()
