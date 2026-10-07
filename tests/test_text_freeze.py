"""All42transports must be fixed before the first inference, CPU fixtures only."""
import contextlib,importlib,io,json,unittest
from unittest.mock import Mock
from tests import test_goal_binding as fixtures
from visual_lab.core import LabError

class TextFreezeTests(unittest.TestCase):
 setUp=fixtures.BindingReplayTests.setUp
 tearDown=fixtures.BindingReplayTests.tearDown
 reference=fixtures.BindingReplayTests.reference
 def test_freezes42requests_three_groups_and_actual_body_hashes(self):
  m=importlib.import_module('tools.freeze_text_study');ref=self.reference();frozen=self.root/'freeze'
  result=m.freeze_text_study(self.source,ref,frozen,allow_mock=True)
  self.assertEqual(len(result['planned_order']),42);self.assertEqual([j['group'] for j in result['planned_order']],[g for g in ['zh','en','jev'] for _ in range(14)])
  self.assertEqual(result['requests']['en'],result['requests']['jev'])
  self.assertEqual(len(list(frozen.glob('*/requests/*.json'))),42);self.assertEqual(len(list(frozen.glob('*/wire_requests/*.json'))),42)
  for g in ['zh','en','jev']:
   for name,req in result['requests'][g].items():m.verify_study_request(result,g,name,req)
  with self.assertRaises(FileExistsError):m.freeze_text_study(self.source,ref,frozen,allow_mock=True)
 def test_changed_request_fails_before_prediction(self):
  m=importlib.import_module('tools.freeze_text_study');ref=self.reference();f=m.freeze_text_study(self.source,ref,self.root/'freeze',allow_mock=True)
  name=next(iter(f['requests']['en']));request=f['requests']['en'][name].copy();request['images']=[{}]
  with self.assertRaises(LabError):m.verify_study_request(f,'en',name,request)

if __name__=='__main__':unittest.main()
