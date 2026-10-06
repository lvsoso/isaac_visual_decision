#!/usr/bin/env python3
"""用已安装 Isaac Sim 的 python.sh 启动。不是 Script Editor 代码。"""
from __future__ import annotations
import argparse
import json
from pathlib import Path
from visual_lab import __version__
from visual_lab.core import load_config, validate_timing
from visual_lab.upstream import find_tutorial, inspect_tutorial
from visual_lab.client import DecisionClient
from visual_lab.audit import AuditLog, sha256_file

ROOT = Path(__file__).resolve().parent


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--mode", choices=["capture", "baseline", "shadow", "visual", "mock"], default="capture")
    p.add_argument("--config", type=Path, default=ROOT/"configs/default.json")
    p.add_argument("--run-dir", required=True, type=Path, help="Must be a NEW directory")
    p.add_argument("--isaac-root")
    p.add_argument("--tutorial-script", help="Installed tutorial_9_pick_place_cumotion.py")
    p.add_argument("--headless", action="store_true", help="Auto-plays; does NOT wait for a livestream Play button")
    p.add_argument("--sim-device", choices=["cpu", "cuda"], default="cuda")
    p.add_argument("--active-gpu", type=int, default=0, help="Isaac/Kit GPU ordinal; NOT CUDA_VISIBLE_DEVICES remapping")
    p.add_argument("--endpoint", default=None)
    p.add_argument("--frame-scale", type=int, default=None)
    p.add_argument("--max-decisions", type=int, default=None)
    p.add_argument("--record-every", type=int, default=0, help="Save an RGB PNG every N physics steps; 0 disables video frames")
    p.add_argument("--xrdf-dir")
    p.add_argument("--urdf", default="robot.urdf")
    p.add_argument("--xrdf", default="robot.xrdf")
    a = p.parse_args()
    config = load_config(a.config)
    for key in ("frame_scale", "max_decisions"):
        value = getattr(a, key)
        if value is not None:
            if value < 1:
                p.error(f"--{key.replace('_','-')} must be positive")
            config[key] = value
    if a.record_every < 0 or a.active_gpu < 0:
        p.error("GPU index / record interval cannot be negative")
    validate_timing(config)
    if a.endpoint:
        config["endpoint"] = a.endpoint
    tutorial = find_tutorial(a.tutorial_script, a.isaac_root)
    metadata = inspect_tutorial(tutorial)
    client = None
    if a.mode in {"shadow", "visual", "mock"}:
        client = DecisionClient(config["endpoint"], config["http_timeout_seconds"])
        # Fail before starting Isaac or moving a robot if the service is wrong.
        client.health(allow_mock=a.mode == "mock")
    source_hashes = {str(f.relative_to(ROOT)): sha256_file(f)
                     for f in [ROOT/"run_isaac.py", *sorted((ROOT/"visual_lab").glob("*.py"))]}
    log = AuditLog(a.run_dir, {"kit_version": __version__, "mode": a.mode, "config": config,
        "target_isaac_version": "6.1.0 with compatible installed Tutorial 9",
        "upstream_tutorial": metadata, "kit_source_sha256": source_hashes,
        "record_every": a.record_every, "active_gpu_requested": a.active_gpu,
        "controller_target_source": "configured_world_coordinates", "model_input_source": "RGB + proprioception",
        "end_to_end_visual_localization": False,
        "frame_scale_note": "Default 4 is an integration budget, not the original tutorial timeout protocol"})
    app = scene = None
    try:
        # ONLY HERE initialize Kit. All omni/pxr/Isaac imports in sim.py happen afterward.
        from isaacsim import SimulationApp
        app = SimulationApp({"headless": a.headless, "hide_ui": False,
                             "active_gpu": a.active_gpu, "physics_gpu": a.active_gpu,
                             "multi_gpu": False, "renderer": "RaytracedLighting"})
        from visual_lab.sim import IsaacScene
        from visual_lab.runner import run_episode
        scene = IsaacScene(app, config, tutorial, xrdf_dir=a.xrdf_dir, urdf=a.urdf, xrdf=a.xrdf,
            sim_device=a.sim_device, record_every=a.record_every, record_directory=log.root/"frames")
        # Version reported by the loaded Python distribution, if exposed; don't invent one.
        import importlib.metadata
        try:
            runtime_version = importlib.metadata.version("isaacsim")
        except importlib.metadata.PackageNotFoundError:
            runtime_version = "not exposed by this standalone distribution; see Isaac startup log"
        log.event("runtime", isaac_distribution_version=runtime_version, source=metadata)
        result = run_episode(scene, config, a.mode, log, client, allow_mock=a.mode == "mock")
        print(json.dumps(result, ensure_ascii=False, indent=2), flush=True)
        print(f"Artifacts: {log.root}", flush=True)
        return 0 if a.mode == "capture" and result["termination_reason"] == "capture_only" or result.get("strict_success") else 2
    except Exception as exc:
        import traceback
        error = f"{type(exc).__name__}: {exc}"
        log.event("setup_error", error=error)
        log.summary({"strict_success": False, "mode": a.mode, "termination_reason": "setup_error", "error": error})
        traceback.print_exc()
        return 2
    finally:
        try:
            if scene is not None:
                scene.close()
        finally:
            log.close()
            if app is not None:
                app.close()

if __name__ == "__main__":
    raise SystemExit(main())
