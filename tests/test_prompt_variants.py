"""User-approved prompt contrasts; synthetic CPU contracts, never model quality."""
import base64
import contextlib
import copy
import hashlib
import importlib
import io
import json
import re
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

from tests.test_factorial import FakeScene, ROOT
from visual_lab.audit import AuditLog, sha256_file
from visual_lab.core import ACTIONS, LabError, ProtocolError, load_config, model_state
from visual_lab.factorial import collect_episode, factor_request, goal_guidance, view_metadata
from visual_lab.png import encode_rgb_bytes
from visual_lab.protocol import validate_request
from visual_lab.server import DecisionBridge, MockEngine


class PromptRequestTests(unittest.TestCase):
    def setUp(self):
        self.p = importlib.import_module('visual_lab.prompt_variants')
        self.state = model_state({'ee_world_position_m': [.4, .2, .3], 'finger_joint_position_rad': .5}, 'transport', 'reached')
        self.views = view_metadata(load_config(ROOT/'configs/default.json'))
        self.guidance = goal_guidance([.5, .5, .05], [.5, .5, .235], [.4993219725, .4819015121, .5481045962], 'tool0')
        self.pngs = [encode_rgb_bytes(2, 2, bytes(rgb*4)) for rgb in ([20, 30, 150], [200, 170, 20])]

    def cell(self, variant, color='blue'):
        return next(cell for cell in self.p.prompt_cells() if cell['variant'] == variant and cell['color'] == color)

    def request(self, variant, color='blue', state=None, guidance=None):
        return self.p.prompt_request(self.pngs, state or self.state, self.views, guidance or self.guidance, self.cell(variant, color))

    def test_twelve_unique_cells_in_three_frozen_rounds(self):
        cells = self.p.prompt_cells()
        self.assertEqual(len(cells), 12)
        self.assertEqual(len({cell['id'] for cell in cells}), 12)
        self.assertEqual({cell['variant'] for cell in cells}, {'en_neutral_raw', 'zh_neutral_raw', 'en_named_raw', 'zh_named_raw', 'en_named_relative', 'zh_named_relative'})
        self.assertTrue(all(cell['views'] == 2 for cell in cells))

    def test_english_neutral_matches_previous_factorial_request_exactly(self):
        for color in ['blue', 'yellow']:
            expected = factor_request(self.pngs, self.state, self.views, self.guidance, {'color': color, 'coordinates': True, 'views': 2})
            self.assertEqual(self.request('en_neutral_raw', color), expected)

    def test_translation_preserves_every_numeric_value_machine_id_and_png(self):
        def numbers(value):
            if isinstance(value, dict): return {key: numbers(item) for key, item in value.items() if not isinstance(item, str)}
            if isinstance(value, list): return [numbers(item) for item in value]
            return value
        for form in ['neutral_raw', 'named_raw']:
            en, zh = self.request('en_'+form), self.request('zh_'+form)
            self.assertEqual(numbers(en['state']), numbers(zh['state']))
            self.assertEqual(en['images'], zh['images'])
            for key in ['previous_action', 'previous_result']:
                self.assertEqual(en['state'][key], zh['state'][key])
            self.assertEqual(zh['state']['goal_guidance']['controller_tool_frame'], 'tool0')
            self.assertIn('红色方块', zh['state']['task'])
            self.assertTrue(all(re.search('[\u4e00-\u9fff]', text) for text in zh['questions']['next_stage']['criteria'].values()))
            self.assertNotIn('world coordinates', json.dumps(zh['state'], ensure_ascii=False))

    def test_color_identification_only_changes_two_target_sentences(self):
        for language in ['en', 'zh']:
            for color, word in [('blue', '蓝色'), ('yellow', '黄色')]:
                neutral, named = self.request(language+'_neutral_raw', color), self.request(language+'_named_raw', color)
                self.assertNotEqual(neutral['state']['task'], named['state']['task'])
                self.assertNotEqual(neutral['questions']['next_stage']['instructions'], named['questions']['next_stage']['instructions'])
                if language == 'zh': self.assertIn(word, named['state']['task'])
                else: self.assertIn(color, named['state']['task'])
                named['state']['task'] = neutral['state']['task']
                named['questions']['next_stage']['instructions'] = neutral['questions']['next_stage']['instructions']
                self.assertEqual(named, neutral)

    def test_relative_format_preserves_question_and_uses_tool_not_cube(self):
        for language in ['en', 'zh']:
            raw, relative = self.request(language+'_named_raw'), self.request(language+'_named_relative')
            self.assertEqual(raw['questions'], relative['questions'])
            self.assertEqual(raw['images'], relative['images'])
            text = json.dumps(relative['state'], ensure_ascii=False)
            self.assertIn('31.3', text)
            self.assertIn('1.8', text)
            self.assertNotRegex(text, r'\d+\.\d{7,}')
            self.assertNotIn('ee_world_position_m', relative['state'])
            self.assertIn('tool0', text)
            self.assertNotIn('holding": true', text)

    def test_signed_height_negative_and_near_zero_do_not_become_action_labels(self):
        for z in [.1, .23499, .235, .55]:
            guidance = goal_guidance([.5, .5, 0], [.5, .5, .235], [.5, .5, z], 'tool0')
            req = self.request('zh_named_relative', guidance=guidance)
            text = json.dumps(req['state']['goal_guidance'], ensure_ascii=False)
            self.assertNotRegex(text, '已对齐|已抓住|应该下降|应释放|下一步|选择lower|选择release')
            self.assertIn('带符号', text)
            if z == .1: self.assertIn('-13.5', text)
            if abs(z-.235) < .0001: self.assertIn('0.0', text)

    def test_whitelist_blocks_private_truth_and_labels_in_all_forms(self):
        dirty = copy.deepcopy(self.state)
        dirty.update(expected_action='release', decision_id=7, private_ground_truth={'cube': 'SECRET'}, holding=True)
        dirty_guidance = copy.deepcopy(self.guidance)
        dirty_guidance.update(cube_world_position_m=[99,99,99], expected_action='release')
        for cell in self.p.prompt_cells():
            clean = self.request(cell['variant'], cell['color'])
            self.assertEqual(clean, self.request(cell['variant'], cell['color'], dirty, dirty_guidance))

    def test_every_form_keeps_all_candidates_and_does_not_mutate_sources(self):
        before = copy.deepcopy((self.state, self.guidance, self.views))
        for cell in self.p.prompt_cells():
            request = self.request(cell['variant'], cell['color'])
            validate_request(request)
            self.assertEqual(tuple(request['questions']['next_stage']['criteria']), ACTIONS)
            self.assertEqual([base64.b64decode(image['data']) for image in request['images']], self.pngs)
        self.assertEqual((self.state, self.guidance, self.views), before)

    def test_bad_variant_or_nonfinite_geometry_refuses_construction(self):
        bad = self.cell('en_named_raw'); bad['variant'] = 'invented'
        with self.assertRaises(ProtocolError): self.p.prompt_request(self.pngs, self.state, self.views, self.guidance, bad)
        dirty = copy.deepcopy(self.guidance); dirty['tool_height_above_placement_m'] = float('nan')
        with self.assertRaises(ProtocolError): self.request('zh_named_relative', guidance=dirty)


class PromptReplayTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.source, self.output = self.root/'capture', self.root/'replay'
        log = AuditLog(self.source, {'kind': 'paired_factorial_capture', 'synthetic_fixture': True})
        try: collect_episode(FakeScene(), [object(), object()], load_config(ROOT/'configs/default.json'), log)
        finally: log.close()
        self.p = importlib.import_module('visual_lab.prompt_variants')
        bridge = DecisionBridge(MockEngine())
        self.client = SimpleNamespace(health=lambda **kw: bridge.health(), predict=lambda request: (bridge.predict(request), 1.0))

    def tearDown(self):
        self.temp.cleanup()

    def run_replay(self, client=None):
        with contextlib.redirect_stdout(io.StringIO()):
            return self.p.run_prompt_replay(self.source, self.output, client or self.client, allow_mock=True)

    def test_all_84_inputs_are_saved_before_first_inference_and_never_modified(self):
        predict = self.client.predict
        before = {}
        def inspect_first(request):
            if not before:
                files = list((self.output/'requests').glob('*.json'))
                self.assertEqual(len(files), 84)
                manifest = json.loads((self.output/'manifest.json').read_text())
                self.assertEqual(len(manifest['planned_order']), 84)
                before.update({path.name:sha256_file(path) for path in files})
            return predict(request)
        self.client.predict = inspect_first
        result = self.run_replay()
        self.assertTrue(result['complete'])
        self.assertEqual(result['api_completed'], 84)
        self.assertFalse(result['model_had_control'])
        self.assertTrue(result['mock_backend'])
        self.assertEqual(before, {path.name:sha256_file(path) for path in (self.output/'requests').glob('*.json')})
        self.assertEqual(len(result['cells']), 12)
        self.assertEqual(len(result['conditional_contrasts']), 14)

    def test_existing_directory_is_preserved(self):
        self.output.mkdir(); (self.output/'user.txt').write_text('keep')
        with self.assertRaises(FileExistsError): self.run_replay()
        self.assertEqual((self.output/'user.txt').read_text(), 'keep')

    def test_failure_stops_once_with_original_response_and_incomplete_summary(self):
        self.client.predict = Mock(side_effect=LabError('contract API failure'))
        result = self.run_replay()
        self.assertFalse(result['complete'])
        self.assertEqual(result['api_completed'], 0)
        self.assertEqual(self.client.predict.call_count, 1)
        self.assertIn('API failure', result['error'])
        self.assertEqual(len(list((self.output/'requests').glob('*.json'))), 84)

    def test_synthetic_invalidated_and_single_view_are_rejected_before_inference(self):
        self.client.predict = Mock()
        with self.assertRaisesRegex(LabError, 'synthetic|production'):
            self.p.run_prompt_replay(self.source, self.output, self.client)
        (self.source/'INVALIDATED.json').write_text('{}')
        with self.assertRaisesRegex(LabError, 'invalidated'): self.run_replay()
        (self.source/'INVALIDATED.json').unlink()
        self.client.health = lambda **kw: {'is_mock': True, 'max_images': 1}
        with self.assertRaises(ProtocolError): self.run_replay()
        self.client.predict.assert_not_called()
        self.assertFalse(self.output.exists())

    def test_busy_service_refused_without_creating_run(self):
        self.client.health = lambda **kw: {'is_mock': True, 'max_images': 2, 'busy': True}
        with self.assertRaisesRegex(ProtocolError, 'busy'): self.run_replay()
        self.assertFalse(self.output.exists())

    def test_ordered_image_audit_failure_is_not_counted_as_completed(self):
        predict = self.client.predict
        def corrupt(request):
            raw, latency = predict(request); raw['_bridge']['image_sha256s'].reverse()
            return raw, latency
        self.client.predict = corrupt
        result = self.run_replay()
        self.assertFalse(result['complete'])
        self.assertEqual(result['api_completed'], 0)
        self.assertEqual(len(list((self.output/'responses').glob('*.json'))), 1)
        self.assertIn('image', result['error'].lower())

    def test_source_changes_during_replay_invalidate_completed_requests(self):
        predict = self.client.predict
        changed = [False]
        def alter(request):
            if not changed[0]:
                changed[0] = True
                with (self.source/'snapshots.json').open('a') as stream: stream.write('\n')
            return predict(request)
        self.client.predict = alter
        result = self.run_replay()
        self.assertFalse(result['complete'])
        self.assertIn('source', result['error'].lower())

    def test_changed_service_provenance_is_incomplete_not_silently_accepted(self):
        health = self.client.health; calls=[0]
        def altered(**kw):
            calls[0]+=1; value=health(**kw)
            if calls[0]>1: value['temperature'] = 9.0
            return value
        self.client.health = altered
        result = self.run_replay()
        self.assertFalse(result['complete'])
        self.assertIn('provenance', result['error'].lower())

    def test_request_tampering_is_detected_before_it_is_sent(self):
        predict = self.client.predict; altered=[False]
        def tamper(request):
            if not altered[0]:
                altered[0]=True
                for path in (self.output/'requests').glob('*.json'): path.write_text('{}')
            return predict(request)
        self.client.predict = tamper
        result = self.run_replay()
        self.assertFalse(result['complete'])
        self.assertEqual(result['api_completed'], 1)
        self.assertIn('request', result['error'].lower())

    def test_exact_probability_tie_never_counts_reference_as_chosen(self):
        result = self.run_replay()
        rows = result['decisions']
        row = next(row for row in rows if row['expected_action']=='release')
        row['proposed_action']='lift'; row['probabilities']={action: .5 if action in {'lift','release'} else 0.0 for action in ACTIONS}
        summary = self.p.summarize_prompts(rows)
        cell = next(cell for cell in summary['cells'] if cell['id']==row['cell'])
        self.assertEqual(cell['final_two_agreement'], 1)
        self.assertEqual(cell['baseline_agreement'], 6)


class PromptReportTests(unittest.TestCase):
    setUp = PromptReplayTests.setUp
    tearDown = PromptReplayTests.tearDown
    run_replay = PromptReplayTests.run_replay
    def build_report(self):
        self.run_replay()
        self.builder = importlib.import_module('tools.make_prompt_report')
        return self.builder.build_prompt_report(self.source, self.output, self.root/'report.html', allow_mock=True)

    def test_html_embeds_28_original_pngs_all_84_actual_inputs_and_warning(self):
        report = self.build_report()
        text = report.read_text()
        data = json.loads(re.search(r'<script id="report-data" type="application/json">(.*?)</script>',text,re.S).group(1))
        self.assertEqual(len(data['assets']),28)
        self.assertEqual(len(data['requests']),84)
        self.assertEqual(len(data['responses']),84)
        self.assertIn('合成契约测试',text)
        self.assertNotRegex(text,r'<(?:script|link)[^>]+(?:src|href)=["\']https?://')

    def test_report_rejects_tamper_incomplete_mock_as_real_and_overwrite(self):
        report = self.build_report()
        with self.assertRaises(FileExistsError): self.builder.build_prompt_report(self.source,self.output,report,allow_mock=True)
        with self.assertRaisesRegex(LabError,'mock|synthetic'): self.builder.build_prompt_report(self.source,self.output,self.root/'real.html')
        response = next((self.output/'responses').glob('*.json')); response.write_text('{}')
        with self.assertRaisesRegex(LabError,'hash'): self.builder.build_prompt_report(self.source,self.output,self.root/'bad.html',allow_mock=True)
        summary_path=self.output/'summary.json'; summary=json.loads(summary_path.read_text()); summary['complete']=False; summary_path.write_text(json.dumps(summary))
        with self.assertRaisesRegex(LabError,'complete'): self.builder.build_prompt_report(self.source,self.output,self.root/'partial.html',allow_mock=True)

    def test_safe_embedded_metadata_cannot_close_script(self):
        self.run_replay()
        builder=importlib.import_module('tools.make_prompt_report')
        path=self.output/'manifest.json';manifest=json.loads(path.read_text());manifest['model_health']['checkpoint']='</script><script>alert(1)</script>';path.write_text(json.dumps(manifest))
        output=builder.build_prompt_report(self.source,self.output,self.root/'safe.html',allow_mock=True)
        self.assertNotIn('</script><script>alert',output.read_text())


if __name__ == '__main__':
    unittest.main()
