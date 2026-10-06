"""Prompt-contract regressions, not proof of real-model decision correctness."""
import copy
import unittest

from visual_lab.core import ACTIONS, ProtocolError, model_state
from visual_lab.png import encode_rgb_bytes
from visual_lab.protocol import CRITERIA, INSTRUCTIONS, make_request, validate_request


class ActionDescriptionTests(unittest.TestCase):
    def test_lift_excludes_an_already_elevated_cube(self):
        self.assertIn("already visibly elevated", CRITERIA["lift"])
        self.assertIn("Do not", CRITERIA["lift"])

    def test_grasp_excludes_already_closed_fingers(self):
        self.assertIn("already closed", CRITERIA["grasp"])
        self.assertIn("Do not", CRITERIA["grasp"])

    def test_motion_descriptions_have_observable_preconditions_and_exclusions(self):
        for action in ("pre_grasp", "approach", "lift", "transport", "lower", "release"):
            with self.subTest(action=action):
                self.assertIn("Use when", CRITERIA[action])
                self.assertIn("Do not", CRITERIA[action])

    def test_joint_reference_is_explained_without_claiming_a_grasp(self):
        self.assertIn("near 0.0", INSTRUCTIONS)
        self.assertIn("near 0.5", INSTRUCTIONS)
        self.assertIn("not proof", INSTRUCTIONS)
        self.assertIn("not the cube center", INSTRUCTIONS)

    def test_history_is_context_not_a_mandatory_sequence(self):
        self.assertIn("not a mandatory sequence", INSTRUCTIONS)

    def test_request_keeps_all_options_and_original_evidence(self):
        png = encode_rgb_bytes(2, 2, bytes([180, 50, 50]*4))
        state = model_state({"ee_world_position_m": [0.55, 0.01, 0.38],
                             "finger_joint_position_rad": 0.496}, "lift", "reached")
        original = copy.deepcopy(state)
        request = make_request(png, state)
        validate_request(request)
        self.assertEqual(tuple(request["questions"]["next_stage"]["criteria"]), ACTIONS)
        self.assertEqual(request["state"], original)
        self.assertEqual(state, original)
        self.assertEqual(set(request), {"state", "images", "questions"})
        self.assertNotIn("cube_world_position_m", request["state"])
        self.assertNotIn("target_world_position_m", request["state"])

    def test_history_does_not_mask_or_rewrite_candidate_actions(self):
        png = encode_rgb_bytes(1, 1, bytes([180, 50, 50]))
        criteria = []
        for previous in ACTIONS[:-1]:
            state = model_state({"ee_world_position_m": [0.5, 0.5, 0.3],
                                 "finger_joint_position_rad": 0.5}, previous, "reached")
            request = make_request(png, state)
            criteria.append(request["questions"]["next_stage"]["criteria"])
        self.assertTrue(all(row == CRITERIA for row in criteria))
        self.assertEqual(len(criteria[0]), 8)

    def test_request_builder_rejects_non_object_state(self):
        png = encode_rgb_bytes(1, 1, bytes([180, 50, 50]))
        with self.assertRaisesRegex(ProtocolError, "state must be a dict"):
            make_request(png, None)

    def test_malformed_evidence_or_question_is_rejected(self):
        png = encode_rgb_bytes(1, 1, bytes([180, 50, 50]))
        original = make_request(png, {})
        cases = [
            ("state", lambda r: r.update(state=None)),
            ("question_type", lambda r: r["questions"]["next_stage"].update(type="score")),
            ("blank_description", lambda r: r["questions"]["next_stage"]["criteria"].update(lift=" ")),
            ("instructions", lambda r: r["questions"]["next_stage"].update(instructions=None)),
            ("missing_criteria", lambda r: r["questions"]["next_stage"].pop("criteria")),
            ("no_image", lambda r: r.update(images=[])),
            ("wrong_image_type", lambda r: r["images"][0].update(type="image/jpeg")),
        ]
        for name, change in cases:
            with self.subTest(name=name):
                request = copy.deepcopy(original)
                change(request)
                with self.assertRaises(ProtocolError):
                    validate_request(request)


if __name__ == "__main__":
    unittest.main()
