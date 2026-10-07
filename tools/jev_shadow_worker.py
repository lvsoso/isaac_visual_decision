#!/usr/bin/env python3
"""Isolated seven-state shadow worker: single operation, secret never crosses IPC."""
import argparse,hashlib,io,json,sys,urllib.error
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from visual_lab.audit import write_json
from visual_lab.client import MAX_RESPONSE_BYTES
from visual_lab.core import ProtocolError
from visual_lab.jev import JevClient,JEV_URL,jev_payload
from visual_lab.jev_shadow import ONLINE_INSTRUCTIONS
from visual_lab.text_english import EN_CRITERIA
from tools.run_frozen_jev import CaptureOpener

class OnlineCapture:
    def __init__(self,inner,token,request,output):
        self.inner=inner;self.token=token;self.expected=json.dumps(jev_payload(request),ensure_ascii=False,allow_nan=False).encode();self.output=output;self.called=False
        output.parent.mkdir(parents=True,exist_ok=True);output.mkdir(exist_ok=False)
    def open(self,request,*,timeout):
        if self.called or request.get_method()!='POST' or request.full_url!=JEV_URL or request.data!=self.expected:
            raise ProtocolError('Online single-call frozen HTTP body gate violated')
        self.called=True;write_json(self.output/'CALL_STARTED.json',{'automatic_retries':0,'request_body_sha256':hashlib.sha256(request.data).hexdigest()})
        (self.output/'request.body').write_bytes(request.data)
        try:
            with self.inner.open(request,timeout=timeout) as response:
                raw=response.read(MAX_RESPONSE_BYTES+1);CaptureOpener.archive(self,self.output,response.status,response.headers,raw)
        except urllib.error.HTTPError as exc:
            try:CaptureOpener.archive(self,self.output,exc.code,exc.headers,exc.read(MAX_RESPONSE_BYTES+1))
            finally:exc.close()
            raise
        return io.BytesIO(raw)

def perform(client,message,color,capture_dir):
    if message['op']=='health':return {'ok':True,'health':client.health(allow_mock=False)}
    request=message.get('request')
    if message['op']!='predict' or not isinstance(request,dict):raise ProtocolError('Unsupported isolated worker operation')
    if (request['state'].get('task')!=f'Place the red cube inside the {color} square ground outline, then release it.'
            or request['questions']!={'next_stage':{'type':'choice','instructions':ONLINE_INSTRUCTIONS,'criteria':EN_CRITERIA}}):
        raise ProtocolError('Online shadow English template changed')
    client.opener=OnlineCapture(client.opener,client.token,request,capture_dir)
    raw,_=client.predict(request);return {'ok':True,'response':raw}

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--key-file',type=Path,required=True);parser.add_argument('--goal-color',choices=['blue','yellow'],required=True);parser.add_argument('--capture-dir',type=Path);args=parser.parse_args()
    try:
        data=sys.stdin.buffer.read(MAX_RESPONSE_BYTES+1)
        if len(data)>MAX_RESPONSE_BYTES:raise ProtocolError('IPC body exceeds size limit')
        message=json.loads(data);client=JevClient(key_file=args.key_file,timeout=60)
        result=perform(client,message,args.goal_color,args.capture_dir);code=0
    except Exception as exc:result={'ok':False,'error_class':type(exc).__name__};code=2
    print(json.dumps(result,ensure_ascii=False,allow_nan=False),flush=True);return code

if __name__=='__main__':raise SystemExit(main())
