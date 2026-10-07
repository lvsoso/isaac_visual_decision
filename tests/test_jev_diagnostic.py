"""One-call capture and numeric diagnosis; no SDK install or live key required."""
import copy,importlib,json,tempfile,unittest
from pathlib import Path
from types import SimpleNamespace
from visual_lab.core import ACTIONS,LabError

def mod():return importlib.import_module('visual_lab.jev_diagnostic')
def payload():return {'model':'jev-1.13.0','state':{'task':'CPU fixture','camera_views':[]},'questions':{'next_stage':{'type':'choice','instructions':'fixture','criteria':{a:a for a in ACTIONS}}}}
def raw():return {'model':'jev-1.13.0','answers':{'next_stage':{'type':'choice','choice':'abort','probabilities':{a:.125 for a in ACTIONS},'confidence':0.0}},'usage':{'input_tokens':100,'output_tokens':20}}

class DiagnosticTests(unittest.TestCase):
 def setUp(self):self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name);self.output=self.root/'capture'
 def tearDown(self):self.tmp.cleanup()
 def capture(self):return mod().DiagnosticCapture(self.output,payload(),token='CPU-fixture-secret')
 def request(self,body=None,url='https://api.typesafe.ai/v1/systemone'):
  return SimpleNamespace(method='POST',url=url,content=json.dumps(payload() if body is None else body).encode())
 def test_request_frozen_and_one_call_budget_persisted(self):
  c=self.capture();c.before_send(self.request());self.assertEqual(c.attempts,1)
  self.assertEqual(json.loads((self.output/'request.body').read_bytes()),payload());self.assertTrue((self.output/'CALL_STARTED.json').exists())
  with self.assertRaises(LabError):c.before_send(self.request())
  self.assertEqual(c.attempts,1)
  with self.assertRaises(FileExistsError):self.capture()
 def test_wrong_endpoint_changed_body_or_order_rejected_before_send(self):
  c=self.capture();dirty=payload();dirty['state']['task']='different'
  for request in [self.request(url='https://evil.example'),self.request(body=dirty)]:
   with self.assertRaises(LabError):c.before_send(request)
  dirty=payload();dirty['questions']['next_stage']['criteria']=dict(reversed(list(dirty['questions']['next_stage']['criteria'].items())))
  with self.assertRaises(LabError):c.before_send(self.request(body=dirty))
  self.assertEqual(c.attempts,0)
 def test_safe_invalid_probability_body_saved_exact_before_validation(self):
  c=self.capture();c.before_send(self.request());r=raw();r['answers']['next_stage']['probabilities']['abort']=0.0;body=json.dumps(r,indent=2).encode()
  c.record_response(200,{'content-type':'application/json','x-typesafe-request-id':'fixture-id','set-cookie':'private','authorization':'CPU-fixture-secret'},body)
  self.assertEqual((self.output/'response.body').read_bytes(),body);meta=json.loads((self.output/'response_meta.json').read_text())
  self.assertEqual(meta['request_id'],'fixture-id');self.assertNotIn('authorization',meta['headers']);self.assertNotIn('set-cookie',meta['headers'])
   d=mod().audit_choice_response(r);self.assertTrue(d['project_valid']);self.assertEqual(d['validation_policy'],'jev_sdk_basic_v1');self.assertFalse(d['sum_check_enforced']);self.assertFalse(d['confidence_formula_enforced']);self.assertEqual(d['probability_sum'],.875);self.assertEqual(d['probability_sum_decimal'],'0.875');self.assertEqual(d['probabilities'],r['answers']['next_stage']['probabilities'])
 def test_secret_echo_never_written_even_when_json_escaped(self):
  c=self.capture();c.before_send(self.request());r=raw();r['debug']='CPU-fixture-secret';body=json.dumps(r).replace('CPU-fixture-secret','CPU-fixture-\\u0073ecret').encode()
  with self.assertRaises(LabError) as e:c.record_response(200,{},body)
  self.assertNotIn('CPU-fixture-secret',str(e.exception));self.assertFalse((self.output/'response.body').exists())
 def test_oversized_body_is_not_archived(self):
  c=self.capture();c.before_send(self.request())
  with self.assertRaises(LabError):c.record_response(200,{},b'x'*(2*1024*1024+1))
  self.assertFalse((self.output/'response.body').exists())
 def test_non_json_or_http_error_body_retained_as_evidence_not_decision(self):
  c=self.capture();c.before_send(self.request());c.record_response(422,{'content-type':'text/plain'},b'fixture non-JSON error')
  self.assertEqual((self.output/'response.body').read_bytes(),b'fixture non-JSON error');self.assertEqual(json.loads((self.output/'response_meta.json').read_text())['status_code'],422)
 def test_range_and_sum_failures_are_distinct_and_raw_not_mutated(self):
  r=raw();r['answers']['next_stage']['probabilities']['abort']=-.01;saved=copy.deepcopy(r);d=mod().audit_choice_response(r)
  self.assertEqual(d['out_of_range'],{'abort':-.01});self.assertFalse(d['sum_within_project_tolerance']);self.assertEqual(r,saved)
 def test_normal_response_tie_and_confidence_formula_remain_separate(self):
  d=mod().audit_choice_response(raw());self.assertTrue(d['project_valid']);self.assertEqual(d['top_probability_ties'],list(ACTIONS));self.assertTrue(d['selected_is_argmax']);self.assertEqual(d['expected_confidence'],0.0)
 def test_missing_candidates_or_nonfinite_values_diagnosed_without_filling(self):
  r=raw();r['answers']['next_stage']['probabilities'].pop('abort');d=mod().audit_choice_response(r);self.assertEqual(d['missing_candidates'],['abort']);self.assertFalse(d['project_valid'])
  r=raw();r['answers']['next_stage']['probabilities']['abort']=float('nan');d=mod().audit_choice_response(r);self.assertFalse(d['all_finite']);self.assertIsNone(d['probability_sum'])

if __name__=='__main__':unittest.main()
