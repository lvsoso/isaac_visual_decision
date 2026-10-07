"""Frozen14 wire capture contracts; no real API or credentials."""
import copy,importlib,io,json,tempfile,unittest,urllib.error,urllib.request
from pathlib import Path
from unittest.mock import Mock,patch
from visual_lab.core import ACTIONS,LabError
from visual_lab.jev import JEV_URL,JevClient,jev_payload
from tools.freeze_text_study import body_sha256

def module():
    return importlib.import_module('tools.run_frozen_jev')

class FrozenJevTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
        old=json.loads(Path('test_reports/text_study_input_review_20261007.json').read_text())
        self.frozen={'requests':old['requests']['jev'],'planned_order':[j for j in old['planned_order'] if j['group']=='jev'],
                     'http_body_sha256':old['http_body_sha256']['jev']}
        self.raw={'model':'jev-1.13.0','answers':{'next_stage':{'type':'choice','choice':'abort','confidence':.55,
                  'probabilities':{a:.125 if a!='abort' else 0.0 for a in ACTIONS}}},'usage':{'input_tokens':100,'output_tokens':20}}
        self.body=json.dumps(self.raw,separators=(',',':')).encode()
        self.inner=Mock();self.inner.open.side_effect=self.response
    def tearDown(self):
        self.tmp.cleanup()
    def response(self,*args,**kwargs):
        stream=io.BytesIO(self.body);stream.status=200;stream.headers={'content-type':'application/json','x-typesafe-request-id':'fixture-id','set-cookie':'private'}
        return stream
    def capture(self):
        return module().CaptureOpener(self.frozen,self.root/'wire',self.inner,token='CPU-fixture-secret')
    def request(self,index=0):
        name=self.frozen['planned_order'][index]['name'];body=json.dumps(jev_payload(self.frozen['requests'][name]),ensure_ascii=False,allow_nan=False).encode()
        return urllib.request.Request(JEV_URL,data=body)
    def test_all14_actual_bodies_frozen_and_raw_kept_before_basic_validation(self):
        capture=self.capture();client=JevClient(token='CPU-fixture-secret');client.opener=capture
        for job in self.frozen['planned_order']:
            result,_=client.predict(self.frozen['requests'][job['name']]);self.assertEqual(result,self.raw)
            path=self.root/'wire'/job['name'];self.assertEqual((path/'response.body').read_bytes(),self.body)
            self.assertEqual(body_sha256(json.loads((path/'request.body').read_bytes())),self.frozen['http_body_sha256'][job['name']])
            meta=json.loads((path/'response_meta.json').read_text());self.assertEqual(meta['request_id'],'fixture-id');self.assertNotIn('set-cookie',meta['headers'])
        self.assertEqual(client.requests_completed,14);self.assertEqual(capture.attempts,14);self.assertEqual(self.inner.open.call_count,14)
        with self.assertRaises(LabError):capture.open(self.request(),timeout=60)
        self.assertEqual(self.inner.open.call_count,14)
    def test_wrong_order_body_or_host_never_sent(self):
        capture=self.capture();wrong=self.request();wrong.data=b'{}'
        for req in [self.request(1),wrong,urllib.request.Request('https://evil.example',data=b'{}')]:
            with self.assertRaises(LabError):capture.open(req,timeout=60)
        self.assertEqual(capture.attempts,0);self.inner.open.assert_not_called()
    def test_duplicate_call_or_restart_cannot_reuse_a_consumed_slot(self):
        capture=self.capture();capture.open(self.request(),timeout=60)
        with self.assertRaises(LabError):capture.open(self.request(),timeout=60)
        with self.assertRaises(FileExistsError):self.capture()
        self.assertTrue((self.root/'wire'/self.frozen['planned_order'][0]['name']/'CALL_STARTED.json').exists())
        self.inner.open.assert_called_once()
    def test_http_error_retains_safe_body_and_request_id_but_no_retry(self):
        capture=self.capture();error=urllib.error.HTTPError(JEV_URL,422,'fixture',{'x-typesafe-request-id':'error-id'},io.BytesIO(b'{"detail":"fixture"}'));self.inner.open.side_effect=error
        with self.assertRaises(urllib.error.HTTPError):capture.open(self.request(),timeout=60)
        path=self.root/'wire'/self.frozen['planned_order'][0]['name'];self.assertEqual((path/'response.body').read_bytes(),b'{"detail":"fixture"}')
        self.assertEqual(json.loads((path/'response_meta.json').read_text())['status_code'],422);self.inner.open.assert_called_once()
    def test_private_echo_and_size_limit_do_not_persist_body(self):
        for body in [b'{"debug":"CPU-fixture-\\u0073ecret"}',b'x'*(2*1024*1024+1)]:
            with tempfile.TemporaryDirectory(dir=self.root) as folder:
                self.body=body;capture=module().CaptureOpener(self.frozen,Path(folder)/'wire',self.inner,token='CPU-fixture-secret')
                with self.assertRaises(LabError) as raised:capture.open(self.request(),timeout=60)
                self.assertNotIn('CPU-fixture-secret',str(raised.exception));self.assertFalse(list((Path(folder)/'wire').glob('*/response.body')))
    def test_health_get_is_not_a_prediction_and_wrong_method_is_denied(self):
        capture=self.capture();capture.open(urllib.request.Request('https://api.typesafe.ai/v1/models'),timeout=60)
        self.assertEqual(capture.attempts,0)
        with self.assertRaises(LabError):capture.open(urllib.request.Request(JEV_URL),timeout=60)
    def test_non_json_response_evidence_is_not_lost(self):
        self.body=b'fixture invalid JSON';capture=self.capture();client=JevClient(token='CPU-fixture-secret');client.opener=capture
        with self.assertRaises(Exception):client.predict(self.frozen['requests'][self.frozen['planned_order'][0]['name']])
        self.assertEqual((self.root/'wire'/self.frozen['planned_order'][0]['name']/'response.body').read_bytes(),self.body);self.assertEqual(client.requests_completed,0)
    def test_incomplete_freeze_is_rejected(self):
        bad=copy.deepcopy(self.frozen);bad['planned_order'].pop()
        with self.assertRaises(LabError):module().CaptureOpener(bad,self.root/'wire',self.inner,token='CPU-fixture-secret')
    def test_cli_complete14_with_fake_network_and_frozen_source_gate(self):
        mod=module();self.frozen.update(code_sha256=mod.binding_code_hashes(),driver_sha256=mod.sha256_file(Path(mod.__file__)),
            model='jev-1.13.0',validation_policy='jev_sdk_basic_v1',count=14,seed=20261006,reference_files_sha256={'fixture':'hash'})
        frozen=self.root/'frozen.json';frozen.write_text(json.dumps(self.frozen));client=JevClient(token='CPU-fixture-secret');client.opener=self.inner
        def replay(source,reference,output,actual_client,**kwargs):
            for job in self.frozen['planned_order']:actual_client.predict(self.frozen['requests'][job['name']])
            return {'complete':True,'api_completed':14,'error':None}
        args=['run_frozen_jev','--source',str(self.root/'source'),'--reference',str(self.root/'reference'),'--frozen',str(frozen),
              '--output',str(self.root/'output'),'--wire-output',str(self.root/'wire'),'--lifecycle',str(self.root/'life.json'),'--authorize-fourteen-calls']
        with patch.object(mod.sys,'argv',args),patch.object(mod,'JevClient',return_value=client),patch.object(mod,'binding_reference',return_value={'files_sha256':{'fixture':'hash'}}),patch.object(mod,'binding_inputs',return_value=self.frozen['requests']),patch.object(mod,'run_binding_replay',side_effect=replay),patch.object(mod,'build_binding_report'):
            self.assertEqual(mod.main(),0)
        life=json.loads((self.root/'life.json').read_text());self.assertTrue(life['complete']);self.assertEqual(life['actual_transport_attempts'],14);self.assertEqual(self.inner.open.call_count,14)
    def test_cli_requires_authorization_before_any_io(self):
        mod=module();args=['run_frozen_jev']
        for name in ['source','reference','frozen','output','wire-output','lifecycle']:args.extend(['--'+name,str(self.root/name)])
        with patch.object(mod.sys,'argv',args),self.assertRaises(SystemExit) as raised:mod.main()
        self.assertEqual(raised.exception.code,2);self.inner.open.assert_not_called()

if __name__=='__main__':unittest.main()
