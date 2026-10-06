import tempfile
import unittest
from pathlib import Path
from visual_lab.upstream import *

# Deliberately synthetic contract fixture, not NVIDIA code or a simulated robot.
FIXTURE='''
import math
raise RuntimeError("top-level app startup MUST NOT run")
class UR10ePickPlace:
    _ROBOT_PRIM_PATH="/World/ur10e_robot"
    _CUBE_PRIM_PATH="/World/cube"
    _EE_LINK_NAME="right_inner_finger"
    _GRIPPER_JOINT="finger_joint"
    _OPEN_POS: float=0.0
    _CLOSED_POS: float=0.5
    _TOOL_OFFSET={"tool0":0.0}
    def __init__(self, cube_position=None, target_position=None, xrdf_dir=None, urdf_filename=None, xrdf_filename=None): pass
    async def setup_scene(self): pass
    def initialize_after_play(self): pass
    def _make_setpoint(self): pass
    def _estimated_state(self): return math.sqrt(4)
    def _set_gripper(self): pass
    def _phase_ee_target(self): pass
'''

class UpstreamTests(unittest.TestCase):
    def setUp(self):
        self.t=tempfile.TemporaryDirectory()
        self.p=Path(self.t.name)/"tutorial.py"; self.p.write_text(FIXTURE)
    def tearDown(self): self.t.cleanup()
    def test_ast_contract_validation(self):
        m=inspect_tutorial(self.p); self.assertEqual(len(m["sha256"]),64)
    def test_main_and_top_level_not_executed(self):
        cls,m=load_tutorial(self.p)
        self.assertEqual(cls()._estimated_state(),2)
    def test_missing_method_fails_early(self):
        self.p.write_text(FIXTURE.replace("def _set_gripper", "def changed"))
        with self.assertRaises(LabError): inspect_tutorial(self.p)
    def test_missing_constructor_argument_fails(self):
        self.p.write_text(FIXTURE.replace("cube_position=None", "changed=None"))
        with self.assertRaises(LabError): inspect_tutorial(self.p)
    def test_missing_path(self):
        with self.assertRaises(LabError): find_tutorial(str(self.p)+"missing")
    def test_source_layout_discovery(self):
        p=Path(self.t.name)/"source"/RELATIVE_SCRIPT
        p.parent.mkdir(parents=True); p.write_text(FIXTURE)
        self.assertEqual(find_tutorial(isaac_root=self.t.name),p.resolve())

if __name__ == "__main__": unittest.main()
