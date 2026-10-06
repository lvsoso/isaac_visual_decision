"""Controller-model tool FK and physical finger telemetry are distinct references.

CPU doubles test routing and world transforms, not model/asset calibration or grasp.
"""
import math
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from visual_lab.core import LabError, model_state
from tests import test_sim_commands as commands


class SimReferenceTests(unittest.TestCase):
    def setUp(self):
        self.fixture = commands.SimCommandTests()
        self.fixture.setUp()
        self.scene = self.fixture.scene
        self.scene.scenario._tool_frame = "tool0"
        self.finger_position = [0.59402138, 0.01116086, 0.42365772]
        self.scene.proprioception = lambda: {
            "ee_world_position_m": self.finger_position,
            "finger_joint_position_rad": self.fixture.articulation.positions[6]}
        self.scene._controller_tool_world_position = Mock(side_effect=lambda:
            list(self.fixture.target if self.fixture.articulation.positions[:6] == self.fixture.arm_targets
                 else self.fixture.initial_ee))

    def test_tool_converges_without_comparing_finger_to_tool_target(self):
        result = self.scene.execute("pre_grasp")
        self.assertEqual(result["status"], "reached")
        self.assertEqual(result["frames"], 1)
        self.assertGreater(result["ee_error_m"], 0.13)  # keep the physical finger diagnostic
        self.assertEqual(result["controller_tool_error_m"], 0.0)
        self.assertEqual(result["controller_tool_world_position_m"], self.fixture.target)
        self.assertEqual(result["convergence_position_source"], "controller_model_fk_from_measured_joints")
        self.assertEqual(result["controller_tool_frame"], "tool0")

    def test_finger_at_target_does_not_mask_unconverged_controller_tool(self):
        self.finger_position = list(self.fixture.target)
        self.scene._controller_tool_world_position.return_value = list(self.fixture.initial_ee)
        self.scene._controller_tool_world_position.side_effect = None
        result = self.scene.execute("pre_grasp")
        self.assertEqual(result["status"], "timeout")
        self.assertEqual(result["ee_error_m"], 0.0)
        self.assertGreater(result["controller_tool_error_m"], 0.9)

    def test_sent_joint_targets_without_measured_motion_cannot_pass(self):
        self.fixture.articulation.update = lambda: None
        result = self.scene.execute("pre_grasp")
        self.assertEqual(result["status"], "timeout")
        self.assertEqual(result["max_joint_displacement_rad"], 0.0)
        self.assertGreater(result["controller_tool_error_m"], 0.9)

    def test_controller_targets_and_model_finger_state_are_not_rewritten(self):
        self.scene.execute("pre_grasp")
        for call in self.scene.scenario._make_setpoint.call_args_list:
            self.assertEqual(call.args[0].tolist(), self.fixture.target)
        state = model_state(self.scene.proprioception(), "pre_grasp", "reached")
        self.assertEqual(state["ee_reference"], "right_inner_finger link, not the gripper's grasp center")
        self.assertEqual(state["ee_world_position_m"], [round(v, 5) for v in self.finger_position])
        self.assertNotIn("controller_tool_world_position_m", state)

    def fk_scene(self, *, rotation=None, origin=None, quaternion=None):
        # Exercise the actual helper, replacing only native NumPy/cuMotion objects.
        del self.scene._controller_tool_world_position
        self.scene.np = SimpleNamespace(array=Mock(side_effect=lambda values, **kw: commands.Array(values)))
        robot = SimpleNamespace(controlled_joint_names=["arm_a", "arm_b"],
            kinematics=SimpleNamespace(position=Mock(return_value=commands.Array([1.0, 2.0, 3.0]))))
        self.scene.scenario._cumotion_robot = robot
        self.scene.scenario._articulation = SimpleNamespace(
            dof_names=["finger", "arm_b", "arm_a"],
            get_dof_positions=lambda: commands.Array([0.5, 0.2, 0.1]),
            get_world_poses=lambda: (commands.Array(origin or [0.0]*3),
                                     commands.Array(quaternion or [1.0, 0.0, 0.0, 0.0])))
        rotation_factory = Mock(return_value=SimpleNamespace(matrix=lambda: commands.Array(
            rotation or [[1, 0, 0], [0, 1, 0], [0, 0, 1]])))
        return robot, rotation_factory

    def test_fk_uses_measured_joints_in_controller_order(self):
        robot, rotation = self.fk_scene()
        with patch.dict("sys.modules", {"cumotion": SimpleNamespace(Rotation3=rotation)}):
            position = self.scene._controller_tool_world_position()
        self.assertEqual(position, [1.0, 2.0, 3.0])
        self.assertEqual(robot.kinematics.position.call_args.args[0].tolist(), [0.1, 0.2])
        self.assertEqual(robot.kinematics.position.call_args.args[1], "tool0")
        rotation.assert_called_once_with(1.0, 0.0, 0.0, 0.0)

    def test_fk_position_is_rotated_and_translated_to_world(self):
        quaternion = [math.sqrt(0.5), 0.0, 0.0, math.sqrt(0.5)]
        _, rotation = self.fk_scene(rotation=[[0, -1, 0], [1, 0, 0], [0, 0, 1]],
                                   origin=[10.0, 20.0, 30.0], quaternion=quaternion)
        with patch.dict("sys.modules", {"cumotion": SimpleNamespace(Rotation3=rotation)}):
            self.assertEqual(self.scene._controller_tool_world_position(), [8.0, 21.0, 33.0])
        rotation.assert_called_once_with(*quaternion)

    def test_nonfinite_fk_position_is_rejected(self):
        robot, rotation = self.fk_scene()
        robot.kinematics.position.return_value = commands.Array([float("nan"), 0, 0])
        with patch.dict("sys.modules", {"cumotion": SimpleNamespace(Rotation3=rotation)}):
            with self.assertRaisesRegex(LabError, "non-finite"):
                self.scene._controller_tool_world_position()

    def test_missing_controlled_joint_is_rejected(self):
        robot, rotation = self.fk_scene()
        robot.controlled_joint_names = ["missing_joint"]
        with patch.dict("sys.modules", {"cumotion": SimpleNamespace(Rotation3=rotation)}):
            with self.assertRaisesRegex(LabError, "controlled joint"):
                self.scene._controller_tool_world_position()


if __name__ == "__main__":
    unittest.main()
