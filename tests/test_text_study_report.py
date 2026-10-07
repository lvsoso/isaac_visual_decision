"""Three-group offline report invariants, no live vendor or GPU calls."""
import copy,importlib,json,tempfile,unittest
from unittest.mock import patch
from pathlib import Path

class StudyReportTests(unittest.TestCase):
 def payload(self,backend='intern',language='en'):
  req={'state':{'task':'CPU fixture','camera_views':[]},'images':[],'questions':{'next_stage':{'type':'choice','criteria':{a:a for a in ['pre_grasp','approach','grasp','lift','transport','lower','release','abort']}}}}
  requests={f'{c}_images_0_decision_{j:03d}':copy.deepcopy(req) for c in ['blue','yellow'] for j in range(1,8)}
  return {'summary':{'language':language,'backend':backend},'requests':requests}
 def test_english_pair_same_state_questions_and_no_wire_images(self):
  m=importlib.import_module('tools.make_text_study_report');a=self.payload();b=self.payload('jev')
  m.check_english_pair(a,b)
  b['requests']['blue_images_0_decision_001']['state']['task']='different'
  with self.assertRaisesRegex(Exception,'English|english|input'):m.check_english_pair(a,b)
 def test_pair_rejects_missing_or_nonempty_image_input(self):
  m=importlib.import_module('tools.make_text_study_report');a=self.payload();b=self.payload('jev')
  b['requests'].pop('yellow_images_0_decision_007')
  with self.assertRaises(Exception):m.check_english_pair(a,b)
  b=self.payload('jev');b['requests']['blue_images_0_decision_001']['images']=[{}]
  with self.assertRaises(Exception):m.check_english_pair(a,b)
 def test_combined_builder_embeds_mocked_group_data_offline_and_refuses_overwrite(self):
  m=importlib.import_module('tools.make_text_study_report')
  with tempfile.TemporaryDirectory() as directory:
   root=Path(directory);(root/'wire_requests').mkdir();groups={'zh':self.payload(language='zh'),'en':self.payload(),'jev':self.payload('jev')}
   for g,p in groups.items():p['manifest']={'reference':{'CPU_fixture_only':True}}
   def builder(source,replay,output):
    output.write_text('<script id="report-data" type="application/json">'+json.dumps(groups[replay.name])+'</script>');return output
   with patch.object(m,'build_binding_report',side_effect=builder):
    out=m.build_study_report(root,root/'zh',root/'en',root/'jev',root/'report.html');self.assertIn('英文Jev',out.read_text());self.assertIn('CPU_fixture_only',out.read_text())
    with self.assertRaises(FileExistsError):m.build_study_report(root,root/'zh',root/'en',root/'jev',out)

if __name__=='__main__':unittest.main()
