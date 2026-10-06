"""CPU provenance/equal-state checks; fixtures never prove GPU rendering."""
import copy
import importlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock

from tests.test_factorial import FakeScene, ROOT
from visual_lab.audit import AuditLog
from visual_lab.core import LabError, load_config


class StaticPairTests(unittest.TestCase):
    def setUp(self):
        self.f = importlib.import_module('visual_lab.factorial')
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.config = load_config(ROOT/'configs/default.json')

    def tearDown(self):
        self.temp.cleanup()

    def collect(self, color):
        scene = FakeScene()
        scene.colors = [self.f.GOAL_COLORS[color]]
        scene.set_goal_color = Mock(side_effect=AssertionError('No live recoloring is permitted'))
        directory = self.root/color
        manifest = {'kind': 'static_color_capture', 'synthetic_fixture': True, 'static_goal_color': color,
                    'config': self.config, 'source_sha256': {'fixture': 'CPU'}, 'cameras': self.f.camera_configs(self.config)}
        log = AuditLog(directory, manifest)
        try:
            result = self.f.collect_episode(scene, [object(), object()], self.config, log, static_color=color)
        finally:
            log.close()
        self.assertTrue(result['complete'])
        scene.set_goal_color.assert_not_called()
        return directory

    def modify_snapshot(self, directory, modify):
        path = directory/'snapshots.json'
        value = json.loads(path.read_text())
        modify(value)
        path.write_text(json.dumps(value))

    def test_static_collection_has_no_recoloring(self):
        source = self.collect('yellow')
        bundle = json.loads((source/'snapshots.json').read_text())
        self.assertEqual(len(list((source/'images').glob('*.png'))), 14)
        self.assertTrue(all(list(record['images']) == ['yellow'] for record in bundle['records']))
        self.assertTrue(all('private_frozen_state' in record for record in bundle['records']))

    def test_pairing_matches_all_seven_physical_states_and_preserves_pixels(self):
        blue, yellow = self.collect('blue'), self.collect('yellow')
        output = self.root/'paired'
        result = self.f.pair_static_captures(blue, yellow, output, allow_mock=True)
        self.assertTrue(result['complete'])
        self.assertTrue(result['all_physical_states_exactly_equal'])
        self.assertEqual(len(list((output/'images').glob('*.png'))), 28)
        bundle = self.f.load_snapshots(output)
        for record in bundle['records']:
            for color, source in [('blue', blue), ('yellow', yellow)]:
                for asset in record['images'][color]:
                    self.assertEqual((output/asset['path']).read_bytes(), (source/asset['path']).read_bytes())
        with self.assertRaises(FileExistsError):
            self.f.pair_static_captures(blue, yellow, output, allow_mock=True)

    def test_any_physical_state_difference_is_rejected(self):
        blue, yellow = self.collect('blue'), self.collect('yellow')
        self.modify_snapshot(yellow, lambda value: value['records'][4]['private_frozen_state'].update(physics_updates=99))
        with self.assertRaisesRegex(LabError, 'state|trajectory'):
            self.f.pair_static_captures(blue, yellow, self.root/'paired', allow_mock=True)

    def test_proprioception_difference_is_rejected(self):
        blue, yellow = self.collect('blue'), self.collect('yellow')
        self.modify_snapshot(yellow, lambda value: value['records'][0]['model_state'].update(finger_joint_position_rad=.2))
        with self.assertRaisesRegex(LabError, 'state|trajectory'):
            self.f.pair_static_captures(blue, yellow, self.root/'paired', allow_mock=True)

    def test_source_configuration_difference_is_rejected(self):
        blue, yellow = self.collect('blue'), self.collect('yellow')
        path = yellow/'manifest.json'
        value = json.loads(path.read_text())
        value['config']['cube_position_m'][0] += .01
        path.write_text(json.dumps(value))
        with self.assertRaisesRegex(LabError, 'configuration'):
            self.f.pair_static_captures(blue, yellow, self.root/'paired', allow_mock=True)

    def test_real_pairing_rejects_synthetic_sources(self):
        blue, yellow = self.collect('blue'), self.collect('yellow')
        with self.assertRaisesRegex(LabError, 'synthetic'):
            self.f.pair_static_captures(blue, yellow, self.root/'paired')

    def test_invalidated_static_source_is_rejected(self):
        blue, yellow = self.collect('blue'), self.collect('yellow')
        (yellow/'INVALIDATED.json').write_text('{}')
        with self.assertRaisesRegex(LabError, 'invalidated'):
            self.f.pair_static_captures(blue, yellow, self.root/'paired', allow_mock=True)

    def test_color_validation_fails_when_treatments_have_identical_pixels(self):
        from visual_lab.png import encode_rgb_bytes
        png = encode_rgb_bytes(2, 2, bytes([20, 20, 100]*4))
        with self.assertRaisesRegex(LabError, 'color'):
            self.f.check_color_treatment(png, png, 1, allow_mock=True)


if __name__ == '__main__':
    unittest.main()
