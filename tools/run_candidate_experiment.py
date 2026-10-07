#!/usr/bin/env python3
"""Single authorized experiment: two live shadows, then two gated skill-control runs."""
import argparse,datetime,json,os,socket,subprocess,sys,tarfile,time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from visual_lab.audit import sha256_file,write_json
from visual_lab.candidate_control import check_health,code_hashes,write_admission,validate_admission
from visual_lab.client import DecisionClient
from visual_lab.core import load_config
from visual_lab.core import ProtocolError

ROOT=Path(__file__).resolve().parents[1]
def utc():return datetime.datetime.now(datetime.timezone.utc).isoformat()
def query(args):return subprocess.run(args,capture_output=True,text=True,check=True).stdout.strip()

def gpu_pids(report):
    pids=[]
    for line in report.splitlines():
        value=line.split(',',1)[0].strip()
        if not value.isdecimal() or int(value)<=0:raise ProtocolError('GPU process report has an invalid host PID')
        pids.append(int(value))
    if len(set(pids))!=len(pids):raise ProtocolError('Duplicate GPU process host PID')
    return sorted(pids)

def gpu_baseline(report,*,container_service_pid):
    host_pids=gpu_pids(report)
    if len(host_pids)!=1:raise ProtocolError('Require exactly one model GPU process after an idle precheck')
    return {'container_service_pid':container_service_pid,'host_gpu_pids':host_pids,'initial_compute_report':report,
        'accounting':'NVML host PID identity pinned after only our service starts; never compare to container namespace PID'}

def verify_gpu_after_episode(baseline,report):
    observed=gpu_pids(report)
    if observed!=baseline['host_gpu_pids']:
        raise ProtocolError(f'GPU process identities changed: expected host PIDs {baseline["host_gpu_pids"]}, observed {observed}')
    return {'container_service_pid':baseline['container_service_pid'],'observed_host_gpu_pids':observed,
        'observed_compute_report':report,'only_pinned_model_gpu_process_remains':True}

def execute(plan_path):
    plan=json.loads(plan_path.read_text());out=ROOT/plan['experiment_dir']
    assert not out.exists(),'Fresh experiment outputs required'
    assert all(not (ROOT/job['run_dir']).exists() for job in plan['runs'])
    assert all(sha256_file(ROOT/name)==h for name,h in plan['source_sha256'].items()),'Frozen source changed'
    assert sha256_file(ROOT/'configs/default.json')==plan['config_sha256']
    subprocess.run(['git','diff','--quiet'],cwd=ROOT,check=True);subprocess.run(['git','diff','--cached','--quiet'],cwd=ROOT,check=True)
    assert query(['nvidia-smi','--query-compute-apps=pid,process_name','--format=csv,noheader'])=='','GPU busy before launch'
    with socket.socket() as sock:assert sock.connect_ex(('127.0.0.1',8766))!=0,'Loopback model port occupied'
    out.mkdir();life={'kind':'intern_dual_live_authorized_experiment','started_utc':utc(),'plan_sha256':sha256_file(plan_path),
        'git_head':query(['git','-C',str(ROOT),'rev-parse','HEAD']),'gpu_before':query(['nvidia-smi','--query-gpu=name,memory.used','--format=csv,noheader']),
        'gpu_compute_before':'','source_sha256':code_hashes(),'automatic_retries':0,'runs':[],'complete':False,'control_started':False}
    life_path=out/'lifecycle.json';write_json(life_path,life);service=None;child=None;child_stream=None;service_stream=None
    env=dict(os.environ);env['OMNI_KIT_ALLOW_ROOT']='1';env['LD_LIBRARY_PATH']=''
    env['IVD_ISAAC_PRELAUNCH_LD_LIBRARY_PATH']=env['LD_LIBRARY_PATH']
    for key in ['PYTHONPATH','PYTHONHOME']:env.pop(key,None)
    life['launch_environment']={k:env[k] for k in ['OMNI_KIT_ALLOW_ROOT','LD_LIBRARY_PATH']}
    client=DecisionClient('http://127.0.0.1:8766/v1/decisions',timeout=60)
    try:
        preflight=subprocess.run([plan['isaac_python'],str(ROOT/'tools/preflight.py'),'--isaac-root',plan['isaac_root']],env=env,cwd=ROOT,capture_output=True,text=True,timeout=120)
        (out/'preflight.log').write_text(preflight.stdout+preflight.stderr);assert preflight.returncode==0,'Isaac preflight failed'
        assert plan['tutorial_sha256'] in preflight.stdout,'Installed tutorial changed'
        command=[plan['model_python'],'-u',str(ROOT/'serve_model.py'),'--checkpoint',plan['checkpoint'],
            '--trust-model-code','--expected-inference-sha256',plan['inference_sha256'],'--device','cuda','--dtype','bfloat16',
            '--max-length','8192','--host','127.0.0.1','--port','8766']
        life['service_command']=command;service_stream=(out/'service.log').open('x')
        service=subprocess.Popen(command,env=env,cwd=ROOT,stdout=service_stream,stderr=subprocess.STDOUT);life['service_pid']=service.pid
        deadline=time.monotonic()+180
        while True:
            assert service.poll() is None,'Own service exited before ready'
            try:health=check_health(client.health());break
            except Exception:
                if time.monotonic()>deadline:raise
                time.sleep(1)
        assert health['requests_completed']==0;life['initial_health']=health;write_json(life_path,life)
        baseline_report=query(['nvidia-smi','--query-compute-apps=pid,process_name,used_memory','--format=csv,noheader'])
        life['gpu_service_baseline']=gpu_baseline(baseline_report,container_service_pid=service.pid);write_json(life_path,life)
        for job in plan['runs']:
            assert all(sha256_file(ROOT/name)==h for name,h in plan['source_sha256'].items()),'Source changed during experiment'
            if job['mode']=='control':
                if not life.get('admission_created'):
                    try:
                        proof=write_admission([ROOT/j['run_dir'] for j in plan['runs'] if j['mode']=='shadow'],out/'admission.json',load_config(ROOT/'configs/default.json'),client.health())
                        life['admission_created']=True;life['admission_sha256']=sha256_file(out/'admission.json')
                    except Exception as exc:
                        life['admission_created']=False;life['gate_rejection']=f'{type(exc).__name__}: {exc}';life['complete']=True
                        print('CONTROL_NOT_STARTED: dual-shadow admission rejected',flush=True);break
                validate_admission(out/'admission.json',load_config(ROOT/'configs/default.json'),client.health())
                life['control_started']=True
            command=[plan['isaac_python'],str(ROOT/'run_candidate.py'),'--isaac-root',plan['isaac_root'],'--headless',
                '--mode',job['mode'],'--goal-color',job['color'],'--run-dir',str(ROOT/job['run_dir'])]
            if job['mode']=='control':command+=['--admission',str(out/'admission.json')]
            health=check_health(client.health());before=health['requests_completed']
            record={**job,'started_utc':utc(),'service_count_before':before,'command':command};life['runs'].append(record);write_json(life_path,life)
            print('START',job['mode'],job['color'],utc(),flush=True)
            child_stream=(out/(Path(job['run_dir']).name+'.log')).open('x')
            child=subprocess.Popen(command,env=env,cwd=ROOT,stdout=child_stream,stderr=subprocess.STDOUT);record['isaac_process_pid']=child.pid
            returncode=child.wait(timeout=900);child_stream.close();child_stream=None
            record.update(process_returncode=returncode,ended_utc=utc(),service_count_after=check_health(client.health())['requests_completed'])
            summary_path=ROOT/job['run_dir']/'summary.json'
            if summary_path.exists():record['summary']=json.loads(summary_path.read_text())
            write_json(life_path,life);print(json.dumps(record,ensure_ascii=False,indent=2),flush=True)
            assert returncode==0 and record.get('summary',{}).get('complete') and record['summary']['strict_success'],'First failed episode stops remaining launches; no fallback or retry'
            assert record['service_count_after']-before==record['summary']['api_completed']==record['summary']['api_attempts']
            assert record['summary']['api_attempts']<=job['max_decisions']
            report=query(['nvidia-smi','--query-compute-apps=pid,process_name,used_memory','--format=csv,noheader'])
            record['gpu_compute_after_isaac_exit']=report;write_json(life_path,life)
            record['gpu_after_isaac_verified']=verify_gpu_after_episode(life['gpu_service_baseline'],report);write_json(life_path,life)
        else:life['complete']=True
        life['final_health']=check_health(client.health());life['prediction_calls']=life['final_health']['requests_completed']
        assert life['prediction_calls']<=34
    except BaseException as exc:
        life['error']=f'{type(exc).__name__}: {exc}'
    finally:
        # Only exact PIDs created above; never kill unrelated GPU/SSH/Notebook work.
        for name,process in [('isaac',child),('service',service)]:
            if process is not None:
                if process.poll() is None:
                    process.terminate()
                    try:process.wait(timeout=30)
                    except subprocess.TimeoutExpired:process.kill();process.wait(timeout=10)
                life[name+'_returncode']=process.returncode
        if child_stream is not None:child_stream.close()
        if service_stream is not None:service_stream.close()
        life.update(ended_utc=utc(),gpu_compute_after=query(['nvidia-smi','--query-compute-apps=pid,process_name,used_memory','--format=csv,noheader']),own_processes_closed=True)
        write_json(life_path,life);archive=out/'evidence.tar.gz'
        with tarfile.open(archive,'w:gz') as t:
            for record in life['runs']:
                path=ROOT/record['run_dir']
                if path.exists():t.add(path,arcname=path.name)
            for path in sorted(out.iterdir()):
                if path!=archive and path.is_file():t.add(path,arcname='experiment/'+path.name)
            t.add(plan_path,arcname='experiment/plan.json');t.add(Path(__file__),arcname='experiment/actual_driver.py')
        print('ARCHIVE_SHA256',sha256_file(archive),flush=True);print(json.dumps(life,ensure_ascii=False,indent=2),flush=True)
    return 0 if life['complete'] and 'error' not in life else 2

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--plan',type=Path,required=True)
    raise SystemExit(execute(parser.parse_args().plan))
