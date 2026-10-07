#!/usr/bin/env python3
"""Only with --authorize-one-call: same frozen request, official SDK, no retries."""
import argparse,hashlib,importlib.metadata,json,logging,os,sys,time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from visual_lab.audit import write_json,sha256_file
from visual_lab.core import LabError
from visual_lab.client import MAX_RESPONSE_BYTES
from visual_lab.jev import JEV_MODEL
from visual_lab.jev_diagnostic import DiagnosticCapture,SDK_VERSION,ORIGINAL_REQUEST_SHA256,audit_choice_response,utc

def run(request_path: Path,output: Path,key_file: Path,*,transport=None):
    if sha256_file(request_path)!=ORIGINAL_REQUEST_SHA256:raise LabError('Require the exact originally frozen request file')
    if importlib.metadata.version('typesafe-sdk')!=SDK_VERSION:raise LabError('Require pinned typesafe-sdk0.7.2')
    os.environ['TYPESAFE_LOG_LEVEL']='off'
    for name in ['typesafe_sdk','httpx2','httpcore2']:logging.getLogger(name).disabled=True
    import httpx2
    from typesafe_sdk import RetryPolicy,SystemOneResponse,TypeSafeClient
    request=json.loads(request_path.read_text());token=key_file.expanduser().read_text().strip()
    capture=DiagnosticCapture(output,request,token=token);start=time.perf_counter()
    inner=transport if transport is not None else httpx2.HTTPTransport(retries=0,trust_env=False)
    class CapturingTransport(httpx2.BaseTransport):
        def handle_request(self,req):
            capture.before_send(req)
            response=inner.handle_request(req);chunks=[];count=0
            try:
                for chunk in response.iter_bytes():
                    count+=len(chunk)
                    if count>MAX_RESPONSE_BYTES:raise LabError('Diagnostic response exceeds size limit')
                    chunks.append(chunk)
                body=b''.join(chunks);capture.record_response(response.status_code,response.headers,body)
                decoded_headers=dict(response.headers)
                for name in ['content-encoding','content-length']:decoded_headers.pop(name,None)
                return httpx2.Response(response.status_code,headers=decoded_headers,content=body,request=req)
            finally:response.close()
        def close(self):inner.close()
    result={'kind':'independent_single_jev_sdk_diagnostic','sdk_version':SDK_VERSION,'source_request_sha256':sha256_file(request_path),
            'started_utc':utc(),'network_attempts':0,'automatic_retries':0,'sdk_call_parsed':False,
            'sdk_error_class':None,'raw_body_available':False,'normalization_applied':False,'model_had_control':False}
    try:
        http=httpx2.Client(transport=CapturingTransport(),trust_env=False,follow_redirects=False,timeout=60)
        with TypeSafeClient(api_key=token,model=JEV_MODEL,base_url='https://api.typesafe.ai',
                            retry=RetryPolicy(max_retries=0),http_client=http) as client:
            response=client.system_one(state=request['state'],questions=request['questions'],model=JEV_MODEL)
            result['sdk_call_parsed']=True
    except Exception as exc:result['sdk_error_class']=type(exc).__name__  # No unsafe SDK error repr/body/headers.
    result.update(network_attempts=capture.attempts,ended_utc=utc(),elapsed_ms=(time.perf_counter()-start)*1000)
    if (output/'response.body').exists():
        result['raw_body_available']=True;body=(output/'response.body').read_bytes();meta=json.loads((output/'response_meta.json').read_text())
        result['response_meta']=meta
        try:
            raw=json.loads(body);write_json(output/'response.json',raw);result['choice_audit']=audit_choice_response(raw)
        except (ValueError,UnicodeDecodeError,AttributeError,TypeError):result['choice_audit_error']='Response JSON does not expose the expected Choice shape'
        try:
            # Re-parse the SAME captured response offline, no additional HTTP request.
            decoded_headers={k:v for k,v in meta['headers'].items() if k!='content-encoding'}
            parsed=SystemOneResponse.from_http_response(httpx2.Response(meta['status_code'],headers=decoded_headers,content=body))
            parsed_data=parsed.model_dump(mode='json');write_json(output/'sdk_parsed.json',parsed_data)
            result['offline_sdk_parsed']=True;result['sdk_did_not_change_probabilities']=(parsed_data['answers']['next_stage']['probabilities']==raw['answers']['next_stage']['probabilities'])
        except Exception as exc:result['offline_sdk_parsed']=False;result['offline_sdk_error_class']=type(exc).__name__
    result['diagnostic_capture_complete']=capture.attempts==1 and result['raw_body_available']
    write_json(output/'summary.json',result);return result

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--request',type=Path,default=Path('test_reports/jev_first_request_20261007.json'))
    p.add_argument('--output',type=Path,required=True);p.add_argument('--key-file',type=Path,default=Path('~/.ssh/ts.key'));p.add_argument('--authorize-one-call',action='store_true');a=p.parse_args()
    if not a.authorize_one_call:p.error('Explicit one-call authorization required; this is not a replay retry')
    result=run(a.request,a.output,a.key_file);print(json.dumps(result,ensure_ascii=False,allow_nan=False,indent=2))
    return 0 if result['diagnostic_capture_complete'] else 2

if __name__=='__main__':raise SystemExit(main())
