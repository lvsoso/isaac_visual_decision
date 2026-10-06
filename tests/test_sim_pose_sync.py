"""CPU doubles for CUDA tensor state versus default USD pose readers.

These model backend routing and initialization order, not Isaac GPU rendering.
"""
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from visual_lab.core import LabError, load_config
from visual_lab.sim import IsaacScene
from tests.test_sim_timeline import DeferredTimeline

ROOT = Path(__file__).resolve().parents[1]


class Settings:
    def __init__(self, events):
        self.events = events
        self.values = {"/physics/updateToUsd": False, "/physics/suppressReadback": True}

    def set_bool(self, name, value):
        self.events.append((name, value))
        self.values[name] = value

    def get_as_bool(self, name):
        return self.values[name]


class Manager:
    def __init__(self, settings, events, timeline):
        self.settings, self.events, self.timeline = settings, events, timeline
        self.fabric_enabled = True

    def setup_simulation(self, *, dt, device):
        self.events.append(("setup", device))
        # Model the CUDA setup side effects in NVIDIA SimulationManager.
        self.fabric_enabled = True
        self.settings.values.update({"/physics/updateToUsd": False, "/physics/suppressReadback": True})

    def enable_fabric(self, enable):
        self.events.append(("fabric", enable))
        self.fabric_enabled = enable
        self.settings.values["/physics/updateToUsd"] = not enable

    def is_fabric_enabled(self):
        return self.fabric_enabled

    def is_simulating(self):
        return self.timeline.is_playing()


class Values:
    def __init__(self, values):
        self.values = values

    def numpy(self):
        return self

    def reshape(self, *args):
        return self

    def tolist(self):
        return list(self.values)

    def __getitem__(self, index):
        value = self.values[index]
        return Values(value) if isinstance(value, list) else value


class PoseSyncTests(unittest.TestCase):
    def setUp(self):
        self.events = []
        self.timeline = DeferredTimeline()
        self.settings = Settings(self.events)
        self.manager = Manager(self.settings, self.events, self.timeline)
        self.scene = IsaacScene.__new__(IsaacScene)
        self.scene.manager = self.manager

    def test_cuda_readback_updates_default_ee_and_cube_pose_readers(self):
        self.scene._configure_pose_updates(self.settings)
        state = {"ee": [1.27949, 0.42191, 0.06085], "cube": [0.5, 0.0, 0.025]}
        moving = {"ee": [0.5, 0.0, 0.525], "cube": [0.5, 0.0, 0.075]}
        updates = []

        def update():
            self.timeline.apply_pending()
            updates.append(1)
            if self.settings.get_as_bool("/physics/updateToUsd") and not self.settings.get_as_bool("/physics/suppressReadback"):
                state.update(moving)

        def prim(key):
            return SimpleNamespace(get_world_poses=lambda: (Values([state[key]]), None))

        self.scene.app = SimpleNamespace(is_running=lambda: True, update=update)
        self.scene.timeline = self.timeline
        self.scene.frames = 0
        self.scene.c = {"target_position_m": [0.0, 0.0, 0.025]}
        self.timeline.get_current_time = lambda: 1.0 / 60.0
        self.scene.scenario = SimpleNamespace(_ee_prim=prim("ee"), _finger_idx=6,
            _articulation=SimpleNamespace(get_dof_positions=lambda: Values([0.0]*7)))
        self.scene.cube_prim = prim("cube")
        self.timeline.play()
        self.scene._physics_step(record=False)
        self.assertEqual(self.scene.proprioception()["ee_world_position_m"], moving["ee"])
        self.assertEqual(self.scene.private_truth()["cube_world_position_m"], moving["cube"])
        self.assertEqual(len(updates), 1)  # synchronization must not add a physics step

    def test_initialization_configures_sync_after_device_and_before_scene(self):
        events = self.events

        class Tutorial:
            _ROBOT_PRIM_PATH = "/World/ur10e_robot"
            _CUBE_PRIM_PATH = "/World/cube"
            _EE_LINK_NAME = "right_inner_finger"
            _GRIPPER_JOINT = "finger_joint"
            _OPEN_POS, _CLOSED_POS = 0.0, 0.5

            def __init__(self, **kwargs):
                events.append(("scene", None))
                self._finger_idx = 6
                self._ee_prim = Mock()
                self._articulation = SimpleNamespace(dof_names=["joint"]*7, set_dof_position_targets=Mock())

            def setup_scene(self):
                return None

            def initialize_after_play(self):
                pass

        modules = {"numpy": SimpleNamespace(array=lambda data, **kw: data),
                   "carb": SimpleNamespace(settings=SimpleNamespace(get_settings=lambda: self.settings)),
                   "omni": SimpleNamespace(timeline=SimpleNamespace(get_timeline_interface=lambda: self.timeline)),
                   "omni.timeline": SimpleNamespace(get_timeline_interface=lambda: self.timeline),
                   "isaacsim.core.simulation_manager": SimpleNamespace(SimulationManager=self.manager),
                   "isaacsim.core.experimental.prims": SimpleNamespace(GeomPrim=Mock())}
        config = load_config(ROOT / "configs/default.json")
        config["warmup_frames"] = 0
        with patch.dict("sys.modules", modules):
            with patch("visual_lab.sim.load_tutorial", return_value=(Tutorial, {})):
                with patch("visual_lab.sim.SceneCamera"), patch.object(IsaacScene, "_decorate_scene"):
                    scene = IsaacScene(Mock(), config, Path("installed-tutorial.py"), sim_device="cuda")
        self.assertEqual(events[0], ("setup", "cuda"))
        self.assertLess(events.index(("fabric", False)), events.index(("scene", None)))
        self.assertLess(events.index(("/physics/suppressReadback", False)), events.index(("scene", None)))
        self.assertEqual(scene.physics_pose_sync, {
            "pose_backend": "usd", "fabric_enabled": False, "update_to_usd": True, "suppress_readback": False})

    def test_configuration_does_not_change_device_or_step_physics(self):
        self.scene._configure_pose_updates(self.settings)
        self.assertEqual(self.events, [("fabric", False), ("/physics/suppressReadback", False)])

    def test_still_enabled_fabric_fails_instead_of_using_stale_poses(self):
        self.manager.is_fabric_enabled = lambda: True
        with self.assertRaisesRegex(LabError, "USD"):
            self.scene._configure_pose_updates(self.settings)

    def test_disabled_usd_updates_are_rejected(self):
        self.manager.enable_fabric = lambda enable: setattr(self.manager, "fabric_enabled", enable)
        with self.assertRaisesRegex(LabError, "USD"):
            self.scene._configure_pose_updates(self.settings)

    def test_suppressed_readback_is_rejected(self):
        self.settings.set_bool = lambda name, value: None
        with self.assertRaisesRegex(LabError, "USD"):
            self.scene._configure_pose_updates(self.settings)


if __name__ == "__main__":
    unittest.main()
