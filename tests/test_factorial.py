"""Synthetic paired-factor tests, never real-model or GPU evidence."""
import base64
import copy
import importlib
import json
import math
import unittest
from pathlib import Path

from visual_lab.core import ACTIONS, load_config, model_state
from visual_lab.png import encode_rgb_bytes
from visual_lab.protocol import validate_request

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


if __name__ == '__main__':
    unittest.main()
