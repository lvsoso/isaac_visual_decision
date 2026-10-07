"""Three-group offline report invariants, no live vendor or GPU calls."""
import copy,importlib,json,tempfile,unittest
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

if __name__=='__main__':unittest.main()
