"""Load only the installed NVIDIA tutorial class, never its standalone application.

The tutorial has import-time SimulationApp startup. A normal import would create a
second app. We compile just its top-level imports and UR10ePickPlace ClassDef,
not CLI parsing, app construction, main(), loop or finally. This is NOT a sandbox:
only a trusted local NVIDIA script should be supplied.
"""
from __future__ import annotations
import ast
import os
import types
from pathlib import Path
from .core import LabError
from .audit import sha256_file

REQUIRED_METHODS = {"__init__", "setup_scene", "initialize_after_play", "_make_setpoint", "_estimated_state", "_set_gripper", "_phase_ee_target"}
REQUIRED_CONSTANTS = {"_ROBOT_PRIM_PATH", "_CUBE_PRIM_PATH", "_EE_LINK_NAME", "_GRIPPER_JOINT", "_OPEN_POS", "_CLOSED_POS", "_TOOL_OFFSET"}
RELATIVE_SCRIPT = Path("standalone_examples/tutorials/manipulation/tutorial_9_pick_place_cumotion.py")


def find_tutorial(explicit: str | None = None, isaac_root: str | None = None) -> Path:
    if explicit:
        p = Path(explicit).expanduser().resolve()
        if not p.is_file():
            raise LabError(f"Tutorial not found: {p}")
        return p
    roots = []
    for root in (isaac_root, os.getenv("ISAAC_ROOT"), os.getcwd()):
        if root:
            roots.append(Path(root).expanduser())
    for root in roots:
        for p in (root / RELATIVE_SCRIPT, root / "source" / RELATIVE_SCRIPT):
            if p.is_file():
                return p.resolve()
    raise LabError("Cannot locate installed Tutorial 9. Set ISAAC_ROOT or pass --tutorial-script <actual path>. Do not use a random main-branch script with an older runtime.")


def inspect_tutorial(path: str | Path) -> dict:
    path = Path(path).resolve()
    source = path.read_text(encoding="utf-8-sig")
    tree = ast.parse(source, filename=str(path))
    classes = [n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "UR10ePickPlace"]
    if len(classes) != 1:
        raise LabError("Tutorial must define exactly one UR10ePickPlace class")
    cls = classes[0]
    methods = {n.name for n in cls.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}
    constants = set()
    for n in cls.body:
        targets = n.targets if isinstance(n, ast.Assign) else [n.target] if isinstance(n, ast.AnnAssign) else []
        constants.update(t.id for t in targets if isinstance(t, ast.Name))
    if REQUIRED_METHODS - methods or REQUIRED_CONSTANTS - constants:
        raise LabError(f"Unsupported tutorial API. Missing methods={sorted(REQUIRED_METHODS-methods)}, constants={sorted(REQUIRED_CONSTANTS-constants)}")
    init = next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == "__init__")
    args = {a.arg for a in init.args.args + init.args.kwonlyargs}
    required_args = {"cube_position", "target_position", "xrdf_dir", "urdf_filename", "xrdf_filename"}
    if required_args - args:
        raise LabError(f"Tutorial constructor lacks {sorted(required_args-args)}")
    constants_source = {}
    for n in cls.body:
        if isinstance(n, ast.AnnAssign) and isinstance(n.target, ast.Name):
            try:
                constants_source[n.target.id] = ast.literal_eval(n.value)
            except (ValueError, TypeError):
                pass
    return {"path": str(path), "sha256": sha256_file(path), "class_methods": sorted(methods),
            "reported_constants": constants_source,
            "note": "Local installed source is reused; its forward()/phase-convergence logic is NOT used."}


def load_tutorial(path: str | Path):
    metadata = inspect_tutorial(path)
    tree = ast.parse(Path(path).read_text(encoding="utf-8-sig"), filename=str(path))
    selected = []
    for node in tree.body:
        if isinstance(node, ast.Import):
            selected.append(node)
        elif isinstance(node, ast.ImportFrom):
            # SimulationApp is owned by run_isaac.py, not this extracted module.
            if node.module != "isaacsim":
                selected.append(node)
        elif isinstance(node, ast.ClassDef) and node.name == "UR10ePickPlace":
            selected.append(node)
    # Imports retain original relative order, including __future__ if present.
    module = types.ModuleType("visual_lab_installed_tutorial")
    module.__file__ = str(Path(path).resolve())
    compiled = compile(ast.fix_missing_locations(ast.Module(body=selected, type_ignores=[])), str(path), "exec")
    exec(compiled, module.__dict__)
    return module.UR10ePickPlace, metadata
