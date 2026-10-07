#!/usr/bin/env python3
"""Recording-only entry: unchanged dual-view policy and admission, native PNG sampling.

Separate from the frozen original entry so historical shadow source hashes stay
unchanged. This adapter is explicitly hashed in the recording plan and manifest.
"""
import argparse,json,os
from pathlib import Path
from run_candidate import ROOT,launch_environment
from visual_lab.audit import AuditLog,sha256_file
from visual_lab.client import DecisionClient
from visual_lab.core import ProtocolError,load_config
from visual_lab.factorial import GOAL_COLORS,camera_configs
from visual_lab.candidate_control import VARIANT,check_health,code_hashes,run_candidate,validate_admission
from visual_lab.upstream import find_tutorial,inspect_tutorial

def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--mode',choices=['control'],required=True);p.add_argument('--goal-color',choices=list(GOAL_COLORS),required=True)
    p.add_argument('--run-dir',type=Path,required=True);p.add_argument('--isaac-root',required=True);p.add_argument('--headless',action='store_true')
    p.add_argument('--admission',type=Path,required=True);p.add_argument('--record-every',type=int,required=True)
    args=p.parse_args(argv)
    if args.record_every<1:p.error('Recording requires a positive physics sampling interval')
    try:environment=launch_environment(args.isaac_root,os.environ)
    except ProtocolError as exc:p.error(str(exc))
    config=load_config(ROOT/'configs/default.json');client=DecisionClient('http://127.0.0.1:8766/v1/decisions',timeout=60)
    health=check_health(client.health(allow_mock=False));proof=validate_admission(args.admission,config,health)
    tutorial=find_tutorial(None,args.isaac_root)
    log=AuditLog(args.run_dir,{'kind':'intern_dual_live','mode':'control','goal_color':args.goal_color,'variant':VARIANT,
        'config':config,'cameras':camera_configs(config),'source_sha256':code_hashes(),'model_health':health,
        'upstream_tutorial':inspect_tutorial(tutorial),'admission':proof,'model_had_control':True,
        'launch_environment':environment['before_python_sh'],'inside_isaac_ld_library_path':environment['inside_isaac_ld_library_path'],
        'record_every':args.record_every,'recording_entry_sha256':sha256_file(Path(__file__)),
        'recording_scope':'Native first-camera physics-step PNGs; API waits omitted from simulation-time playback',
        'model_input_source':'Same two live views + original Chinese relative geometry; recording adds no model input',
        'controller_target_source':'Existing configured skill targets; model selects skill only','end_to_end_visual_localization':False})
    app=scene=second=None
    try:
        from isaacsim import SimulationApp
        app=SimulationApp({'headless':args.headless,'active_gpu':0,'physics_gpu':0,'multi_gpu':False,'renderer':'RaytracedLighting'})
        from visual_lab.sim import IsaacScene
        from visual_lab.capture import SceneCamera
        scene=IsaacScene(app,config,tutorial,visual_goal_color=GOAL_COLORS[args.goal_color],
            record_every=args.record_every,record_directory=log.root/'frames')
        second=SceneCamera(camera_configs(config)[1])
        log.event('runtime',simulation_device='cuda',active_gpu=0,physics_pose_sync=scene.physics_pose_sync,controller_tool_frame=scene.scenario._tool_frame)
        result=run_candidate(scene,[scene.camera,second],config,args.goal_color,'control',log,client,admission=args.admission)
        print(json.dumps(result,ensure_ascii=False,indent=2),flush=True)
        return 0 if result['complete'] and result['strict_success'] else 2
    except Exception as exc:
        log.summary({'complete':False,'strict_success':False,'model_had_control':False,'mode':'intern_dual_control','error':f'{type(exc).__name__}: {exc}','termination_reason':'setup_error'})
        return 2
    finally:
        try:
            if second is not None:second.close()
            if scene is not None:scene.close()
        finally:
            log.close()
            if app is not None:app.close()

if __name__=='__main__':raise SystemExit(main())
