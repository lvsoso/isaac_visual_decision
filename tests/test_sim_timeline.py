"""Exercise the real adapter with Kit-style deferred timeline state changes.

These CPU doubles reproduce command ordering, not GPU physics or rendering.
"""
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

from visual_lab.core import LabError, load_config
from visual_lab.sim import IsaacScene

ROOT = Path(__file__).resolve().parents[1]


class DeferredTimeline:
    def __init__(self):
        self.playing = False
        self.pending = None

    def play(self):
        self.pending = True

    def pause(self):
        self.pending = False

    def is_playing(self):
        return self.playing

    def apply_pending(self):
        if self.pending is not None:
            self.playing = self.pending
            self.pending = None


class FakeApp:
    def __init__(self, timeline):
        self.timeline = timeline
        self.running = True
        self.updates = 0
        self.physics_updates = 0

    def is_running(self):
        return self.running

    def update(self):
        self.updates += 1
        self.timeline.apply_pending()
        if self.timeline.is_playing():
            self.physics_updates += 1


class SimTimelineTests(unittest.TestCase):
    def setUp(self):
        # Bypass native scene construction, but exercise the actual adapter methods.
        self.scene = IsaacScene.__new__(IsaacScene)
        self.scene.timeline = DeferredTimeline()
        self.scene.app = FakeApp(self.scene.timeline)
        self.scene.manager = SimpleNamespace(is_simulating=self.scene.timeline.is_playing)
        self.scene.frames = 0
        self.scene.record_every = 0
        self.scene.recorded_frames = 0
        self.scene.gripper_command = 0.0
        self.scene.c = load_config(ROOT / "configs/default.json")

    def test_play_request_is_applied_before_playing_guard(self):
        self.scene.timeline.play()
        self.assertFalse(self.scene.timeline.is_playing())
        self.scene._physics_step()
        self.assertEqual(self.scene.frames, 1)
        self.assertEqual(self.scene.app.physics_updates, 1)
        self.assertEqual(self.scene.app.updates, 1)

    def test_pending_pause_is_reported_as_timeline_pause(self):
        self.scene.timeline.playing = True
        self.scene.timeline.pause()
        with self.assertRaisesRegex(LabError, "Timeline paused"):
            self.scene._physics_step()
        self.assertEqual(self.scene.frames, 0)
        self.assertEqual(self.scene.app.physics_updates, 0)

    def test_paused_without_play_request_still_fails(self):
        with self.assertRaisesRegex(LabError, "Timeline paused"):
            self.scene._physics_step()
        self.assertEqual(self.scene.frames, 0)
        self.assertEqual(self.scene.app.physics_updates, 0)

    def test_closed_window_never_updates(self):
        self.scene.app.running = False
        self.scene.timeline.play()
        with self.assertRaisesRegex(LabError, "window was closed"):
            self.scene._physics_step()
        self.assertEqual(self.scene.app.updates, 0)

    def test_playing_without_physics_still_fails(self):
        self.scene.timeline.playing = True
        self.scene.manager.is_simulating = lambda: False
        with self.assertRaisesRegex(LabError, "Physics is not simulating"):
            self.scene._physics_step()
        self.assertEqual(self.scene.frames, 0)

    def test_recording_resumes_on_the_next_counted_update(self):
        def capture():
            self.scene.timeline.pause()
            self.scene.timeline.apply_pending()
            return b"test-frame"

        with tempfile.TemporaryDirectory() as directory:
            self.scene.record_directory = Path(directory)
            self.scene.record_every = 1
            self.scene.capture = capture
            self.scene.timeline.playing = True
            self.scene._physics_step()
            self.assertFalse(self.scene.timeline.is_playing())
            self.scene._physics_step()
            self.assertEqual(self.scene.frames, 2)
            self.assertEqual(self.scene.app.physics_updates, 2)
            self.assertEqual(self.scene.recorded_frames, 2)
            self.assertEqual(len(list(Path(directory).glob("frame_*.png"))), 2)

    def test_settle_resumes_from_pause_without_extra_updates(self):
        self.scene.c["settle_frames"] = 3
        self.scene.scenario = SimpleNamespace(_set_gripper=Mock())
        self.scene.settle()
        self.assertEqual(self.scene.frames, 3)
        self.assertEqual(self.scene.app.physics_updates, 3)
        self.assertEqual(self.scene.app.updates, 3)
        self.assertFalse(self.scene.timeline.pending)

    def test_pre_grasp_resumes_after_capture_pause(self):
        target = [0.5, 0.0, 0.5]
        controller = Mock()
        controller.reset.return_value = True
        positions = Mock()
        positions.numpy.return_value.reshape.return_value.tolist.return_value = [0.0]*6
        controller.forward.return_value = SimpleNamespace(joints=SimpleNamespace(
            positions=positions, position_indices=list(range(6))))
        articulation = Mock()
        articulation.dof_names = [f"joint_{i}" for i in range(8)]
        articulation.get_dof_positions.return_value.numpy.return_value.reshape.return_value.tolist.return_value = [0.0]*8
        self.scene.scenario = SimpleNamespace(
            _phase_ee_target=Mock(return_value=SimpleNamespace(tolist=lambda: target)),
            _articulation=articulation, _controller=controller, _finger_idx=6,
            _estimated_state=Mock(), _make_setpoint=Mock(), _set_gripper=Mock())
        self.scene._sync_world = Mock()
        self.scene.proprioception = Mock(return_value={
            "ee_world_position_m": target, "finger_joint_position_rad": 0.0})
        self.scene.frames = 120
        result = self.scene.execute("pre_grasp")
        self.assertEqual(result["status"], "reached")
        self.assertEqual(result["frames"], 1)
        self.assertEqual(self.scene.frames, 121)
        self.assertEqual(self.scene.app.physics_updates, 1)


if __name__ == "__main__":
    unittest.main()
