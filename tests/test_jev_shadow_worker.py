"""One-operation private worker wire tests, fake HTTPS only."""
import contextlib,importlib,io,json,tempfile,unittest,urllib.error,urllib.request
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock,patch
from visual_lab.core import LabError,ProtocolError,model_state,load_config
from visual_lab.jev import JevClient,JEV_URL,jev_payload
from visual_lab.factorial import goal_guidance
from tests.test_jev_shadow import raw,FakeClient

class WorkerTests(unittest.TestCase):
    def setUp(self):
        self.mod=importlib.import_module('tools.jev_shadow_worker');self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
        shadow=importlib.import_module('visual_lab.jev_shadow');self.request=shadow.online_request(model_state({'ee_world_position_m':[.5,.2,.4],'finger_joint_position_rad':.5},None,None),goal_guidance([.5,.5,.05],[.5,.5,.235],[.5,.2,.4],'tool0'),'blue')
        self.client=JevClient(token='CPU-fixture-secret');self.inner=Mock();self.client.opener=self.inner;self.body=json.dumps(raw()).encode();self.inner.open.side_effect=self.response
    def tearDown(self):self.tmp.cleanup()
    def response(self,*args,**kw):
        r=io.BytesIO(self.body);r.status=200;r.headers={'x-typesafe-request-id':'fixture-id','content-type':'application/json'};return r
    def test_one_call_per_worker_raw_archived_before_validation(self):
        result=self.mod.perform(self.client,{'op':'predict','request':self.request},'blue',self.root/'capture')
        self.assertTrue(result['ok']);self.assertEqual(result['response'],raw());self.inner.open.assert_called_once()
        self.assertEqual((self.root/'capture/response.body').read_bytes(),self.body)
        meta=json.loads((self.root/'capture/response_meta.json').read_text());self.assertEqual(meta['request_id'],'fixture-id');self.assertTrue(meta['saved_before_business_validation'])
        with self.assertRaises(ProtocolError):self.client.opener.open(urllib.request.Request(JEV_URL,data=json.dumps(jev_payload(self.request),ensure_ascii=False,allow_nan=False).encode()),timeout=60)
    def test_template_change_rejected_before_call(self):
        self.request['questions']['next_stage']['instructions']='changed'
        with self.assertRaises(ProtocolError):self.mod.perform(self.client,{'op':'predict','request':self.request},'blue',self.root/'capture')
        self.inner.open.assert_not_called()
    def test_invalid_basic_numeric_response_is_still_retained(self):
        invalid=raw();invalid['answers']['next_stage']['probabilities']['abort']=-.1;self.body=json.dumps(invalid).encode()
        with self.assertRaises(ProtocolError):self.mod.perform(self.client,{'op':'predict','request':self.request},'blue',self.root/'capture')
        self.assertEqual((self.root/'capture/response.body').read_bytes(),self.body);self.assertEqual(self.client.requests_completed,0)
    def test_http_error_is_safe_archived_without_retry(self):
        self.inner.open.side_effect=urllib.error.HTTPError(JEV_URL,429,'fixture',{'x-typesafe-request-id':'error-id'},io.BytesIO(b'{"detail":"fixture rate limit"}'))
        with self.assertRaises(Exception):self.mod.perform(self.client,{'op':'predict','request':self.request},'blue',self.root/'capture')
        self.assertEqual(json.loads((self.root/'capture/response_meta.json').read_text())['status_code'],429);self.inner.open.assert_called_once()
    def test_private_response_not_written_or_returned(self):
        self.body=b'{"debug":"CPU-fixture-\\u0073ecret"}'
        with self.assertRaises(LabError):self.mod.perform(self.client,{'op':'predict','request':self.request},'blue',self.root/'capture')
        self.assertFalse((self.root/'capture/response.body').exists())
    def test_stdio_main_health_and_bad_message_do_not_emit_secrets(self):
        for data,success in [(b'{"op":"health"}',True),(b'bad JSON',False),(b'{"op":"unknown"}',False),(b'x'*(2*1024*1024+1),False)]:
            output=io.StringIO();args=['worker','--key-file','fixture.key','--goal-color','blue']
            with patch.object(self.mod.sys,'argv',args),patch.object(self.mod.sys,'stdin',SimpleNamespace(buffer=io.BytesIO(data))),patch.object(self.mod,'JevClient',return_value=FakeClient()),contextlib.redirect_stdout(output):code=self.mod.main()
            result=json.loads(output.getvalue());self.assertEqual(result['ok'],success);self.assertEqual(code,0 if success else 2);self.assertNotIn('CPU-fixture-secret',output.getvalue())

if __name__=='__main__':unittest.main()
