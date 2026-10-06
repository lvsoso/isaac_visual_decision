"""CPU regressions for read/modify/write joint targets within one physics frame.

The articulation double models getters that expose the last committed targets:
a second subset write can discard the first pending write. It is not GPU physics.
"""
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

from visual_lab.core import LabError, load_config
from visual_lab.sim import IsaacScene
from tests.test_sim_timeline import DeferredTimeline

ROOT = Path(__file__).resolve().parents[1]


class Array:
    def __init__(self, values):
        self.values = list(values)

    def numpy(self):
        return self

    def reshape(self, *args):
        return self

    def tolist(self):
        return list(self.values)


def flat(values):
    return values.tolist() if isinstance(values, Array) else list(values)


class DeferredArticulation:
    def __init__(self):
        self.dof_names = [f"joint_{i}" for i in range(8)]
        self.positions = [0.0]*8
        self.targets = [0.0]*8
        self.pending = None
        self.writes = []

    def get_dof_positions(self):
        return Array(self.positions)

    def set_dof_position_targets(self, positions, *, dof_indices=None):
        values = flat(positions)
        indices = list(range(8)) if dof_indices is None else flat(dof_indices)
        # Reflect the full-vector read/modify/write of the tensor target API.
        data = list(self.targets)
        for index, value in zip(indices, values):
            data[index] = value
        self.pending = data
        self.writes.append((indices, values))

    def update(self):
        if self.pending is not None:
            self.targets = self.pending
            self.positions = list(self.targets)
            self.pending = None


class SimCommandTests(unittest.TestCase):
    def setUp(self):
        self.scene = IsaacScene.__new__(IsaacScene)
        self.articulation = DeferredArticulation()
        self.arm_targets = [0.1, -0.2, 0.3, -0.4, 0.5, -0.6]
        self.target = [0.5, 0.0, 0.525]
        self.initial_ee = [1.27949, 0.42191, 0.06085]
        self.controller = Mock()
        self.controller.reset.return_value = True
        self.controller.forward.return_value = SimpleNamespace(joints=SimpleNamespace(
            positions=Array(self.arm_targets), position_indices=Array(range(6))))
        self.scene.scenario = SimpleNamespace(
            _articulation=self.articulation, _finger_idx=6, _controller=self.controller,
            _phase_ee_target=lambda: Array(self.target), _estimated_state=Mock(),
            _make_setpoint=Mock(), _OPEN_POS=0.0, _CLOSED_POS=0.5,
            _set_gripper=lambda pos: self.articulation.set_dof_position_targets([pos], dof_indices=[6]))
        self.scene.timeline = DeferredTimeline()
        self.updates = 0

        def update():
            self.scene.timeline.apply_pending()
            if self.scene.timeline.is_playing():
                self.articulation.update()
                self.updates += 1

        self.scene.app = SimpleNamespace(is_running=lambda: True, update=update)
        self.scene.manager = SimpleNamespace(is_simulating=self.scene.timeline.is_playing)
        self.scene.c = load_config(ROOT / "configs/default.json")
        self.scene.c.update(frame_scale=1, gripper_min_frames=1)
        self.scene.c["tutorial_phase_limits"] = [3]*8
        self.scene.frames = 0
        self.scene.record_every = 0
        self.scene.gripper_command = 0.0
        self.scene._sync_world = Mock()

        def proprioception():
            moved = self.articulation.positions[:6] == self.arm_targets
            return {"ee_world_position_m": list(self.target if moved else self.initial_ee),
                    "finger_joint_position_rad": self.articulation.positions[6]}

        self.scene.proprioception = proprioception

    def test_arm_command_survives_gripper_preservation(self):
        result = self.scene.execute("pre_grasp")
        self.assertEqual(self.articulation.positions[:6], self.arm_targets)
        self.assertEqual(result["status"], "reached")
        self.assertEqual(len(self.articulation.writes), 1)
        self.assertEqual(self.updates, 1)

    def test_grasp_holds_arm_and_closes_finger_in_one_write(self):
        self.articulation.positions[:6] = self.arm_targets
        self.articulation.targets = list(self.articulation.positions)
        result = self.scene.execute("grasp")
        self.assertEqual(result["status"], "reached")
        self.assertEqual(self.articulation.positions[:6], self.arm_targets)
        self.assertEqual(self.articulation.positions[6], 0.5)
        self.assertEqual(len(self.articulation.writes), 1)

    def test_closed_finger_overrides_controller_finger_target(self):
        self.scene.gripper_command = 0.5
        self.controller.forward.return_value = SimpleNamespace(joints=SimpleNamespace(
            positions=Array(self.arm_targets + [0.0]), position_indices=Array(range(7))))
        result = self.scene.execute("transport")
        self.assertEqual(result["status"], "reached")
        self.assertEqual(self.articulation.positions[:6], self.arm_targets)
        self.assertEqual(self.articulation.positions[6], 0.5)
        self.assertEqual(len(self.articulation.writes), 1)

    def test_controller_without_output_fails_before_physics(self):
        self.controller.forward.return_value = None
        with self.assertRaisesRegex(LabError, "no joint position command"):
            self.scene.execute("pre_grasp")
        self.assertEqual(self.updates, 0)
        self.assertEqual(self.articulation.writes, [])

    def test_mismatched_targets_and_indices_are_rejected(self):
        self.controller.forward.return_value.joints.position_indices = Array(range(5))
        with self.assertRaisesRegex(LabError, "target.*indices"):
            self.scene.execute("pre_grasp")
        self.assertEqual(self.articulation.writes, [])

    def test_nonfinite_target_is_rejected(self):
        self.controller.forward.return_value.joints.positions = Array([float("nan")]*6)
        with self.assertRaisesRegex(LabError, "finite"):
            self.scene.execute("pre_grasp")
        self.assertEqual(self.articulation.writes, [])

    def test_invalid_joint_index_is_rejected(self):
        self.controller.forward.return_value.joints.position_indices = Array([0, 1, 2, 3, 4, 99])
        with self.assertRaisesRegex(LabError, "index"):
            self.scene.execute("pre_grasp")
        self.assertEqual(self.articulation.writes, [])

    def test_phase_end_reports_commands_and_measured_motion(self):
        result = self.scene.execute("pre_grasp")
        self.assertEqual(result["controller_command_frames"], 1)
        self.assertEqual(result["ee_world_position_start_m"], self.initial_ee)
        self.assertEqual(result["ee_world_position_end_m"], self.target)
        self.assertEqual(result["joint_positions_start_rad"], [0.0]*8)
        self.assertEqual(result["joint_positions_end_rad"][:6], self.arm_targets)
        self.assertAlmostEqual(result["max_joint_displacement_rad"], 0.6)


if __name__ == "__main__":
    unittest.main()
