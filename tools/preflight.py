#!/usr/bin/env python3
"""Check files and runtime BEFORE launching Isaac. No simulator/model import."""
from __future__ import annotations
import argparse
import json
import platform
import subprocess
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from visual_lab.upstream import find_tutorial, inspect_tutorial
from visual_lab.core import load_config


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--isaac-root")
    p.add_argument("--tutorial-script")
    p.add_argument("--checkpoint", type=Path)
    a = p.parse_args()
    root = Path(__file__).resolve().parents[1]
    report = {"python": sys.version, "executable": sys.executable, "platform": platform.platform()}
    c = load_config(root/"configs/default.json")
    report["timing"] = {"minimum": {"arm": c["arm_min_frames"], "gripper": c["gripper_min_frames"]},
                        "effective_phase_limits": [x*c["frame_scale"] for x in c["tutorial_phase_limits"]]}
    failures = []
    if a.isaac_root or a.tutorial_script:
        try:
            report["tutorial"] = inspect_tutorial(find_tutorial(a.tutorial_script, a.isaac_root))
            if a.isaac_root:
                launcher = Path(a.isaac_root).expanduser()/"python.sh"
                report["isaac_python_sh"] = str(launcher)
                if not launcher.is_file():
                    failures.append("No python.sh at --isaac-root; pip/source installations must supply their own supported launcher")
        except Exception as exc:
            failures.append(str(exc))
    if a.checkpoint:
        cp = a.checkpoint.expanduser().resolve()
        required = ["inference.py", "config.json", "chat_template.jinja", "tokenizer_config.json", "preprocessor_config.json"]
        report["checkpoint_files"] = {name: (cp/name).is_file() for name in required}
        if not all(report["checkpoint_files"].values()):
            failures.append("Incomplete checkpoint directory")
    try:
        result = subprocess.run(["nvidia-smi", "--query-gpu=index,name,memory.total,memory.free,driver_version", "--format=csv"],
                                text=True, capture_output=True, timeout=15)
        report["nvidia_smi"] = result.stdout.strip() or result.stderr.strip()
        report["nvidia_smi_exit_code"] = result.returncode
    except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
        report["nvidia_smi"] = str(exc)
    report["failures"] = failures
    report["gpu_simulation_validated"] = False
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 2 if failures else 0

if __name__ == "__main__":
    raise SystemExit(main())
