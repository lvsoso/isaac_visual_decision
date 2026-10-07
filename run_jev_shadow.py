#!/usr/bin/env python3
"""Isaac GPU live text-only Jev shadow; no visual/model-controlled mode exists."""
import argparse,json,os
from pathlib import Path
from visual_lab.audit import AuditLog,sha256_file
from visual_lab.core import load_config
from visual_lab.factorial import GOAL_COLORS
from visual_lab.jev_shadow import ONLINE_INSTRUCTIONS,ShadowProcessClient,run_shadow
from visual_lab.upstream import find_tutorial,inspect_tutorial

ROOT=Path(__file__).resolve().parent
def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--isaac-root',required=True);parser.add_argument('--run-dir',type=Path,required=True)
    parser.add_argument('--config',type=Path,default=ROOT/'configs/default.json');parser.add_argument('--goal-color',choices=['blue','yellow'],required=True)
    parser.add_argument('--worker-python',type=Path,required=True);parser.add_argument('--key-file',type=Path,required=True);parser.add_argument('--headless',action='store_true');args=parser.parse_args()
    if os.getenv('OMNI_KIT_ALLOW_ROOT')!='1':parser.error('Set OMNI_KIT_ALLOW_ROOT=1 before launching Isaac')
    config=load_config(args.config);tutorial=find_tutorial(None,args.isaac_root)
    log=AuditLog(args.run_dir,{'kind':'jev_online_shadow','config':config,'goal_color':args.goal_color,'upstream_tutorial':inspect_tutorial(tutorial),
        'model_had_control':False,'model_input_source':'Live text/proprioception/FK only; PNGs for audit, never sent',
        'instructions':ONLINE_INSTRUCTIONS,'source_sha256':{str(p.relative_to(ROOT)):sha256_file(p) for p in [Path(__file__),ROOT/'tools/jev_shadow_worker.py',ROOT/'tools/run_frozen_jev.py',*sorted((ROOT/'visual_lab').glob('*.py'))]},
        'worker_python':str(args.worker_python),'worker_ld_library_path':'','separate_model_process':True,'max_api_attempts':7,'automatic_retries':0})
    app=scene=None
    try:
        client=ShadowProcessClient(args.worker_python,args.key_file,log.root/'http_evidence',color=args.goal_color)
        health=client.health(allow_mock=False);log.event('pre_isaac_health',health=health)
        from isaacsim import SimulationApp
        app=SimulationApp({'headless':args.headless,'active_gpu':0,'physics_gpu':0,'multi_gpu':False,'renderer':'RaytracedLighting'})
        from visual_lab.sim import IsaacScene
        scene=IsaacScene(app,config,tutorial,visual_goal_color=GOAL_COLORS[args.goal_color])
        log.event('runtime',physics_pose_sync=scene.physics_pose_sync,controller_tool_frame=scene.scenario._tool_frame,simulation_device='cuda',active_gpu=0)
        result=run_shadow(scene,config,args.goal_color,log,client);print(json.dumps(result,ensure_ascii=False,indent=2),flush=True)
        return 0 if result['complete'] and result['strict_success'] else 2
    except Exception as exc:
        log.summary({'complete':False,'strict_success':False,'model_had_control':False,'termination_reason':'setup_error','error':f'{type(exc).__name__}: {exc}'})
        return 2
    finally:
        try:
            if scene is not None:scene.close()
        finally:
            log.close()
            if app is not None:app.close()

if __name__=='__main__':raise SystemExit(main())
