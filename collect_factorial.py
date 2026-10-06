#!/usr/bin/env python3
"""Isaac GPU: one STATIC color and simultaneous views along a fixed trajectory."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
from visual_lab.audit import AuditLog, sha256_file
from visual_lab.core import load_config
from visual_lab.factorial import GOAL_COLORS, camera_configs, collect_episode
from visual_lab.upstream import find_tutorial, inspect_tutorial

ROOT = Path(__file__).resolve().parent


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--config', type=Path, default=ROOT/'configs/default.json')
    p.add_argument('--run-dir', type=Path, required=True)
    p.add_argument('--isaac-root', required=True)
    p.add_argument('--headless', action='store_true')
    p.add_argument('--goal-color', choices=list(GOAL_COLORS), required=True)
    a = p.parse_args()
    config = load_config(a.config)
    tutorial = find_tutorial(None, a.isaac_root)
    log = AuditLog(a.run_dir, {'kind': 'static_color_capture', 'static_goal_color': a.goal_color, 'config': config,
        'cameras': camera_configs(config), 'goal_colors': GOAL_COLORS, 'render_settle_steps_per_color': 3,
        'upstream_tutorial': inspect_tutorial(tutorial), 'model_had_control': False,
        'source_sha256': {str(path.relative_to(ROOT)): sha256_file(path) for path in
            [Path(__file__), *sorted((ROOT/'visual_lab').glob('*.py'))]}})
    app = scene = second = None
    try:
        from isaacsim import SimulationApp
        app = SimulationApp({'headless': a.headless, 'active_gpu': 0, 'physics_gpu': 0,
                             'multi_gpu': False, 'renderer': 'RaytracedLighting'})
        from visual_lab.sim import IsaacScene
        from visual_lab.capture import SceneCamera
        scene = IsaacScene(app, config, tutorial, visual_goal_color=GOAL_COLORS[a.goal_color])
        second = SceneCamera(camera_configs(config)[1])
        result = collect_episode(scene, [scene.camera, second], config, log, static_color=a.goal_color)
        print(json.dumps(result, indent=2))
        return 0 if result['complete'] and result['strict_success'] else 2
    except Exception as exc:
        log.summary({'complete': False, 'strict_success': False, 'error': f'{type(exc).__name__}: {exc}'})
        raise
    finally:
        try:
            if second is not None:
                second.close()
            if scene is not None:
                scene.close()
        finally:
            log.close()
            if app is not None:
                app.close()


if __name__ == '__main__':
    raise SystemExit(main())
