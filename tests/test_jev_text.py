"""English equivalence and Jev transport contracts; fake HTTP, no live key."""
import copy,importlib,io,json,re,unittest,urllib.error
from unittest.mock import Mock
from tests import test_image_ablation as fixtures
from visual_lab.image_ablation import image_request
from visual_lab.core import ACTIONS,ProtocolError

def mod():return importlib.import_module('visual_lab.jev')

class EnglishTests(unittest.TestCase):
 setUp=fixtures.ImageRequestContracts.setUp
 def test_translation_has_no_cjk_and_retains_numeric_evidence_and_labels(self):
  from visual_lab.goal_binding import binding_request
  for color in ['blue','yellow']:
   old=image_request(self.pngs,self.state,self.views,self.guidance,{'color':color,'views':0},prompt_policy='modality_aware_v1');bound=binding_request(old,color)
   english=importlib.import_module('visual_lab.text_english').english_request(bound,color)
   self.assertNotRegex(json.dumps(english,ensure_ascii=False),r'[\u4e00-\u9fff]');self.assertEqual(english['images'],[])
   self.assertEqual(tuple(english['questions']['next_stage']['criteria']),ACTIONS)
   for key in ['previous_action','previous_result','finger_joint_position_rad','gripper_command_reference_rad','camera_views']:self.assertEqual(english['state'][key],bound['state'][key])
   for key in ['spatial_description']:
    self.assertEqual(re.findall(r'[-+]?\d+(?:\.\d+)?',english['state']['goal_guidance'][key]),re.findall(r'[-+]?\d+(?:\.\d+)?',bound['state']['goal_guidance'][key]))
   self.assertIn(color+' square ground outline',english['state']['task']);self.assertIn('the configured ground outline',english['state']['goal_guidance']['spatial_description'])

class JevTests(unittest.TestCase):
 def request(self):return {'state':{'task':'CPU fixture only','camera_views':[]},'images':[],'questions':{'next_stage':{'type':'choice','instructions':'fixture','criteria':{a:a for a in ACTIONS}}}}
 def raw(self):return {'model':'jev-1.13.0','answers':{'next_stage':{'type':'choice','choice':'abort','probabilities':{a:.125 if a!='abort' else .125 for a in ACTIONS},'confidence':0.0}},'usage':{'input_tokens':100,'output_tokens':20}}
 def test_payload_removes_empty_images_only_and_pins_model(self):
  original=self.request();saved=copy.deepcopy(original);body=mod().jev_payload(original)
  self.assertEqual(body,{'model':'jev-1.13.0','state':original['state'],'questions':original['questions']});self.assertEqual(original,saved)
  original['images']=[{}]
  with self.assertRaises(ProtocolError):mod().jev_payload(original)
 def test_confidence_formula_is_not_top_probability_and_ties_preserved(self):
  answer=mod().verify_jev_response(self.raw());self.assertEqual(answer.action,'abort');self.assertEqual(answer.confidence,0.0)
  self.assertEqual(max(answer.probabilities.values()),.125)
  bad=self.raw();bad['answers']['next_stage']['confidence']=.125
  with self.assertRaisesRegex(ProtocolError,'confidence'):mod().verify_jev_response(bad)
 def test_wrong_model_bad_candidates_or_usage_are_rejected(self):
  for field in ['model','probabilities','usage']:
   bad=self.raw()
   if field=='model':bad['model']='jev-latest'
   elif field=='probabilities':bad['answers']['next_stage']['probabilities'].pop('abort')
   else:bad['usage']['input_tokens']=-1
   with self.assertRaises(ProtocolError):mod().verify_jev_response(bad)
 def test_https_fixed_host_no_redirect_and_single_call(self):
  client=mod().JevClient(token='CPU-fixture-secret');client.opener=Mock()
  response=io.BytesIO(json.dumps(self.raw()).encode());client.opener.open.return_value=response
  raw,latency=client.predict(self.request());self.assertEqual(raw,self.raw());self.assertGreaterEqual(latency,0)
  request=client.opener.open.call_args.args[0];self.assertEqual(request.full_url,'https://api.typesafe.ai/v1/systemone')
  self.assertEqual(json.loads(request.data),mod().jev_payload(self.request()));self.assertEqual(client.requests_completed,1);client.opener.open.assert_called_once()
  self.assertIsNone(mod().NoRedirect().redirect_request(request,None,302,'redirect',{},'https://evil.example'))
 def test_http_error_does_not_leak_key_or_response_body_and_never_retries(self):
  client=mod().JevClient(token='CPU-fixture-secret');client.opener=Mock();client.opener.open.side_effect=urllib.error.HTTPError('https://api.typesafe.ai',401,'bad',{},io.BytesIO(b'CPU-fixture-secret'))
  with self.assertRaises(Exception) as raised:client.predict(self.request())
  self.assertNotIn('CPU-fixture-secret',str(raised.exception));client.opener.open.assert_called_once();self.assertEqual(client.requests_completed,0)
 def test_missing_key_and_non_json_responses_are_not_fabricated(self):
  with self.assertRaises(ProtocolError):mod().JevClient(token='')
  client=mod().JevClient(token='CPU-fixture-secret');client.opener=Mock();client.opener.open.return_value=io.BytesIO(b'not JSON')
  with self.assertRaises(Exception):client.predict(self.request())
  self.assertEqual(client.requests_completed,0)
 def test_success_body_cannot_echo_private_key_into_artifacts(self):
  client=mod().JevClient(token='CPU-fixture-secret');client.opener=Mock();raw=self.raw();raw['debug']='CPU-fixture-secret'
  client.opener.open.return_value=io.BytesIO(json.dumps(raw).encode())
  with self.assertRaises(Exception) as raised:client.predict(self.request())
  self.assertNotIn('CPU-fixture-secret',str(raised.exception));self.assertEqual(client.requests_completed,0)
 def test_health_uses_cached_models_list_and_size_and_network_errors_stop(self):
  client=mod().JevClient(token='CPU-fixture-secret');client.opener=Mock();client.opener.open.return_value=io.BytesIO(b'{"models":[{"name":"jev-latest","release_date":"fixture"}]}')
  self.assertEqual(client.health()['model'],'jev-1.13.0');client.health();client.opener.open.assert_called_once()
  for response in [b'x'*(2*1024*1024+1),b'[]',b'{}']:
   c=mod().JevClient(token='CPU-fixture-secret');c.opener=Mock();c.opener.open.return_value=io.BytesIO(response)
   with self.assertRaises(Exception):c.health()
  c=mod().JevClient(token='CPU-fixture-secret');c.opener=Mock();c.opener.open.side_effect=urllib.error.URLError('CPU-fixture-secret')
  with self.assertRaises(Exception) as raised:c.health()
  self.assertNotIn('CPU-fixture-secret',str(raised.exception))
 def test_invalid_probability_response_is_retained_without_retry_or_normalization(self):
  client=mod().JevClient(token='CPU-fixture-secret');client.opener=Mock();raw=self.raw();raw['answers']['next_stage']['probabilities']['abort']=.0
  client.opener.open.return_value=io.BytesIO(json.dumps(raw).encode())
  with self.assertRaises(ProtocolError):client.predict(self.request())
  self.assertEqual(client.last_response,raw);self.assertEqual(client.requests_completed,0);self.assertEqual(client.attempts,1);client.opener.open.assert_called_once()
 def test_private_echo_is_never_retained_as_last_response(self):
  client=mod().JevClient(token='CPU-fixture-secret');client.opener=Mock();raw=self.raw();raw['debug']='CPU-fixture-secret'
  client.opener.open.return_value=io.BytesIO(json.dumps(raw).encode())
  with self.assertRaises(Exception):client.predict(self.request())
  self.assertIsNone(client.last_response)

if __name__=='__main__':unittest.main()
