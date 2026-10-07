"""Single-field target identity regression and14-call replay contracts, CPU only."""
import contextlib,copy,importlib,io,json,re,unittest
from unittest.mock import Mock
from tests import test_image_ablation as fixtures
from visual_lab.core import ACTIONS,LabError,ProtocolError
from visual_lab.image_ablation import image_request,run_image_replay

def module():return importlib.import_module('visual_lab.goal_binding')

class BindingRequestTests(unittest.TestCase):
 setUp=fixtures.ImageRequestContracts.setUp
 def old(self,color='yellow'):
  return image_request(self.pngs,self.state,self.views,self.guidance,{'color':color,'views':0},prompt_policy='modality_aware_v1')
 def test_only_one_description_prefix_changes(self):
  for color,word in [('blue','蓝色'),('yellow','黄色')]:
   old=self.old(color);saved=copy.deepcopy(old);new=module().binding_request(old,color)
   description=new['state']['goal_guidance']['spatial_description'];previous=old['state']['goal_guidance']['spatial_description']
   self.assertTrue(description.endswith(previous));self.assertIn(word+'方形轮廓线就是',description);self.assertIn('内部',description)
   new['state']['goal_guidance']['spatial_description']=previous
   self.assertEqual(new,old);self.assertEqual(old,saved)
 def test_no_geometry_truth_or_new_action_conditions(self):
  old=self.old();new=module().binding_request(old,'yellow');self.assertEqual(new['questions'],old['questions'])
  a=old['state']['goal_guidance']['spatial_description'];b=new['state']['goal_guidance']['spatial_description']
  self.assertEqual(re.findall(r'[-+]?\d+(?:\.\d+)?',a),re.findall(r'[-+]?\d+(?:\.\d+)?',b))
  self.assertEqual(new['images'],[]);self.assertEqual(new['state']['camera_views'],[])
 def test_rejects_wrong_color_task_images_and_missing_description(self):
  old=self.old()
  with self.assertRaises(ProtocolError):module().binding_request(old,'blue')
  for key in ['task','images','spatial']:
   dirty=copy.deepcopy(old)
   if key=='task':dirty['state']['task']='unknown'
   elif key=='images':dirty['images']=[{'type':'image/png','data':'bogus'}]
   else:dirty['state']['goal_guidance'].pop('spatial_description')
   with self.assertRaises(ProtocolError):module().binding_request(dirty,'yellow')

class BindingReplayTests(unittest.TestCase):
 setUp=fixtures.ImageReplayContracts.setUp
 tearDown=fixtures.ImageReplayContracts.tearDown
 def reference(self):
  target=self.root/'reference'
  with contextlib.redirect_stdout(io.StringIO()):run_image_replay(self.source,target,self.client,prompt_policy='modality_aware_v1',allow_mock=True)
  return target
 def replay(self,reference):
  with contextlib.redirect_stdout(io.StringIO()):return module().run_binding_replay(self.source,reference,self.output,self.client,allow_mock=True)
 def test_exact14_requests_frozen_before_first_call(self):
  ref=self.reference();original=self.client.predict;checked=[False]
  def predict(request):
   if not checked[0]:
    self.assertEqual(len(list((self.output/'requests').glob('*.json'))),14);manifest=json.loads((self.output/'manifest.json').read_text());self.assertEqual(len(manifest['planned_order']),14)
    self.assertTrue(all(job['image_count']==0 for job in manifest['planned_order']));checked[0]=True
   return original(request)
  self.client.predict=predict;result=self.replay(ref)
  self.assertTrue(result['complete']);self.assertEqual(result['api_completed'],14);self.assertFalse(result['model_had_control']);self.assertTrue(checked[0])
  self.assertEqual(len(result['cells']),2);self.assertEqual(len(result['decisions']),14)
  with self.assertRaises(FileExistsError):self.replay(ref)
 def test_reference_tamper_rejected_before_any_new_call(self):
  ref=self.reference();next((ref/'requests').glob('*_images_0_*.json')).write_text('{}');self.client.predict=Mock()
  with self.assertRaisesRegex(LabError,'hash'):self.replay(ref)
  self.client.predict.assert_not_called();self.assertFalse(self.output.exists())
 def test_failure_stops_without_retry(self):
  ref=self.reference();self.client.predict=Mock(side_effect=ProtocolError('CPU fixture failure'))
  result=self.replay(ref);self.assertFalse(result['complete']);self.assertEqual(result['api_completed'],0);self.client.predict.assert_called_once()
 def test_busy_service_rejected_before_call(self):
  ref=self.reference();health=self.client.health;self.client.health=lambda **kw:{**health(**kw),'busy':True};self.client.predict=Mock()
  with self.assertRaises(ProtocolError):self.replay(ref)
  self.client.predict.assert_not_called()
 def test_changed_service_count_or_request_invalidates(self):
  ref=self.reference();predict=self.client.predict
  def corrupt(request):
   raw,latency=predict(request)
   for path in (self.output/'requests').glob('*.json'):path.write_text('{}')
   return raw,latency
  self.client.predict=corrupt;result=self.replay(ref);self.assertFalse(result['complete']);self.assertEqual(result['api_completed'],1)

class BindingReportTests(unittest.TestCase):
 setUp=BindingReplayTests.setUp
 tearDown=BindingReplayTests.tearDown
 reference=BindingReplayTests.reference
 replay=BindingReplayTests.replay
 def test_report_embeds14_actual_empty_requests_and_pair_probabilities(self):
  ref=self.reference();self.replay(ref);out=self.root/'report.html';module().build_binding_report(self.source,self.output,out,allow_mock=True)
  text=out.read_text();data=json.loads(re.search(r'<script id="report-data" type="application/json">(.*?)</script>',text,re.S).group(1))
  self.assertEqual(len(data['requests']),14);self.assertEqual(len(data['responses']),14);self.assertTrue(all(r['images']==[] for r in data['requests'].values()))
  self.assertIn('不提供图片',text);self.assertIn('不是自主成功率',text)
  with self.assertRaises(FileExistsError):module().build_binding_report(self.source,self.output,out,allow_mock=True)
 def test_report_rejects_synthetic_as_real_and_changed_response(self):
  ref=self.reference();self.replay(ref)
  with self.assertRaises(LabError):module().build_binding_report(self.source,self.output,self.root/'real.html')
  next((self.output/'responses').glob('*.json')).write_text('{}')
  with self.assertRaisesRegex(LabError,'hash'):module().build_binding_report(self.source,self.output,self.root/'bad.html',allow_mock=True)

if __name__=='__main__':unittest.main()
