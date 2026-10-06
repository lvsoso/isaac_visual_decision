"""CPU checks of visual-only USD goal geometry, not GPU contrast or perception."""
import copy
import math
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from visual_lab.core import LabError, load_config
from visual_lab.sim import IsaacScene
from tests.test_camera_framing import cross, dot, unit

ROOT = Path(__file__).resolve().parents[1]


class Attribute:
    def __init__(self):
        self.value = None

    def Set(self, value):
        self.value = value


class GoalVisibilityTests(unittest.TestCase):
    def test_experiment_color_is_authored_before_first_render(self):
        self.scene.visual_goal_color = [1.0, .85, .02]
        self.decorate()
        self.assertTrue(all(edge.color == [(1.0, .85, .02)] for edge in self.edges.values()))

    def setUp(self):
        self.scene = IsaacScene.__new__(IsaacScene)
        self.scene.c = load_config(ROOT / "configs/default.json")
        self.scene.scenario = SimpleNamespace(_CUBE_PRIM_PATH="/World/cube")
        self.cube_color = Attribute()
        self.cube = SimpleNamespace(IsValid=lambda: True)
        self.edges = {}
        self.stage = SimpleNamespace(GetPrimAtPath=lambda path: self.cube)

        def define(stage, path):
            edge = SimpleNamespace(size=None, color=None, translate=Attribute(), scale=Attribute())
            edge.CreateSizeAttr = lambda value: setattr(edge, "size", value)
            edge.CreateDisplayColorAttr = lambda value: setattr(edge, "color", value)
            edge.GetPrim = lambda: edge
            edge.AddTranslateOp = lambda: edge.translate
            edge.AddScaleOp = lambda: edge.scale
            self.edges[path] = edge
            return edge

        geom = SimpleNamespace(Cube=SimpleNamespace(Define=define),
            Gprim=lambda prim: SimpleNamespace(GetDisplayColorAttr=lambda: self.cube_color),
            Xformable=lambda prim: prim)
        gf = SimpleNamespace(Vec3f=lambda *v: tuple(v), Vec3d=lambda *v: tuple(v))
        usd = SimpleNamespace(get_context=lambda: SimpleNamespace(get_stage=lambda: self.stage))
        self.modules = {"omni": SimpleNamespace(usd=usd), "omni.usd": usd,
                        "pxr": SimpleNamespace(UsdGeom=geom, Gf=gf)}

    def decorate(self):
        with patch.dict("sys.modules", self.modules):
            self.scene._decorate_scene()

    def test_outline_uses_20mm_strips_without_moving_the_goal(self):
        self.decorate()
        self.assertEqual(len(self.edges), 4)
        tx, ty, _ = self.scene.c["target_position_m"]
        positions = [(tx-.06, ty, .0005), (tx+.06, ty, .0005),
                     (tx, ty-.06, .0005), (tx, ty+.06, .0005)]
        scales = [(0.02, 0.12, 0.001)]*2 + [(0.12, 0.02, 0.001)]*2
        for edge, position, scale in zip(self.edges.values(), positions, scales):
            self.assertEqual(edge.translate.value, position)
            self.assertEqual(edge.scale.value, scale)
            self.assertEqual(edge.size, 1.0)

    def test_default_projected_strip_width_exceeds_two_pixels(self):
        self.decorate()
        camera = self.scene.c["camera"]
        forward = unit(tuple(t-p for t, p in zip(camera["look_at"], camera["position"])))
        right = unit(cross(forward, (0, 0, 1)))
        up = cross(right, forward)
        width, height = camera["resolution"]
        focal = camera["focal_length_mm"] / 20.955

        def project(point):
            relative = tuple(t-p for t, p in zip(point, camera["position"]))
            depth = dot(relative, forward)
            return (width*(.5 + focal*dot(relative, right)/depth),
                    height*(.5 - focal*(width/height)*dot(relative, up)/depth))

        for edge in self.edges.values():
            center = list(edge.translate.value)
            scale = edge.scale.value
            short = 0 if scale[0] < scale[1] else 1
            long = 1-short
            a, b, end = center.copy(), center.copy(), center.copy()
            a[short] -= scale[short]/2
            b[short] += scale[short]/2
            end[long] += scale[long]/2
            pa, pb, pc, pe = project(a), project(b), project(center), project(end)
            along = [pe[i]-pc[i] for i in range(2)]
            across = [pb[i]-pa[i] for i in range(2)]
            pixels = abs(along[0]*across[1]-along[1]*across[0]) / math.hypot(*along)
            self.assertGreaterEqual(pixels, 2.0)

    def test_colors_and_configured_physics_are_unchanged(self):
        before = copy.deepcopy(self.scene.c)
        self.decorate()
        self.assertEqual(self.scene.c, before)
        self.assertEqual(self.cube_color.value, [(0.85, 0.04, 0.04)])
        for edge in self.edges.values():
            self.assertEqual(edge.color, [(0.02, 0.18, 0.95)])
            # The test double exposes only visual attrs/ops, not physics APIs.
            self.assertEqual(set(vars(edge)), {"size", "color", "translate", "scale",
                "CreateSizeAttr", "CreateDisplayColorAttr", "GetPrim", "AddTranslateOp", "AddScaleOp"})

    def test_custom_goal_position_is_used_without_a_default_coordinate(self):
        self.scene.c["target_position_m"] = [0.7, -0.3, 0.05]
        self.decorate()
        xs = [edge.translate.value[0] for edge in self.edges.values()]
        ys = [edge.translate.value[1] for edge in self.edges.values()]
        self.assertAlmostEqual(sum(xs)/4, 0.7)
        self.assertAlmostEqual(sum(ys)/4, -0.3)

    def test_missing_cube_fails_before_goal_creation(self):
        self.cube.IsValid = lambda: False
        with self.assertRaisesRegex(LabError, "cube was not created"):
            self.decorate()
        self.assertEqual(self.edges, {})


if __name__ == "__main__":
    unittest.main()
