"""Pinhole framing regression; does not validate GPU rendering or occlusion.

Uses Replicator's default horizontal aperture (20.955 mm), square pixels and
the Z-up scene. The gripper reference comes from the real 6.0.1 capture log.
"""
import itertools
import math
import unittest
from pathlib import Path

from visual_lab.core import load_config

ROOT = Path(__file__).resolve().parents[1]


def dot(a, b):
    return sum(x * y for x, y in zip(a, b))


def cross(a, b):
    return (a[1]*b[2] - a[2]*b[1], a[2]*b[0] - a[0]*b[2], a[0]*b[1] - a[1]*b[0])


def unit(v):
    length = math.sqrt(dot(v, v))
    return tuple(x / length for x in v)


class CameraFramingTests(unittest.TestCase):
    def setUp(self):
        self.config = load_config(ROOT / "configs/default.json")

    def assert_box_framed(self, center, half_size):
        camera = self.config["camera"]
        position = camera["position"]
        forward = unit(tuple(t - p for t, p in zip(camera["look_at"], position)))
        right = unit(cross(forward, (0.0, 0.0, 1.0)))
        up = cross(right, forward)
        width, height = camera["resolution"]
        focal = camera["focal_length_mm"] / 20.955
        margins = []
        for signs in itertools.product((-1, 1), repeat=3):
            relative = tuple(c + sign * half - p
                             for c, sign, half, p in zip(center, signs, half_size, position))
            depth = dot(relative, forward)
            self.assertGreater(depth, 0, "Subject must be in front of the camera")
            u = 0.5 + focal * dot(relative, right) / depth
            v = 0.5 - focal * (width / height) * dot(relative, up) / depth
            margins.extend((u, 1 - u, v, 1 - v))
        self.assertGreaterEqual(min(margins), 0.04, "Subject is clipped or too close to the image edge")

    def test_default_camera_frames_cube(self):
        half = self.config["cube_size_m"] / 2
        self.assert_box_framed(self.config["cube_position_m"], (half, half, half))

    def test_default_camera_frames_goal_outline(self):
        x, y, _ = self.config["target_position_m"]
        self.assert_box_framed((x, y, 0.0005), (0.07, 0.07, 0.0005))

    def test_default_camera_frames_observed_initial_gripper_region(self):
        # Leave 8 cm around right_inner_finger, not just its point coordinate.
        self.assert_box_framed((1.27949, 0.42191, 0.06085), (0.08, 0.08, 0.08))


if __name__ == "__main__":
    unittest.main()
