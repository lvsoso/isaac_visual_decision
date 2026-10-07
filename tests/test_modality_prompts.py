"""Regression for image-demanding text-only prompts; CPU fixtures, not model quality."""
import contextlib
import copy
import importlib
import io
import json
import re
import unittest
from unittest.mock import Mock

from tests import test_image_ablation as fixtures
from visual_lab.core import ACTIONS, LabError, ProtocolError
from visual_lab.image_ablation import image_request, run_image_replay
from visual_lab.protocol import validate_request

POLICY='modality_aware_v1'
COMMON=('task','previous_action','previous_result','finger_joint_position_rad','goal_guidance','ee_position_description','gripper_command_reference_rad','limitations','ee_reference')


class ModalityRequestTests(unittest.TestCase):
    setUp=fixtures.ImageRequestContracts.setUp
    def request(self,color,count,state=None):
        return image_request(self.pngs,state or self.state,self.views,self.guidance,{'color':color,'views':count},prompt_policy=POLICY)

    def test_text_only_explicitly_declares_no_images_and_no_camera_input(self):
        request=self.request('blue',0)
        self.assertEqual(request['images'],[]);self.assertEqual(request['state']['camera_views'],[])
        self.assertIn('本次没有提供',request['state']['observation'])
        self.assertIn('仅',request['state']['observation'])
        self.assertNotIn('当前同时RGB视图',request['state']['observation'])

    def test_text_only_removes_image_requirements_from_entire_state_questions(self):
        request=self.request('blue',0);text=json.dumps({'state':request['state'],'questions':request['questions']},ensure_ascii=False)
        self.assertNotRegex(text,r'根据当前RGB|使用图像判断夹持|检查红色方块是否位于手指之间|图像中明显|图像顺序与camera_views')
        for criterion in request['questions']['next_stage']['criteria'].values():self.assertNotRegex(criterion,r'图像|视觉|可见|目视')

    def test_text_only_allows_contextual_estimate_without_claiming_holding_or_forcing_abort(self):
        q=self.request('yellow',0)['questions']['next_stage'];text=q['instructions']
        for phrase in ['综合','上一动作','不是强制序列','没有图片本身不是','不能证明夹持']:self.assertIn(phrase,text)
        self.assertNotRegex(text,r'无图就选择abort|没有图片时必须abort|默认已经抓住|假定已夹持')
        self.assertEqual(tuple(q['criteria']),ACTIONS)

    def test_shared_state_numbers_task_and_action_context_are_unchanged(self):
        for color in ['blue','yellow']:
            old=image_request(self.pngs,self.state,self.views,self.guidance,{'color':color,'views':2})
            for count in range(3):
                new=self.request(color,count)
                for key in COMMON:self.assertEqual(new['state'][key],old['state'][key])
                self.assertEqual(len(new['images']),count);validate_request(new,allow_empty_images=True)

    def test_single_image_metadata_matches_first_camera_and_dual_stays_exact(self):
        old=image_request(self.pngs,self.state,self.views,self.guidance,{'color':'blue','views':2})
        single=self.request('blue',1)
        self.assertEqual(single['state']['camera_views'],old['state']['camera_views'][:1])
        self.assertIn('一张',single['state']['observation']);self.assertNotIn('两张',single['state']['observation'])
        self.assertEqual(single['images'],old['images'][:1]);self.assertEqual(single['questions'],old['questions'])
        self.assertEqual(self.request('blue',2),old)

    def test_legacy_policy_remains_reproducible_and_unknown_policy_is_rejected(self):
        old=image_request(self.pngs,self.state,self.views,self.guidance,{'color':'blue','views':0})
        explicit=image_request(self.pngs,self.state,self.views,self.guidance,{'color':'blue','views':0},prompt_policy='legacy_deletion')
        self.assertEqual(explicit,old);self.assertIn('根据当前RGB',old['questions']['next_stage']['instructions'])
        with self.assertRaisesRegex(ProtocolError,'policy'):image_request(self.pngs,self.state,self.views,self.guidance,{'color':'blue','views':0},prompt_policy='guess')

    def test_private_truth_still_cannot_change_any_modality_request(self):
        dirty=copy.deepcopy(self.state);dirty.update(expected_action='release',decision_id=7,holding=True,private_ground_truth={'cube':[99,99,99]})
        for count in range(3):self.assertEqual(self.request('blue',count,dirty),self.request('blue',count))

    def test_adaptation_does_not_mutate_input_and_rejects_wrong_view_count(self):
        mod=importlib.import_module('visual_lab.modality_prompts')
        original=image_request(self.pngs,self.state,self.views,self.guidance,{'color':'blue','views':2});saved=copy.deepcopy(original)
        modified=mod.adapt_modality(original,0)
        self.assertEqual(original,saved);self.assertIsNot(modified,original)
        for count in [-1,3,True]:
            with self.assertRaises(ProtocolError):mod.adapt_modality(original,count)


class ModalityReplayTests(unittest.TestCase):
    setUp=fixtures.ImageReplayContracts.setUp
    tearDown=fixtures.ImageReplayContracts.tearDown
    def run_replay(self):
        with contextlib.redirect_stdout(io.StringIO()):return run_image_replay(self.source,self.output,self.client,prompt_policy=POLICY,allow_mock=True)

    def test_design_and_all_42_requests_are_frozen_and_versioned_before_first_call(self):
        original=self.client.predict;checked=[False]
        def predict(request):
            if not checked[0]:
                manifest=json.loads((self.output/'manifest.json').read_text());self.assertEqual(manifest['prompt_policy'],POLICY)
                self.assertEqual(len(list((self.output/'requests').glob('*.json'))),42)
                for path in (self.output/'requests').glob('*_images_0_*.json'):
                    req=json.loads(path.read_text());self.assertEqual(req['state']['camera_views'],[])
                    self.assertNotIn('根据当前RGB',req['questions']['next_stage']['instructions'])
                checked[0]=True
            return original(request)
        self.client.predict=predict;result=self.run_replay()
        self.assertTrue(result['complete']);self.assertEqual(result['prompt_policy'],POLICY)
        self.assertEqual(result['api_completed'],42);self.assertFalse(result['model_had_control'])
        self.assertEqual(len(result['conditional_contrasts']),6)
        self.assertTrue(all(cell['variant']==POLICY for cell in result['cells']))
        self.assertIn('prompt',result['scope'].lower())

    def test_unknown_policy_or_busy_service_is_rejected_without_any_call(self):
        self.client.predict=Mock()
        with self.assertRaisesRegex(ProtocolError,'policy'):run_image_replay(self.source,self.output,self.client,prompt_policy='guess',allow_mock=True)
        self.assertFalse(self.output.exists());self.client.predict.assert_not_called()

    def test_failures_still_stop_without_retries_or_fake_response(self):
        self.client.predict=Mock(side_effect=ProtocolError('fixture failure'))
        result=self.run_replay();self.assertFalse(result['complete']);self.assertEqual(result['api_completed'],0)
        self.assertEqual(self.client.predict.call_count,1)

    def legacy(self):
        target=self.root/'legacy'
        with contextlib.redirect_stdout(io.StringIO()):run_image_replay(self.source,target,self.client,allow_mock=True)
        return target

    def test_legacy_same_zero_image_reference_is_saved_separately(self):
        legacy=self.legacy()
        with contextlib.redirect_stdout(io.StringIO()):result=run_image_replay(self.source,self.output,self.client,prompt_policy=POLICY,legacy_reference=legacy,allow_mock=True)
        self.assertTrue(result['complete']);self.assertEqual(len(result['legacy_text_contrasts']),2)
        manifest=json.loads((self.output/'manifest.json').read_text())
        self.assertEqual(len(manifest['legacy_text_reference']['text_rows']),14)
        self.assertTrue(all(row['image_count']==0 for row in manifest['legacy_text_reference']['text_rows']))

    def test_legacy_artifact_tamper_rejects_before_new_model_calls(self):
        legacy=self.legacy();next((legacy/'requests').glob('*_images_0_*.json')).write_text('{}')
        self.client.predict=Mock()
        with self.assertRaisesRegex(LabError,'hash'):run_image_replay(self.source,self.output,self.client,prompt_policy=POLICY,legacy_reference=legacy,allow_mock=True)
        self.client.predict.assert_not_called();self.assertFalse(self.output.exists())


class ModalityReportTests(unittest.TestCase):
    setUp=ModalityReplayTests.setUp
    tearDown=ModalityReplayTests.tearDown
    run_replay=ModalityReplayTests.run_replay

    def test_html_identifies_matching_prompts_and_preserves_actual_zero_image_inputs(self):
        self.run_replay();builder=importlib.import_module('tools.make_image_report')
        report=builder.build_image_report(self.source,self.output,self.root/'report.html',allow_mock=True)
        text=report.read_text();data=json.loads(re.search(r'<script id="report-data" type="application/json">(.*?)</script>',text,re.S).group(1))
        self.assertEqual(data['manifest']['prompt_policy'],POLICY);self.assertEqual(len(data['requests']),42)
        self.assertEqual(sum(r['image_paths']==[] for r in data['requests'].values()),14)
        for r in data['requests'].values():
            if not r['image_paths']:self.assertEqual(r['state']['camera_views'],[]);self.assertNotIn('根据当前RGB',r['questions']['next_stage']['instructions'])
        self.assertIn('提示适配',text);self.assertIn('不是纯图片',text);self.assertIn('没有向模型发送图片',text)

    def test_report_rejects_silent_policy_relabeling(self):
        self.run_replay();builder=importlib.import_module('tools.make_image_report')
        path=self.output/'manifest.json';manifest=json.loads(path.read_text());manifest['prompt_policy']='legacy_deletion';path.write_text(json.dumps(manifest))
        with self.assertRaisesRegex(Exception,'policy|design|construction'):builder.build_image_report(self.source,self.output,self.root/'wrong.html',allow_mock=True)

    def test_report_embeds_legacy_text_inputs_with_mismatch_warning(self):
        legacy=ModalityReplayTests.legacy(self)
        with contextlib.redirect_stdout(io.StringIO()):run_image_replay(self.source,self.output,self.client,prompt_policy=POLICY,legacy_reference=legacy,allow_mock=True)
        builder=importlib.import_module('tools.make_image_report');report=builder.build_image_report(self.source,self.output,self.root/'report.html',allow_mock=True)
        text=report.read_text();data=json.loads(re.search(r'<script id="report-data" type="application/json">(.*?)</script>',text,re.S).group(1))
        info=data['manifest']['legacy_text_reference']
        self.assertEqual(len(info['requests']),14);self.assertEqual(len(info['responses']),14)
        self.assertTrue(all(req['images']==[] for req in info['requests'].values()))
        self.assertIn('提示失配',text);self.assertIn('旧无图',text)


if __name__=='__main__':unittest.main()
