"""Near-contact convergence tests; no CPU test proves actual pad contact or grip.

The uploaded GPU approach stopped 18.8 mm high before closing on a 50 mm cube.
"""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock

from visual_lab.core import PHASES, ProtocolError, load_config, phase_result, validate_timing
from tests import test_sim_commands as commands

ROOT = Path(__file__).resolve().parents[1]


class NearPoseTests(unittest.TestCase):
    def setUp(self):
        self.c = load_config(ROOT / "configs/default.json")
        self.c.update(near_pose_tolerance_m=0.005, near_pose_stable_frames=12)

    def phase(self, action, frame, error, stable):
        return phase_result(action, frame, error, 0.0, self.c, near_stable_frames=stable)

    def config_with(self, **changes):
        values = json.loads((ROOT / "configs/default.json").read_text())
        values.update(changes)
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        path = Path(temp.name) / "config.json"
        path.write_text(json.dumps(values))
        return path

    def test_near_phases_reject_old_19mm_early_stop(self):
        for action in ("approach", "lower"):
            with self.subTest(action=action):
                self.assertIsNone(self.phase(action, 60, 0.0189, 12))

    def test_near_phase_requires_complete_stable_window(self):
        self.assertIsNone(self.phase("approach", 60, 0.004, 11))
        self.assertEqual(self.phase("approach", 61, 0.004, 12), "reached")

    def test_unstable_last_budget_frame_times_out(self):
        maximum = self.c["tutorial_phase_limits"][PHASES.index("approach")] * self.c["frame_scale"]
        self.assertEqual(self.phase("approach", maximum, 0.004, 11), "timeout")

    def test_stable_last_budget_frame_can_reach(self):
        maximum = self.c["tutorial_phase_limits"][PHASES.index("approach")] * self.c["frame_scale"]
        self.assertEqual(self.phase("approach", maximum, 0.004, 12), "reached")

    def test_stable_window_must_fit_phase_budget(self):
        self.c["frame_scale"] = 1
        self.c["tutorial_phase_limits"][PHASES.index("approach")] = 11
        with self.assertRaisesRegex(ProtocolError, "approach"):
            validate_timing(self.c)

    def test_legacy_configs_get_explicit_near_defaults(self):
        path = self.config_with()
        values = json.loads(path.read_text())
        values.pop("near_pose_tolerance_m", None)
        values.pop("near_pose_stable_frames", None)
        path.write_text(json.dumps(values))
        loaded = load_config(path)
        self.assertEqual(loaded["near_pose_tolerance_m"], 0.005)
        self.assertEqual(loaded["near_pose_stable_frames"], 12)

    def test_invalid_near_tolerance_is_rejected(self):
        for value in (0, -0.001, True, float("nan"), 0.03):
            with self.subTest(value=value):
                with self.assertRaisesRegex(ProtocolError, "near_pose_tolerance_m"):
                    load_config(self.config_with(near_pose_tolerance_m=value))

    def test_invalid_stable_frame_count_is_rejected(self):
        for value in (0, -1, True, 12.5, "12"):
            with self.subTest(value=value):
                with self.assertRaisesRegex(ProtocolError, "near_pose_stable_frames"):
                    load_config(self.config_with(near_pose_stable_frames=value))

    def test_default_config_records_5mm_and_12_stable_frames(self):
        values = json.loads((ROOT / "configs/default.json").read_text())
        self.assertEqual(values["near_pose_tolerance_m"], 0.005)
        self.assertEqual(values["near_pose_stable_frames"], 12)

    def adapter(self, errors):
        fixture = commands.SimCommandTests()
        fixture.setUp()
        scene = fixture.scene
        scene.c.update(near_pose_tolerance_m=0.005, near_pose_stable_frames=12)
        scene.c["tutorial_phase_limits"] = [30]*8
        scene._controller_tool_world_position = Mock(side_effect=[
            [fixture.target[0], fixture.target[1], fixture.target[2] + error] for error in errors])
        return scene, fixture

    def test_adapter_continues_until_near_and_stable(self):
        errors = [0.019, 0.007] + [0.004]*12
        scene, fixture = self.adapter(errors)
        result = scene.execute("approach")
        self.assertEqual(result["status"], "reached")
        self.assertEqual(result["frames"], 14)
        self.assertEqual(fixture.updates, 14)
        self.assertEqual(result["near_pose_stable_frames"], 12)
        self.assertEqual(result["required_near_pose_stable_frames"], 12)
        self.assertEqual(result["motion_position_tolerance_m"], 0.005)
        for call in scene.scenario._make_setpoint.call_args_list:
            self.assertEqual(call.args[0].tolist(), fixture.target)

    def test_adapter_resets_window_when_pose_leaves_tolerance(self):
        errors = [0.004]*11 + [0.006] + [0.004]*12
        scene, fixture = self.adapter(errors)
        result = scene.execute("approach")
        self.assertEqual(result["status"], "reached")
        self.assertEqual(result["frames"], 24)
        self.assertEqual(fixture.updates, 24)
        self.assertEqual(result["near_pose_stable_frames"], 12)

    def test_other_motion_keeps_original_coarse_tolerance(self):
        scene, fixture = self.adapter([0.019])
        result = scene.execute("transport")
        self.assertEqual(result["status"], "reached")
        self.assertEqual(fixture.updates, 1)
        self.assertEqual(result["motion_position_tolerance_m"], 0.02)
        self.assertEqual(result["required_near_pose_stable_frames"], 0)

    def test_lower_never_reaches_while_19mm_high(self):
        scene, fixture = self.adapter([0.019]*30)
        result = scene.execute("lower")
        self.assertEqual(result["status"], "timeout")
        self.assertEqual(fixture.updates, 30)
        self.assertEqual(result["near_pose_stable_frames"], 0)


if __name__ == "__main__":
    unittest.main()
