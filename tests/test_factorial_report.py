"""Offline report contract/security tests; no GPU/model-quality evidence."""
import contextlib
import importlib
import io
import json
import re
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from tests.test_factorial import FakeScene, ROOT
from visual_lab.audit import AuditLog
from visual_lab.core import LabError, load_config
from visual_lab.factorial import collect_episode, run_replay
from visual_lab.server import DecisionBridge, MockEngine


class FactorialReportTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.source = self.root/'capture'
        self.replay = self.root/'replay'
        self.output = self.root/'report.html'
        log = AuditLog(self.source, {'kind': 'paired_factorial_capture', 'synthetic_fixture': True})
        try:
            collect_episode(FakeScene(), [object(), object()], load_config(ROOT/'configs/default.json'), log)
        finally:
            log.close()
        bridge = DecisionBridge(MockEngine())
        client = SimpleNamespace(health=lambda **kw: bridge.health(), predict=lambda request: (bridge.predict(request), 1.0))
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertTrue(run_replay(self.source, self.replay, client, allow_mock=True)['complete'])
        self.builder = importlib.import_module('tools.make_factorial_report')

    def tearDown(self):
        self.temp.cleanup()

    def build(self):
        return self.builder.build_factorial_report(self.source, self.replay, self.output, allow_mock=True)

    def payload(self):
        text = self.output.read_text()
        match = re.search(r'<script id="report-data" type="application/json">(.*?)</script>', text, re.S)
        self.assertIsNotNone(match)
        return json.loads(match.group(1))

    def test_self_contained_all_images_and_probabilities_with_mock_warning(self):
        self.build()
        text = self.output.read_text()
        data = self.payload()
        self.assertEqual(len(data['summary']['decisions']), 56)
        self.assertEqual(len(data['assets']), 28)
        self.assertEqual(len(data['requests']), 56)
        self.assertEqual(len(data['responses']), 56)
        self.assertTrue(all(asset['data'].startswith('data:image/png;base64,') for asset in data['assets'].values()))
        self.assertIn('合成契约测试', text)
        self.assertNotRegex(text, r'<(?:script|link)[^>]+(?:src|href)=["\']https?://')

    def test_existing_report_is_never_overwritten(self):
        self.output.write_text('user content')
        with self.assertRaises(FileExistsError):
            self.build()
        self.assertEqual(self.output.read_text(), 'user content')

    def test_real_mode_cannot_label_mock_results_as_real(self):
        with self.assertRaisesRegex(LabError, 'mock|synthetic'):
            self.builder.build_factorial_report(self.source, self.replay, self.output)
        self.assertFalse(self.output.exists())

    def test_hostile_metadata_does_not_break_out_of_data_script(self):
        path = self.replay/'manifest.json'
        manifest = json.loads(path.read_text())
        manifest['model_health']['checkpoint'] = '</script><script>alert("unsafe")</script>'
        path.write_text(json.dumps(manifest))
        self.build()
        self.assertNotIn('</script><script>alert', self.output.read_text())
        self.assertEqual(self.payload()['manifest']['model_health']['checkpoint'], manifest['model_health']['checkpoint'])

    def test_tampered_image_or_response_refuses_report(self):
        response = next((self.replay/'responses').glob('*.json'))
        response.write_text('{}')
        with self.assertRaisesRegex(LabError, 'hash'):
            self.build()
        self.assertFalse(self.output.exists())

    def test_incomplete_experiment_cannot_be_reported_as_complete(self):
        path = self.replay/'summary.json'
        summary = json.loads(path.read_text())
        summary['complete'] = False
        path.write_text(json.dumps(summary))
        with self.assertRaisesRegex(LabError, 'complete'):
            self.build()
        self.assertFalse(self.output.exists())


if __name__ == '__main__':
    unittest.main()
