#!/usr/bin/env python3
"""Pinned Intern dual-view Chinese candidate; control requires both real shadow gates."""
import argparse,json,os
from pathlib import Path
from visual_lab.audit import AuditLog
from visual_lab.client import DecisionClient
from visual_lab.core import ProtocolError,load_config
from visual_lab.factorial import GOAL_COLORS,camera_configs
from visual_lab.candidate_control import VARIANT,check_health,code_hashes,run_candidate,validate_admission
from visual_lab.upstream import find_tutorial,inspect_tutorial

ROOT=Path(__file__).resolve().parent
def launch_environment(isaac_root,env):
    """Empty BEFORE python.sh; its official Isaac-owned libraries are valid AFTER."""
    if env.get('OMNI_KIT_ALLOW_ROOT')!='1' or env.get('IVD_ISAAC_PRELAUNCH_LD_LIBRARY_PATH')!='':
        raise ProtocolError('Require OMNI_KIT_ALLOW_ROOT=1 and an explicit empty pre-python.sh LD declaration')
    root=Path(isaac_root).resolve();inside=env.get('LD_LIBRARY_PATH','')
    for item in inside.split(':'):
        if item and (not Path(item).is_absolute() or not Path(item).resolve().is_relative_to(root)):
            raise ProtocolError('Post-launch library paths must belong to the configured Isaac installation')
    return {'before_python_sh':{'OMNI_KIT_ALLOW_ROOT':'1','LD_LIBRARY_PATH':''},'inside_isaac_ld_library_path':inside}

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--mode',choices=['shadow','control'],required=True)
    p.add_argument('--goal-color',choices=list(GOAL_COLORS),required=True);p.add_argument('--run-dir',type=Path,required=True)
    p.add_argument('--isaac-root',required=True);p.add_argument('--headless',action='store_true');p.add_argument('--admission',type=Path)
    p.add_argument('--check-launch-only',action='store_true',help='Verify official launcher environment only; no model HTTP, Kit, scene, motion or output directory')
    args=p.parse_args()
    try:environment=launch_environment(args.isaac_root,os.environ)
    except ProtocolError as exc:p.error(str(exc))
    if args.check_launch_only:
        print(json.dumps({'launch_check_passed':True,**environment,'model_calls':0,'simulation_app_started':False},indent=2));return 0
    if args.mode=='control' and args.admission is None:p.error('Control requires both real online shadow admission artifacts')
    config=load_config(ROOT/'configs/default.json');client=DecisionClient('http://127.0.0.1:8766/v1/decisions',timeout=60)
    health=check_health(client.health(allow_mock=False));proof=None
    if args.mode=='control':proof=validate_admission(args.admission,config,health)
    tutorial=find_tutorial(None,args.isaac_root)
    log=AuditLog(args.run_dir,{'kind':'intern_dual_live','mode':args.mode,'goal_color':args.goal_color,'variant':VARIANT,
        'config':config,'cameras':camera_configs(config),'source_sha256':code_hashes(),'model_health':health,
        'upstream_tutorial':inspect_tutorial(tutorial),'admission':proof,'model_had_control':args.mode=='control',
        'launch_environment':environment['before_python_sh'],'inside_isaac_ld_library_path':environment['inside_isaac_ld_library_path'],
        'model_input_source':'Two live simultaneous RGB images + Chinese relative geometry from configured target and measured joints; no cube truth',
        'controller_target_source':'Existing configured skill targets; model selects skill only','end_to_end_visual_localization':False})
    app=scene=second=None
    try:
        from isaacsim import SimulationApp
        app=SimulationApp({'headless':args.headless,'active_gpu':0,'physics_gpu':0,'multi_gpu':False,'renderer':'RaytracedLighting'})
        from visual_lab.sim import IsaacScene
        from visual_lab.capture import SceneCamera
        scene=IsaacScene(app,config,tutorial,visual_goal_color=GOAL_COLORS[args.goal_color]);second=SceneCamera(camera_configs(config)[1])
        log.event('runtime',simulation_device='cuda',active_gpu=0,physics_pose_sync=scene.physics_pose_sync,controller_tool_frame=scene.scenario._tool_frame)
        result=run_candidate(scene,[scene.camera,second],config,args.goal_color,args.mode,log,client,admission=args.admission)
        print(json.dumps(result,ensure_ascii=False,indent=2),flush=True)
        return 0 if result['complete'] and result['strict_success'] else 2
    except Exception as exc:
        log.summary({'complete':False,'strict_success':False,'model_had_control':False,'mode':'intern_dual_'+args.mode,'error':f'{type(exc).__name__}: {exc}','termination_reason':'setup_error'})
        return 2
    finally:
        try:
            if second is not None:second.close()
            if scene is not None:scene.close()
        finally:
            log.close()
            if app is not None:app.close()

if __name__=='__main__':raise SystemExit(main())
