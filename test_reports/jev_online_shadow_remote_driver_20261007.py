"""Operator driver: two new Isaac shadow launches maximum, stop on first error."""
import datetime,hashlib,json,os,subprocess,sys,tarfile
from pathlib import Path
ROOT=Path('/root/gpufree-share/isaac_visual_decision');sys.path.insert(0,str(ROOT))
from visual_lab.audit import sha256_file,write_json
plan_path=ROOT/'test_reports/jev_shadow_plan_20261007.json';plan=json.loads(plan_path.read_text());life_path=ROOT/'runs/jev_shadow_20261007_lifecycle.json'
assert not life_path.exists();assert all(not (ROOT/j['run_dir']).exists() for j in plan['planned_runs'])
assert subprocess.run(['git','rev-parse','HEAD'],cwd=ROOT,capture_output=True,text=True,check=True).stdout.strip()=='210f4c0926980e4e6341c1570f7159160fee7042'
assert all(sha256_file(ROOT/name)==h for name,h in plan['source_sha256'].items());assert sha256_file(ROOT/'configs/default.json')==plan['config_sha256']
env=dict(os.environ);env['OMNI_KIT_ALLOW_ROOT']='1';env['LD_LIBRARY_PATH']=''
for key in ['PYTHONPATH','PYTHONHOME']:env.pop(key,None)
def utc():return datetime.datetime.now(datetime.timezone.utc).isoformat()
def query(args):return subprocess.run(args,capture_output=True,text=True,check=True).stdout.strip()
life={'started_utc':utc(),'plan_sha256':sha256_file(plan_path),'implementation_and_freeze_commit':'210f4c0926980e4e6341c1570f7159160fee7042',
      'launch_environment':{k:env[k] for k in ['OMNI_KIT_ALLOW_ROOT','LD_LIBRARY_PATH']},'model_had_control':False,'gpu_before':query(['nvidia-smi','--query-gpu=name,memory.used','--format=csv,noheader']),
      'gpu_compute_before':query(['nvidia-smi','--query-compute-apps=pid,process_name,used_memory','--format=csv,noheader']),
      'automatic_retries':0,'max_prediction_calls':14,'runs':[],'complete':False,'driver_sha256':sha256_file(Path(__file__))}
assert life['gpu_compute_before']=='','GPU compute process already active; no launch'
write_json(life_path,life)
try:
    preflight_command=[str(Path(plan['isaac_root'])/'python.sh'),str(ROOT/'tools/preflight.py'),'--isaac-root',plan['isaac_root']]
    result=subprocess.run(preflight_command,cwd=ROOT,env=env,capture_output=True,text=True,timeout=120)
    (ROOT/'runs/jev_shadow_preflight.log').write_text(result.stdout+result.stderr);life['preflight_returncode']=result.returncode
    assert result.returncode==0,'Isaac file/environment preflight failed'
    assert '56d2128daf7b3abfeb26f909dcd656f629ac342970a736068df2a79aaf43ec15' in result.stdout,'Installed tutorial differs from prior validated capture'
    for job in plan['planned_runs']:
        color=job['color'];directory=ROOT/job['run_dir'];logfile=ROOT/'runs'/f'jev_shadow_{color}.log'
        command=[str(Path(plan['isaac_root'])/'python.sh'),str(ROOT/'run_jev_shadow.py'),'--isaac-root',plan['isaac_root'],
                 '--headless','--goal-color',color,'--run-dir',str(directory),'--worker-python',plan['worker_python'],'--key-file','/root/gpufree-share/ts.key']
        record={'color':color,'started_utc':utc(),'command':command,'run_dir':job['run_dir']};life['runs'].append(record);write_json(life_path,life)
        print('START',color,utc(),flush=True)
        with logfile.open('x') as out:process=subprocess.run(command,cwd=ROOT,env=env,stdout=out,stderr=subprocess.STDOUT,timeout=600)
        record.update(ended_utc=utc(),process_returncode=process.returncode,log_sha256=sha256_file(logfile))
        if (directory/'summary.json').exists():record['summary']=json.loads((directory/'summary.json').read_text())
        write_json(life_path,life);print(json.dumps(record,ensure_ascii=False,indent=2),flush=True)
        assert process.returncode==0 and record.get('summary',{}).get('complete') and record['summary']['strict_success'],'Run failed; no retries or remaining-color launch'
        assert record['summary']['api_attempts']==record['summary']['api_completed']==7 and record['summary']['model_had_control'] is False
        assert query(['nvidia-smi','--query-compute-apps=pid,process_name,used_memory','--format=csv,noheader'])=='','Own Isaac process did not exit cleanly'
    life['complete']=True;life['whole_pair_control_eligible']=all(r['summary']['control_gate']['eligible'] for r in life['runs'])
except Exception as exc:life['error']=f'{type(exc).__name__}: {exc}'
finally:
    life.update(ended_utc=utc(),gpu_compute_after=query(['nvidia-smi','--query-compute-apps=pid,process_name,used_memory','--format=csv,noheader']))
    write_json(life_path,life)
    archive=ROOT/'runs/jev_shadow_20261007_evidence.tar.gz'
    with tarfile.open(archive,'w:gz') as t:
        for job in life['runs']:
            path=ROOT/job['run_dir']
            if path.exists():t.add(path,arcname=path.name)
        for name in ['jev_shadow_20261007_lifecycle.json','jev_shadow_preflight.log','jev_shadow_blue.log','jev_shadow_yellow.log']:
            path=ROOT/'runs'/name
            if path.exists():t.add(path,arcname=name)
        t.add(plan_path,arcname=plan_path.name);t.add(Path(__file__),arcname='remote_driver.py')
    token=Path('/root/gpufree-share/ts.key').read_bytes().strip()
    with tarfile.open(archive) as t:
        for m in t.getmembers():
            if m.isfile():assert token not in t.extractfile(m).read(),'Private key must not leave host'
    print('ARCHIVE_SHA256',sha256_file(archive),flush=True);print(json.dumps(life,ensure_ascii=False,indent=2),flush=True)
if not life['complete']:raise SystemExit(2)
