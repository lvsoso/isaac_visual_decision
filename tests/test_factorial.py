"""Synthetic paired-factor tests, never real-model or GPU evidence."""
import base64
import copy
import importlib
import json
import math
import unittest
import tempfile
import threading
from types import SimpleNamespace
from unittest.mock import Mock, patch
from pathlib import Path

from visual_lab.core import ACTIONS, load_config, model_state
from visual_lab.png import encode_rgb_bytes
from visual_lab.protocol import validate_request
from visual_lab.audit import AuditLog
from visual_lab.core import LabError, ProtocolError

ROOT = Path(__file__).resolve().parents[1]


class FactorialTests(unittest.TestCase):
    def setUp(self):
        self.f = importlib.import_module('visual_lab.factorial')
        self.config = load_config(ROOT/'configs/default.json')
        self.views = self.f.view_metadata(self.config)
        self.state = model_state({'ee_world_position_m': [.4, .2, .3], 'finger_joint_position_rad': .5}, 'lift', 'reached')
        self.guidance = self.f.goal_guidance([.5, .5, .05], [.5, .5, .235], [.5, .2, .4], 'tool0')
        self.pngs = {color: [encode_rgb_bytes(2, 2, bytes(rgb*4)) for rgb in ([20, 20, 90], [30, 30, 80])]
                     for color in ['blue', 'yellow']}

    def request(self, cell, state=None):
        return self.f.factor_request(self.pngs[cell['color']], state or self.state, self.views, self.guidance, cell)

    def test_eight_unique_combinations(self):
        cells = self.f.factor_cells()
        self.assertEqual(len(cells), 8)
        self.assertEqual(len({cell['id'] for cell in cells}), 8)
        self.assertEqual(sum(cell['views'] == 2 for cell in cells), 4)
        self.assertEqual(sum(cell['coordinates'] for cell in cells), 4)

    def test_color_does_not_change_text_or_state(self):
        cells = self.f.factor_cells()
        a, b = self.request(cells[0]), self.request(cells[4])
        self.assertEqual(a, b)  # identical synthetic pixels make entire requests equal
        self.assertNotIn('blue', json.dumps(a).lower())
        self.assertNotIn('yellow', json.dumps(a).lower())

    def test_coordinates_only_add_approved_block(self):
        a, b = self.request(self.f.factor_cells()[0]), self.request(self.f.factor_cells()[2])
        self.assertNotIn('goal_guidance', a['state'])
        self.assertEqual(b['state'].pop('goal_guidance'), self.guidance)
        self.assertEqual(a, b)

    def test_second_view_preserves_first_image_and_proprioception(self):
        a, b = self.request(self.f.factor_cells()[0]), self.request(self.f.factor_cells()[1])
        self.assertEqual(a['images'][0], b['images'][0])
        self.assertEqual(a['state']['camera_views'], b['state']['camera_views'][:1])
        b['images'].pop(); b['state']['camera_views'].pop()
        self.assertEqual(a, b)

    def test_whitelist_discards_truth_even_with_coordinates(self):
        dirty = copy.deepcopy(self.state)
        dirty.update(cube_world_position_m=[99, 99, 99], private_ground_truth={'cube': 'secret'}, decision_id=7,
                     expected_action='release', holding=True, target_world_position_m=[8, 8, 8])
        for cell in self.f.factor_cells():
            self.assertEqual(self.request(cell), self.request(cell, dirty))

    def test_goal_ground_and_lower_tool_target_are_not_confused(self):
        g = self.guidance
        self.assertEqual(g['goal_center_on_ground_world_m'], [.5, .5, 0.0])
        self.assertEqual(g['placement_tool_target_world_m'], [.5, .5, .235])
        self.assertEqual(g['tool_to_placement_delta_m'], [0.0, .3, -.165])
        self.assertAlmostEqual(g['tool_to_goal_horizontal_distance_m'], .3)
        self.assertAlmostEqual(g['tool_height_above_placement_m'], .165)

    def test_view_angles_are_defined_from_world_direction(self):
        for view in self.views:
            direction = view['view_direction_world']
            self.assertAlmostEqual(sum(x*x for x in direction), 1)
            self.assertAlmostEqual(view['view_azimuth_deg'], math.degrees(math.atan2(direction[1], direction[0])), places=4)
            self.assertLess(view['view_elevation_deg'], 0)

    def test_all_candidates_and_valid_image_contract(self):
        before = copy.deepcopy(self.state)
        for cell in self.f.factor_cells():
            request = self.request(cell)
            validate_request(request)
            self.assertEqual(tuple(request['questions']['next_stage']['criteria']), ACTIONS)
            self.assertEqual(base64.b64decode(request['images'][0]['data']), self.pngs[cell['color']][0])
        self.assertEqual(self.state, before)


class FakeScene:
    """Explicit CPU fixture, no Isaac contact/rendering."""
    def __init__(self):
        self.frames = 0
        self.timeline = SimpleNamespace(pause=Mock())
        self.scenario = SimpleNamespace(_tool_frame='tool0')
        self.colors = []
        self.actions = []
        self.fail_capture = False
        self.fail_action = None

    def placement_tool_target(self):
        return [.5, .5, .235]

    def proprioception(self):
        return {'ee_world_position_m': [.5, .2, .4], 'finger_joint_position_rad': .5}

    def _controller_tool_world_position(self):
        return [.5, .2, .4]

    def frozen_state(self):
        return {'simulation_time': self.frames/60, 'physics_updates': self.frames}

    def private_truth(self):
        return {'cube_world_position_m': [.5, .5, .025]}

    def set_goal_color(self, rgb):
        self.colors.append(list(rgb))

    def capture_views(self, cameras):
        if self.fail_capture:
            raise LabError('synthetic capture failure')
        color = [20, 30, 150] if self.colors[-1][0] < .5 else [220, 190, 20]
        return [encode_rgb_bytes(2, 2, bytes(color*4)), encode_rgb_bytes(2, 2, bytes(list(reversed(color))*4))]

    def execute(self, action):
        self.actions.append(action)
        self.frames += 1
        return {'action': action, 'status': 'timeout' if action == self.fail_action else 'reached',
                'target_world_position_m': self.placement_tool_target()}

    def settle(self):
        pass


class CollectionReplayTests(unittest.TestCase):
    def setUp(self):
        self.f = importlib.import_module('visual_lab.factorial')
        self.config = load_config(ROOT/'configs/default.json')
        self.temp = tempfile.TemporaryDirectory()
        self.source = Path(self.temp.name)/'source'
        self.scene = FakeScene()

    def tearDown(self):
        self.temp.cleanup()

    def collect(self):
        log = AuditLog(self.source, {'synthetic_fixture': True})
        try:
            return self.f.collect_episode(self.scene, [object(), object()], self.config, log)
        finally:
            log.close()

    def test_collection_has_one_trajectory_and_four_paired_images_per_state(self):
        result = self.collect()
        self.assertTrue(result['complete'])
        self.assertEqual(self.scene.actions, list(ACTIONS[:-1])+['retract'])
        self.assertFalse(result['model_had_control'])
        bundle = self.f.load_snapshots(self.source)
        self.assertEqual(len(list((self.source/'images').glob('*.png'))), 28)
        self.assertEqual(len(bundle['records']), 7)
        self.assertTrue(all(record['frozen_physics_verified'] for record in bundle['records']))
        self.assertEqual(len({tuple(r['goal_guidance']['placement_tool_target_world_m']) for r in bundle['records']}), 1)

    def test_color_is_restored_on_capture_failure(self):
        self.scene.fail_capture = True
        with self.assertRaisesRegex(LabError, 'capture failure'):
            self.f.capture_pairs(self.scene, [object(), object()])
        self.assertEqual(self.scene.colors[-1], self.f.GOAL_COLORS['blue'])
        self.scene.timeline.pause.assert_called()

    def test_changed_physics_in_quartet_is_rejected(self):
        snapshots = iter([{'physics_updates': 0}, {'physics_updates': 1}])
        self.scene.frozen_state = lambda: next(snapshots)
        with self.assertRaisesRegex(LabError, 'frozen'):
            self.f.capture_pairs(self.scene, [object(), object()], reverse=True)
        self.assertEqual(self.scene.colors[-1], self.f.GOAL_COLORS['blue'])

    def test_timeout_is_incomplete_and_cannot_be_replayed(self):
        self.scene.fail_action = 'approach'
        result = self.collect()
        self.assertFalse(result['complete'])
        self.assertEqual(self.scene.actions, ['pre_grasp', 'approach'])
        with self.assertRaises(LabError):
            self.f.load_snapshots(self.source)

    def test_capture_failure_writes_incomplete_summary(self):
        self.scene.fail_capture = True
        result = self.collect()
        self.assertIn('capture failure', result['error'])
        self.assertFalse(result['complete'])
        self.assertEqual(self.scene.actions, [])

    def test_wrong_lower_reference_fails(self):
        original = self.scene.execute
        def execute(action):
            result = original(action)
            if action == 'lower':
                result['target_world_position_m'] = [9, 9, 9]
            return result
        self.scene.execute = execute
        result = self.collect()
        self.assertIn('differs', result['error'])
        self.assertFalse(result['complete'])

    def test_tampered_image_is_rejected(self):
        self.collect()
        image = next((self.source/'images').glob('*.png'))
        image.write_bytes(b'changed')
        with self.assertRaisesRegex(LabError, 'hash'):
            self.f.load_snapshots(self.source)

    def test_invalidated_gpu_capture_cannot_be_replayed(self):
        self.collect()
        (self.source/'INVALIDATED.json').write_text('{"invalid_for_factorial_conclusions": true}')
        client = SimpleNamespace(health=Mock(return_value={'max_images': 2, 'is_mock': True}),
                                 predict=Mock(side_effect=LabError('fixture must not be reached')))
        with self.assertRaisesRegex(LabError, 'invalidated'):
            self.f.run_replay(self.source, Path(self.temp.name)/'replay', client, allow_mock=True)
        client.health.assert_not_called()
        client.predict.assert_not_called()

    def test_snapshot_path_cannot_escape_source(self):
        self.collect()
        path = self.source/'snapshots.json'
        bundle = json.loads(path.read_text())
        bundle['records'][0]['images']['blue'][0]['path'] = '../outside.png'
        path.write_text(json.dumps(bundle))
        with self.assertRaisesRegex(LabError, 'path'):
            self.f.load_snapshots(self.source)

    def test_fifty_six_requests_through_real_local_http_with_explicit_mock(self):
        from visual_lab.server import DecisionBridge, MockEngine, make_http_server
        from visual_lab.client import DecisionClient
        self.collect()
        server = make_http_server('127.0.0.1', 0, DecisionBridge(MockEngine()))
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            output = Path(self.temp.name)/'replay'
            client = DecisionClient(f'http://127.0.0.1:{server.server_port}/v1/decisions')
            result = self.f.run_replay(self.source, output, client, allow_mock=True)
            self.assertTrue(result['complete'])
            self.assertTrue(result['mock_backend'])
            self.assertEqual(result['api_completed'], 56)
            self.assertEqual(sum(len(row['image_sha256s']) == 2 for row in result['decisions']), 28)
            self.assertEqual(len(result['descriptive_main_effects']), 3)
            self.assertFalse(result['model_had_control'])
            self.assertTrue(all(cell['baseline_agreement'] == 7 for cell in result['cells']))
            with self.assertRaises(FileExistsError):
                self.f.run_replay(self.source, output, client, allow_mock=True)
        finally:
            server.shutdown(); server.server_close(); thread.join(2)

    def test_replay_failure_never_skips_or_falls_back(self):
        self.collect()
        client = SimpleNamespace(health=lambda **kw: {'max_images': 2, 'is_mock': True},
                                 predict=Mock(side_effect=LabError('synthetic API failure')))
        result = self.f.run_replay(self.source, Path(self.temp.name)/'replay', client, allow_mock=True)
        self.assertFalse(result['complete'])
        self.assertEqual(result['api_completed'], 0)
        self.assertIn('API failure', result['error'])
        self.assertEqual(client.predict.call_count, 1)

    def test_single_image_service_is_rejected_before_output_creation(self):
        self.collect()
        client = SimpleNamespace(health=lambda **kw: {'max_images': 1, 'is_mock': True})
        output = Path(self.temp.name)/'replay'
        with self.assertRaises(ProtocolError):
            self.f.run_replay(self.source, output, client, allow_mock=True)
        self.assertFalse(output.exists())

    def test_real_mode_rejects_synthetic_capture_before_output_creation(self):
        self.collect()
        client = SimpleNamespace(health=lambda **kw: {'max_images': 2, 'is_mock': False, 'vision_input_audit': True}, predict=Mock())
        output = Path(self.temp.name)/'replay'
        with self.assertRaisesRegex(LabError, 'production|synthetic'):
            self.f.run_replay(self.source, output, client)
        client.predict.assert_not_called()
        self.assertFalse(output.exists())

    def test_corrupt_actual_processor_audit_is_rejected(self):
        # Deliberately faked real-mode flags exercise rejection, not model quality.
        from visual_lab.server import MockEngine
        import hashlib
        self.collect()
        # Only imitate the production manifest tag to reach the negative API gate.
        # This remains an explicit CPU fixture with no model/renderer.
        manifest = self.source/'manifest.json'
        metadata = json.loads(manifest.read_text())
        metadata.update(kind='paired_factorial_capture', synthetic_fixture=False)
        manifest.write_text(json.dumps(metadata))
        health = {'max_images': 2, 'is_mock': False, 'vision_input_audit': True,
                  'inference_py_sha256': 'CPU-FIXTURE', 'temperature': 1.0}
        def predict(request):
            raw = MockEngine().predict(request)
            raw['model'] = 'CPU-CONTRACT-FIXTURE-NOT-A-REAL-MODEL'
            raw['_bridge'] = {'is_mock': False, 'image_count': len(request['images']),
                              'image_sha256s': [hashlib.sha256(base64.b64decode(item['data'])).hexdigest() for item in request['images']]}
            raw['_vision_audit'] = {'normalized_rgb_sha256s': [], 'image_grid_thw': []}
            return raw, .1
        client = SimpleNamespace(health=lambda **kw: health, predict=predict)
        result = self.f.run_replay(self.source, Path(self.temp.name)/'replay', client)
        self.assertFalse(result['complete'])
        self.assertEqual(result['api_completed'], 0)
        self.assertIn('processor', result['error'])

    def test_changed_service_metadata_marks_replay_incomplete(self):
        from visual_lab.server import DecisionBridge, MockEngine
        self.collect()
        bridge = DecisionBridge(MockEngine())
        calls = [0]
        def health(**kw):
            calls[0] += 1
            value = bridge.health()
            if calls[0] == 2:
                value['protocol_source_sha256'] = 'changed'
            return value
        client = SimpleNamespace(health=health, predict=lambda request: (bridge.predict(request), .1))
        result = self.f.run_replay(self.source, Path(self.temp.name)/'replay', client, allow_mock=True)
        self.assertEqual(result['api_completed'], 56)
        self.assertFalse(result['complete'])
        self.assertIn('provenance', result['error'])


class SimExperimentTests(unittest.TestCase):
    def test_lower_target_lookup_restores_phase_even_on_error(self):
        from visual_lab.sim import IsaacScene
        scene = IsaacScene.__new__(IsaacScene)
        scene.scenario = SimpleNamespace(_event=2, _phase_ee_target=Mock(side_effect=LabError('fake target failure')))
        with self.assertRaises(LabError):
            scene.placement_tool_target()
        self.assertEqual(scene.scenario._event, 2)

    def test_color_only_changes_four_display_attributes(self):
        from visual_lab.sim import IsaacScene
        attrs = [Mock() for _ in range(4)]
        prims = [SimpleNamespace(IsValid=lambda: True, attr=attr) for attr in attrs]
        stage = SimpleNamespace(GetPrimAtPath=lambda path: prims[int(path.rsplit('_', 1)[1])])
        usd = SimpleNamespace(get_context=lambda: SimpleNamespace(get_stage=lambda: stage))
        geom = SimpleNamespace(Gprim=lambda prim: SimpleNamespace(GetDisplayColorAttr=lambda: prim.attr))
        modules = {'omni': SimpleNamespace(usd=usd), 'omni.usd': usd,
                   'pxr': SimpleNamespace(UsdGeom=geom, Gf=SimpleNamespace(Vec3f=lambda *args: args))}
        scene = IsaacScene.__new__(IsaacScene)
        with patch.dict('sys.modules', modules):
            scene.set_goal_color([1, .85, .02])
            for attr in attrs:
                attr.Set.assert_called_once_with([(1., .85, .02)])
            with self.assertRaises(LabError):
                scene.set_goal_color([2, 0, 0])

    def test_both_annotators_read_same_render_step(self):
        from visual_lab.capture import capture_camera_batch
        tick = [0]
        reads = []
        timeline = SimpleNamespace(pause=Mock(), get_current_time=lambda: 0.)
        orchestrator = SimpleNamespace(step=lambda **kw: tick.__setitem__(0, tick[0]+1))
        class Array:
            shape, dtype = (2, 2, 3), 'uint8'
            def __getitem__(self, key):
                return self
        cameras = [SimpleNamespace(timeline=timeline, rep=SimpleNamespace(orchestrator=orchestrator),
                                   config={'resolution': [2, 2], 'rt_subframes': 4},
                                   annotator=SimpleNamespace(get_data=lambda: reads.append(tick[0]) or Array())) for _ in range(2)]
        numpy = SimpleNamespace(asarray=lambda data: data, uint8='uint8', max=lambda data: 10)
        with patch.dict('sys.modules', {'numpy': numpy}), patch('visual_lab.capture.encode_array', return_value=b'PNG'):
            self.assertEqual(capture_camera_batch(cameras), [b'PNG', b'PNG'])
        self.assertEqual(tick[0], 3)
        self.assertEqual(reads, [3, 3])


if __name__ == '__main__':
    unittest.main()
