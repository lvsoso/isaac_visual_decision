"""Encode all actual 48 recording PNGs; add labels only, no generated motion."""
import argparse,json,subprocess
from pathlib import Path
from visual_lab.audit import sha256_file,write_json

def encode(run_dir,output,metadata):
    manifest=json.loads((run_dir/'manifest.json').read_text());summary=json.loads((run_dir/'summary.json').read_text())
    events=[json.loads(line) for line in (run_dir/'events.jsonl').read_text().splitlines()]
    assert summary['model_had_control'] and summary['complete'] and summary['strict_success']
    decisions={e['decision_id']:e for e in events if e['kind']=='decision'}
    assert len(decisions)==summary['api_completed']==summary['api_attempts']==7
    assert all(e['model_had_control'] and e['proposed_action']==e['executed_action'] for e in decisions.values())
    interval=manifest['record_every'];config=manifest['config'];fps=1/(config['physics_dt']*interval)
    ticks=list(range((config['warmup_frames']//interval+1)*interval,summary['physics_updates']+1,interval))
    paths=sorted((run_dir/'frames').glob('frame_*.png'))
    assert len(paths)==summary['recorded_frames']==len(ticks)
    assert [p.name for p in paths]==[f'frame_{i:06d}.png' for i in range(len(paths))]
    phases=[];end=config['warmup_frames']
    for event in events:
        if event['kind']!='phase_end':continue
        assert event['status']=='reached'
        start=end;end+=event['frames'];index=event['decision_id']
        if index is None:
            assert event['automatic'] and event['action']=='retract';label='Automatic retract (controller)'
        else:
            assert event['action']==decisions[index]['executed_action'];label='Model choice = '+event['action']
        phases.append((start,end,label))
    labels=[next((label for start,end,label in phases if start<tick<=end),'Settling (no new model decision)') for tick in ticks]
    groups=[]
    for i,label in enumerate(labels):
        if not groups or groups[-1]['label']!=label:groups.append({'first_video_frame':i,'last_video_frame':i,'label':label})
        else:groups[-1]['last_video_frame']=i
    font=Path('/System/Library/Fonts/Supplemental/Arial.ttf');assert font.exists()
    filters=['pad=iw:ih+96:0:40:color=0x101a20',
        f"drawtext=fontfile={font}:text='Intern-Decision-4B | MODEL CONTROL | BLUE':x=12:y=11:fontsize=17:fontcolor=white",
        f"drawtext=fontfile={font}:text='Simulation-time playback - API waits omitted':x=12:y=558:fontsize=12:fontcolor=0xb9cbd4"]
    for group in groups:
        filters.append(f"drawtext=fontfile={font}:text='{group['label']}':x=12:y=531:fontsize=17:fontcolor=0x7ee5c2:enable='between(n,{group['first_video_frame']},{group['last_video_frame']})'")
    command=['ffmpeg','-n','-hide_banner','-loglevel','error','-framerate',str(fps),'-i',str(run_dir/'frames/frame_%06d.png'),
        '-vf',','.join(filters),'-c:v','libx264','-crf','20','-pix_fmt','yuv420p','-movflags','+faststart',str(output)]
    subprocess.run(command,check=True)
    probe=json.loads(subprocess.run(['ffprobe','-v','error','-count_frames','-show_streams','-show_format','-of','json',str(output)],capture_output=True,text=True,check=True).stdout)
    video=probe['streams'][0];assert int(video['nb_read_frames'])==len(paths) and video['codec_name']=='h264'
    assert video['width']==config['camera']['resolution'][0] and video['height']==config['camera']['resolution'][1]+96
    assert abs(float(probe['format']['duration'])-len(paths)/fps)<.01
    subprocess.run(['ffmpeg','-v','error','-i',str(output),'-f','null','-'],check=True)
    write_json(metadata,{'kind':'real_model_control_recording_encode','video_sha256':sha256_file(output),'frame_count':len(paths),'fps':fps,
        'duration_seconds':len(paths)/fps,'all_native_frames_in_original_order':True,'generated_or_interpolated_motion':False,
        'api_waits_omitted':True,'warmup_not_recorded':True,'sampled_tail_physics_steps_omitted':summary['physics_updates']%interval,
        'labels_derived_from_actual_phase_events':groups,'frames_sha256':{p.name:sha256_file(p) for p in paths},'ffmpeg_command':command,
        'ffprobe':probe,'full_video_decode_passed':True,'source_manifest_sha256':sha256_file(run_dir/'manifest.json'),
        'source_summary_sha256':sha256_file(run_dir/'summary.json'),'source_events_sha256':sha256_file(run_dir/'events.jsonl')})
    print(json.dumps({'video':str(output),'frames':len(paths),'fps':fps,'seconds':len(paths)/fps,'sha256':sha256_file(output)},indent=2))

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ['run-dir','output','metadata']:parser.add_argument('--'+name,type=Path,required=True)
    encode(**vars(parser.parse_args()))
