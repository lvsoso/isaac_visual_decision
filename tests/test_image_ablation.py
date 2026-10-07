"""Image deletion contracts and explicit CPU fixtures, not model/GPU quality."""
import base64
import contextlib
import copy
import importlib
import io
import json
import re
import tempfile
import threading
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

from tests.test_factorial import FakeScene, ROOT
from visual_lab.audit import AuditLog, sha256_file
from visual_lab.client import DecisionClient, ModelAPIError
from visual_lab.core import ACTIONS, LabError, ProtocolError, load_config, model_state
from visual_lab.factorial import collect_episode, goal_guidance, view_metadata
from visual_lab.png import encode_rgb_bytes
from visual_lab.prompt_variants import prompt_request
from visual_lab.protocol import make_request, validate_request
from visual_lab.server import DecisionBridge, MockEngine, OfficialEngine, make_http_server


class TextOnlyContracts(unittest.TestCase):
    def setUp(self):
        self.png=encode_rgb_bytes(2,2,bytes([20,30,150]*4))
        self.request=make_request(self.png,{'previous_action':None});self.request['images']=[]

    def test_default_still_rejects_empty_images(self):
        with self.assertRaises(ProtocolError):make_request([],{'previous_action':None})
        with self.assertRaises(ProtocolError):validate_request(self.request)
        with self.assertRaises(ProtocolError):DecisionBridge(MockEngine()).predict(self.request)

    def test_explicit_builder_and_validation_allow_true_empty_list(self):
        request=make_request([],{'previous_action':None},allow_empty_images=True)
        validate_request(request,allow_empty_images=True)
        self.assertEqual(request['images'],[])
        self.assertEqual(tuple(request['questions']['next_stage']['criteria']),ACTIONS)
        for bad in [None,{},'', [self.request['state']]*3]:
            dirty=copy.deepcopy(request);dirty['images']=bad
            with self.assertRaises(ProtocolError):validate_request(dirty,allow_empty_images=True)

    def test_opt_in_http_has_zero_png_paths_and_no_fake_hash(self):
        seen=[];engine=MockEngine()
        def predict(internal):seen.append(copy.deepcopy(internal));return engine.predict(internal)
        wrapper=SimpleNamespace(metadata=engine.metadata,predict=predict)
        bridge=DecisionBridge(wrapper,allow_text_only=True)
        server=make_http_server('127.0.0.1',0,bridge);thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        client=DecisionClient(f'http://127.0.0.1:{server.server_port}/v1/decisions')
        try:
            self.assertTrue(client.health(allow_mock=True)['supports_text_only_ablation'])
            raw,_=client.predict(self.request)
            self.assertEqual(seen[0]['images'],[])
            self.assertEqual(seen[0]['state'],self.request['state'])
            self.assertEqual(raw['_bridge']['image_count'],0)
            self.assertEqual(raw['_bridge']['image_sha256s'],[])
            self.assertIsNone(raw['_bridge']['image_sha256'])
            self.assertEqual(bridge.requests_completed,1)
            dirty=copy.deepcopy(self.request);dirty['images']=None
            with self.assertRaises(ModelAPIError):client.predict(dirty)
            self.assertEqual(bridge.requests_completed,1)
        finally:server.shutdown();server.server_close();thread.join(2)

    def test_default_health_does_not_enable_text_ablation(self):
        self.assertFalse(DecisionBridge(MockEngine()).health()['supports_text_only_ablation'])


class TokenizerAuditContracts(unittest.TestCase):
    def setUp(self):
        self.server=importlib.import_module('visual_lab.server')
        self.values=[10,11,12,13]
        self.batch={'input_ids':SimpleNamespace(shape=(1,4),tolist=lambda:[self.values])}
        self.kwargs=[]
        class Tokenizer:
            def __init__(inner):inner.tag='unchanged-tokenizer'
            def convert_tokens_to_ids(inner,token):return 100+self.server.VISION_TOKENS.index(token)
            def __call__(inner,*args,**kw):self.kwargs.append(kw);return self.batch
        self.proxy=self.server.TokenizerAudit(Tokenizer())

    def test_tokenizer_records_actual_length_zero_vision_tokens_without_changing_batch(self):
        result=self.proxy('actual text',return_tensors='pt')
        self.assertIs(result,self.batch)
        self.assertEqual(self.proxy.tag,'unchanged-tokenizer')
        self.assertIs(self.kwargs[0]['truncation'],False)
        self.assertEqual(self.proxy.last['input_tokens'],4)
        self.assertEqual(self.proxy.last['image_grid_thw'],[])
        self.assertEqual(self.proxy.last['normalized_rgb_sha256s'],[])
        self.assertEqual(self.proxy.last['encoding_path'],'tokenizer_only')
        self.assertTrue(all(count==0 for count in self.proxy.last['vision_token_counts'].values()))

    def test_truncation_rejected_before_tokenization(self):
        with self.assertRaisesRegex(ProtocolError,'truncation'):self.proxy('text',truncation=True)
        self.assertEqual(self.kwargs,[])

    def engine(self,callback):
        engine=OfficialEngine.__new__(OfficialEngine)
        engine.processor_audit=SimpleNamespace(last={'stale':'old image input'})
        engine.tokenizer_audit=self.proxy
        engine.metadata={'max_length':8192}
        engine.engine=SimpleNamespace(predict=callback)
        return engine

    def test_official_text_path_clears_stale_multimodal_audit(self):
        def predict(request):self.proxy('text');return MockEngine().predict(request)
        engine=self.engine(predict)
        raw=engine.predict({'state':{'previous_action':None},'images':[]})
        self.assertEqual(raw['_vision_audit']['encoding_path'],'tokenizer_only')
        self.assertEqual(raw['_vision_audit']['normalized_rgb_sha256s'],[])
        self.assertIsNone(engine.processor_audit.last)

    def test_missing_text_audit_or_visual_special_token_is_rejected(self):
        engine=self.engine(lambda request:MockEngine().predict(request))
        with self.assertRaisesRegex(ProtocolError,'audit'):engine.predict({'state':{},'images':[]})
        self.values[0]=100
        def predict(request):self.proxy('bad text');return MockEngine().predict(request)
        engine=self.engine(predict)
        with self.assertRaisesRegex(ProtocolError,'vision|visual'):engine.predict({'state':{},'images':[]})


class ImageRequestContracts(unittest.TestCase):
    def setUp(self):
        self.a=importlib.import_module('visual_lab.image_ablation')
        self.state=model_state({'ee_world_position_m':[.4,.2,.3],'finger_joint_position_rad':.5},'transport','reached')
        self.views=view_metadata(load_config(ROOT/'configs/default.json'))
        self.guidance=goal_guidance([.5,.5,0],[.5,.5,.235],[.5,.48,.55],'tool0')
        self.pngs=[encode_rgb_bytes(2,2,bytes(rgb*4)) for rgb in ([20,30,150],[220,180,20])]

    def request(self,color,views,state=None):
        cell=next(c for c in self.a.image_cells() if c['color']==color and c['views']==views)
        return self.a.image_request(self.pngs,state or self.state,self.views,self.guidance,cell)

    def test_six_cells_only_change_image_list(self):
        self.assertEqual(len(self.a.image_cells()),6)
        for color in ['blue','yellow']:
            requests=[self.request(color,n) for n in range(3)]
            for n,request in enumerate(requests):
                validate_request(request,allow_empty_images=True)
                self.assertEqual(len(request['images']),n)
                self.assertEqual(request['state'],requests[2]['state'])
                self.assertEqual(request['questions'],requests[2]['questions'])
                self.assertEqual(tuple(request['questions']['next_stage']['criteria']),ACTIONS)
            self.assertEqual(requests[1]['images'],requests[2]['images'][:1])

    def test_dual_request_matches_27_prompt_and_whitelist_blocks_truth(self):
        dirty=copy.deepcopy(self.state);dirty.update(expected_action='release',decision_id=7,holding=True,private_ground_truth={'cube':[9,9,9]})
        for color in ['blue','yellow']:
            old=prompt_request(self.pngs,self.state,self.views,self.guidance,{'variant':'zh_named_relative','color':color})
            self.assertEqual(self.request(color,2),old)
            for n in range(3):self.assertEqual(self.request(color,n),self.request(color,n,dirty))

    def test_bad_image_count_is_not_silently_clamped(self):
        for n in [-1,3,True]:
            with self.assertRaises(ProtocolError):self.a.image_request(self.pngs,self.state,self.views,self.guidance,{'color':'blue','views':n})


class ImageReplayContracts(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name);self.source=self.root/'capture';self.output=self.root/'replay'
        log=AuditLog(self.source,{'kind':'paired_factorial_capture','synthetic_fixture':True})
        try:collect_episode(FakeScene(),[object(),object()],load_config(ROOT/'configs/default.json'),log)
        finally:log.close()
        self.a=importlib.import_module('visual_lab.image_ablation')
        bridge=DecisionBridge(MockEngine(),allow_text_only=True)
        self.client=SimpleNamespace(health=lambda **kw:bridge.health(),predict=lambda request:(bridge.predict(request),1.0))

    def tearDown(self):self.temp.cleanup()

    def run_replay(self):
        with contextlib.redirect_stdout(io.StringIO()):return self.a.run_image_replay(self.source,self.output,self.client,allow_mock=True)

    def test_42_requests_all_frozen_before_inference_and_14_each_image_count(self):
        predict=self.client.predict;observed=[False]
        def check(request):
            if not observed[0]:
                self.assertEqual(len(list((self.output/'requests').glob('*.json'))),42)
                self.assertEqual(len(json.loads((self.output/'manifest.json').read_text())['planned_order']),42)
                observed[0]=True
            return predict(request)
        self.client.predict=check;result=self.run_replay()
        self.assertTrue(result['complete']);self.assertEqual(result['api_completed'],42);self.assertFalse(result['model_had_control'])
        for n in range(3):self.assertEqual(sum(len(row['image_sha256s'])==n for row in result['decisions']),14)
        self.assertEqual(len(result['cells']),6);self.assertEqual(len(result['conditional_contrasts']),6)
        self.assertTrue(all(cell['baseline_agreement']==7 for cell in result['cells']))
        with self.assertRaises(FileExistsError):self.run_replay()

    def test_real_mode_synthetic_and_missing_capability_reject_before_output(self):
        self.client.predict=Mock()
        with self.assertRaisesRegex(LabError,'synthetic|production'):self.a.run_image_replay(self.source,self.output,self.client)
        self.client.health=lambda **kw:{'is_mock':True,'max_images':2,'supports_text_only_ablation':False}
        with self.assertRaisesRegex(ProtocolError,'text|image'):self.run_replay()
        self.assertFalse(self.output.exists());self.client.predict.assert_not_called()

    def test_api_failure_stops_without_retry_or_placeholder_image(self):
        self.client.predict=Mock(side_effect=LabError('CPU contract failure'))
        result=self.run_replay();self.assertFalse(result['complete']);self.assertEqual(result['api_completed'],0)
        self.assertEqual(self.client.predict.call_count,1);self.assertEqual(len(list((self.output/'requests').glob('*.json'))),42)

    def test_wrong_actual_image_count_marks_incomplete(self):
        predict=self.client.predict
        def corrupt(request):raw,latency=predict(request);raw['_bridge']['image_count']=99;return raw,latency
        self.client.predict=corrupt;result=self.run_replay()
        self.assertFalse(result['complete']);self.assertEqual(result['api_completed'],0);self.assertEqual(len(list((self.output/'responses').glob('*.json'))),1)

    def test_changed_health_source_or_frozen_request_invalidates(self):
        predict=self.client.predict;changed=[False]
        def corrupt(request):
            if not changed[0]:
                changed[0]=True
                for path in (self.output/'requests').glob('*.json'):path.write_text('{}')
            return predict(request)
        self.client.predict=corrupt;result=self.run_replay()
        self.assertFalse(result['complete']);self.assertEqual(result['api_completed'],1);self.assertIn('request',result['error'].lower())


class ImageResponseContracts(unittest.TestCase):
    def test_zero_image_real_flags_require_actual_tokenizer_only_evidence(self):
        a=importlib.import_module('visual_lab.image_ablation')
        raw=MockEngine().predict({'state':{}});raw['_bridge']={'is_mock':False,'image_count':0,'image_sha256s':[],'inference_py_sha256':'CPU-CONTRACT'}
        raw['calibration']={'temperature':1.0}
        health={'max_length':8192,'inference_py_sha256':'CPU-CONTRACT','temperature':1.0}
        with self.assertRaises(ProtocolError):a.verify_image_response([],raw,health)
        raw['_vision_audit']={'encoding_path':'tokenizer_only','input_tokens':100,'normalized_rgb_sha256s':[],'image_grid_thw':[],'vision_token_counts':{'<|image_pad|>':1}}
        with self.assertRaisesRegex(ProtocolError,'vision|visual|token'):a.verify_image_response([],raw,health)
        raw['_vision_audit']['vision_token_counts']={token:0 for token in ['<|vision_start|>','<|vision_end|>','<|image_pad|>','<|video_pad|>']}
        self.assertEqual(a.verify_image_response([],raw,health).action,'pre_grasp')


class ImageReportContracts(unittest.TestCase):
    setUp=ImageReplayContracts.setUp
    tearDown=ImageReplayContracts.tearDown
    run_replay=ImageReplayContracts.run_replay

    def test_html_keeps_zero_image_inputs_empty_and_embeds_42_actual_requests(self):
        self.run_replay();builder=importlib.import_module('tools.make_image_report')
        report=builder.build_image_report(self.source,self.output,self.root/'report.html',allow_mock=True)
        text=report.read_text();data=json.loads(re.search(r'<script id="report-data" type="application/json">(.*?)</script>',text,re.S).group(1))
        self.assertEqual(len(data['requests']),42);self.assertEqual(len(data['assets']),28)
        self.assertEqual(sum(request['image_paths']==[] for request in data['requests'].values()),14)
        self.assertIn('没有向模型发送图片',text);self.assertIn('合成契约测试',text)
        with self.assertRaises(FileExistsError):builder.build_image_report(self.source,self.output,report,allow_mock=True)
        response=next((self.output/'responses').glob('*.json'));response.write_text('{}')
        with self.assertRaisesRegex(LabError,'hash'):builder.build_image_report(self.source,self.output,self.root/'bad.html',allow_mock=True)


if __name__=='__main__':unittest.main()
