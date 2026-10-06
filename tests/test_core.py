import copy
import json
import math
import unittest
from pathlib import Path
from visual_lab.core import *
from visual_lab.protocol import make_request, validate_request
from visual_lab.png import encode_rgb_bytes
from visual_lab.server import MockEngine

ROOT = Path(__file__).resolve().parents[1]

class CoreTests(unittest.TestCase):
    def setUp(self):
        self.c = load_config(ROOT/"configs/default.json")
        self.png = encode_rgb_bytes(2, 2, bytes([180,50,50]*4))
        self.state = model_state({"ee_world_position_m":[.5,0,.2],"finger_joint_position_rad":0}, None, None)
        self.request = make_request(self.png, self.state)
        self.response = MockEngine().predict(self.request)
        self.response["_bridge"] = {"is_mock":True}

    def test_request_contract(self):
        validate_request(self.request)
    def test_option_order_preserved(self):
        self.assertEqual(tuple(self.request["questions"]["next_stage"]["criteria"]), ACTIONS)
    def test_state_has_no_world_truth(self):
        raw = {"ee_world_position_m":[1,2,3],"finger_joint_position_rad":.2,
               "cube_position":[9,9,9],"target_position":[9,9,9],"decision_index":4,"episode_id":3}
        state = model_state(raw, "approach", "reached")
        for forbidden in ("cube_position","target_position","decision_index","episode_id"):
            self.assertNotIn(forbidden, state)
    def test_state_not_mutated(self):
        self.request["state"]["task"] = "changed"
        self.assertNotEqual(self.state["task"], "changed")
    def test_unknown_previous_phase(self):
        with self.assertRaises(ProtocolError):
            model_state({"ee_world_position_m":[0,0,0],"finger_joint_position_rad":0}, "unknown", None)
    def test_nan_position_rejected(self):
        with self.assertRaises(ProtocolError):
            vector3([0,float("nan"),0], "test")
    def test_bool_not_number(self):
        with self.assertRaises(ProtocolError):
            finite_number(True, "x")
    def test_png_size_validation(self):
        with self.assertRaises(ProtocolError):
            encode_rgb_bytes(2,2,b"bad")
    def test_wrong_magic_rejected(self):
        with self.assertRaises(ProtocolError):
            make_request(b"not a PNG", self.state)
    def test_no_local_image_path_over_http(self):
        self.request["images"] = ["/etc/passwd"]
        with self.assertRaises(ProtocolError):
            validate_request(self.request)
    def test_no_remote_image_url(self):
        self.request["images"] = [{"url":"https://example.com/image.png"}]
        with self.assertRaises(ProtocolError):
            validate_request(self.request)
    def test_extra_request_key_rejected(self):
        self.request["targets"] = {"next_stage":"grasp"}
        with self.assertRaises(ProtocolError):
            validate_request(self.request)
    def test_reordered_options_rejected(self):
        c = self.request["questions"]["next_stage"]["criteria"]
        self.request["questions"]["next_stage"]["criteria"] = dict(reversed(list(c.items())))
        with self.assertRaises(ProtocolError):
            validate_request(self.request)
    def test_mock_rejected_for_real(self):
        with self.assertRaises(ProtocolError):
            parse_decision(self.response)
    def test_mock_explicitly_accepted(self):
        self.assertEqual(parse_decision(self.response,allow_mock=True).action,"pre_grasp")
    def test_probability_missing_key(self):
        del self.response["answers"]["next_stage"]["probabilities"]["abort"]
        with self.assertRaises(ProtocolError):
            parse_decision(self.response,allow_mock=True)
    def test_probability_bad_sum(self):
        self.response["answers"]["next_stage"]["probabilities"]["abort"] = .7
        with self.assertRaises(ProtocolError):
            parse_decision(self.response,allow_mock=True)
    def test_probability_nan(self):
        self.response["answers"]["next_stage"]["probabilities"]["abort"] = math.nan
        with self.assertRaises(ProtocolError):
            parse_decision(self.response,allow_mock=True)
    def test_choice_not_argmax(self):
        self.response["answers"]["next_stage"]["choice"] = "grasp"
        with self.assertRaises(ProtocolError):
            parse_decision(self.response,allow_mock=True)
    def test_choice_unknown(self):
        self.response["answers"]["next_stage"]["choice"] = "move_joint_9"
        with self.assertRaises(ProtocolError):
            parse_decision(self.response,allow_mock=True)
    def test_confidence_missing(self):
        del self.response["answers"]["next_stage"]["confidence"]
        with self.assertRaises(ProtocolError):
            parse_decision(self.response,allow_mock=True)
    def test_no_synthesized_response_shape(self):
        with self.assertRaises(ProtocolError):
            parse_decision({"choice":"grasp"})
    def test_gripper_cannot_finish_before_60(self):
        self.assertIsNone(phase_result("grasp",59,0,0,self.c))
    def test_gripper_finishes_at_60(self):
        self.assertEqual(phase_result("grasp",60,0,0,self.c),"reached")
    def test_arm_not_forced_to_wait_60(self):
        self.c["frame_scale"] = 1
        self.assertEqual(phase_result("lift",50,0,0,self.c),"reached")
    def test_timeout_with_error(self):
        self.c["frame_scale"] = 1
        self.assertEqual(phase_result("lift",50,1,0,self.c),"timeout")
    def test_convergence_wins_at_timeout_frame(self):
        self.c["frame_scale"] = 1
        self.assertEqual(phase_result("pre_grasp",250,0,0,self.c),"reached")
    def test_impossible_budget_is_rejected(self):
        self.c["frame_scale"] = 1
        self.c["arm_min_frames"] = 60
        with self.assertRaises(ProtocolError):
            validate_timing(self.c)
    def test_ground_height_not_command_height(self):
        r = judge_episode([.5,.5,.025],self.c,released=True,timed_out=False,termination_reason="completed")
        self.assertTrue(r["strict_success"])
    def test_command_target_z_does_not_pass_ground_test(self):
        r = judge_episode([.5,.5,.05],self.c,released=True,timed_out=False,termination_reason="completed")
        self.assertFalse(r["physical_completion"])
    def test_no_release_cannot_pass(self):
        self.assertFalse(judge_episode([.5,.5,.025],self.c,released=False,timed_out=False,termination_reason="completed")["strict_success"])
    def test_timeout_cannot_strict_pass(self):
        r = judge_episode([.5,.5,.025],self.c,released=True,timed_out=True,termination_reason="completed")
        self.assertTrue(r["physical_completion"])
        self.assertFalse(r["strict_success"])
    def test_abort_cannot_strict_pass(self):
        self.assertFalse(judge_episode([.5,.5,.025],self.c,released=True,timed_out=False,termination_reason="policy_abort")["strict_success"])
    def test_outside_xy(self):
        self.assertFalse(judge_episode([.6,.5,.025],self.c,released=True,timed_out=False,termination_reason="completed")["physical_completion"])

if __name__ == "__main__": unittest.main()
