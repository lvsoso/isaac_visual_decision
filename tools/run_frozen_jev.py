#!/usr/bin/env python3
"""Run one explicitly authorized frozen14 Jev group; preserve safe HTTP evidence."""
from __future__ import annotations
import argparse,datetime,hashlib,io,json,sys,urllib.error
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from visual_lab.audit import sha256_file,write_json
from visual_lab.client import MAX_RESPONSE_BYTES
from visual_lab.core import LabError
from visual_lab.goal_binding import binding_code_hashes,binding_inputs,binding_reference,run_binding_replay,build_binding_report
from visual_lab.jev import JEV_MODEL,JEV_URL,JEV_VALIDATION_POLICY,JevClient,jev_payload

def utc():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()

class CaptureOpener:
    """Wrap existing no-redirect/no-retry transport; gate exact bytes before I/O."""
    def __init__(self,frozen: dict,output: Path,inner,*,token: str):
        jobs=frozen['planned_order'];names=[j['name'] for j in jobs]
        expected={f'{c}_images_0_decision_{s:03d}' for c in ['blue','yellow'] for s in range(1,8)}
        if len(jobs)!=14 or set(names)!=expected or set(frozen['requests'])!=expected or set(frozen['http_body_sha256'])!=expected:
            raise LabError('Require exactly14 distinct frozen English Jev requests')
        self.frozen=frozen;self.output=output;self.inner=inner;self.token=token;self.attempts=0
        output.mkdir(parents=True,exist_ok=False)

    def archive(self,path,status,headers,body):
        if len(body)>MAX_RESPONSE_BYTES:raise LabError('Jev response exceeds size limit; not archived')
        if self.token.encode() in body:raise LabError('Private authentication echo; body not archived')
        try:decoded=json.loads(body)
        except (ValueError,UnicodeDecodeError):decoded=None
        if decoded is not None and self.token in json.dumps(decoded,ensure_ascii=False):
            raise LabError('Private authentication echo; body not archived')
        headers={k.lower():str(v) for k,v in headers.items()}
        allowed={k:v for k,v in headers.items() if k in ('content-type','content-encoding','date','x-typesafe-request-id','x-request-id','retry-after') and self.token not in v}
        (path/'response.body').write_bytes(body)
        write_json(path/'response_meta.json',{'received_utc':utc(),'status_code':status,'headers':allowed,
                   'request_id':allowed.get('x-typesafe-request-id'),'byte_count':len(body),'body_sha256':hashlib.sha256(body).hexdigest(),
                   'saved_before_business_validation':True,'body_representation':'Exact HTTP entity bytes read by urllib; no reserialization or probability changes'})

    def open(self,request,*,timeout):
        if request.get_method()=='GET' and request.full_url=='https://api.typesafe.ai/v1/models':
            return self.inner.open(request,timeout=timeout)
        if request.get_method()!='POST' or request.full_url!=JEV_URL or self.attempts>=14:
            raise LabError('Frozen Jev endpoint/method or14call budget violated')
        job=self.frozen['planned_order'][self.attempts];name=job['name'];body=request.data
        if hashlib.sha256(body).hexdigest()!=self.frozen['http_body_sha256'][name] or json.loads(body)!=jev_payload(self.frozen['requests'][name]):
            raise LabError('Actual Jev HTTP body differs from next frozen request')
        path=self.output/name;path.mkdir(exist_ok=False)
        write_json(path/'CALL_STARTED.json',{'started_utc':utc(),'name':name,'attempt_index':self.attempts+1,'automatic_retries':0})
        (path/'request.body').write_bytes(body);self.attempts+=1
        try:
            with self.inner.open(request,timeout=timeout) as response:
                raw=response.read(MAX_RESPONSE_BYTES+1);self.archive(path,response.status,response.headers,raw)
        except urllib.error.HTTPError as exc:
            try:self.archive(path,exc.code,exc.headers,exc.read(MAX_RESPONSE_BYTES+1))
            finally:exc.close()
            raise
        return io.BytesIO(raw)

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ['source','reference','frozen','output','wire_output','lifecycle']:
        parser.add_argument('--'+name.replace('_','-'),type=Path,required=True)
    parser.add_argument('--key-file',type=Path,default=Path('~/.ssh/ts.key'))
    parser.add_argument('--authorize-fourteen-calls',action='store_true');args=parser.parse_args()
    if not args.authorize_fourteen_calls:parser.error('Explicit new14call authorization required')
    if args.output.exists() or args.wire_output.exists() or args.lifecycle.exists():raise FileExistsError('Independent group output already exists')
    frozen=json.loads(args.frozen.read_text())
    if (frozen['code_sha256']!=binding_code_hashes() or frozen['driver_sha256']!=sha256_file(Path(__file__))
            or frozen['model']!=JEV_MODEL or frozen['validation_policy']!=JEV_VALIDATION_POLICY or frozen['count']!=14):
        raise LabError('Frozen implementation/model/policy mismatch')
    prior=binding_reference(args.source,args.reference)
    if binding_inputs(prior,language='en')!=frozen['requests'] or prior['files_sha256']!=frozen['reference_files_sha256']:
        raise LabError('Source/reference does not reproduce frozen English requests')
    client=JevClient(key_file=args.key_file);capture=CaptureOpener(frozen,args.wire_output,client.opener,token=client.token);client.opener=capture
    life={'started_utc':utc(),'kind':'new_complete_english_jev_group','validation_policy':JEV_VALIDATION_POLICY,
          'frozen_sha256':sha256_file(args.frozen),'driver_sha256':sha256_file(Path(__file__)),'model':JEV_MODEL,
          'api_completed':0,'http_prediction_attempts':0,'complete':False,'automatic_retries':0,
          'new_isaac_process_started':False,'model_had_control':False,'old32batch_resumed':False}
    write_json(args.lifecycle,life)
    try:
        result=run_binding_replay(args.source,args.reference,args.output,client,language='en',seed=frozen['seed'])
        life.update(complete=result['complete'],api_completed=result['api_completed'],error=result['error'])
        if result['complete']:
            if client.attempts!=14 or capture.attempts!=14:raise LabError('Unexpected actual14call counters')
            build_binding_report(args.source,args.output,args.output/'report.html')
        return 0 if result['complete'] else 2
    finally:
        life.update(ended_utc=utc(),http_prediction_attempts=client.attempts,actual_transport_attempts=capture.attempts)
        write_json(args.lifecycle,life);print(json.dumps(life,ensure_ascii=False,indent=2))

if __name__=='__main__':raise SystemExit(main())
