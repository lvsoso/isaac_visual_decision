#!/usr/bin/env python3
"""Freeze all42canonical and transport requests before any model inference."""
import argparse,datetime,hashlib,json,random,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from visual_lab.audit import sha256_file,write_json
from visual_lab.core import LabError
from visual_lab.goal_binding import binding_reference,binding_inputs,binding_code_hashes
from visual_lab.jev import jev_payload

def body_sha256(request):
    return hashlib.sha256(json.dumps(request,ensure_ascii=False,allow_nan=False).encode()).hexdigest()

def freeze_text_study(source: Path,reference: Path,output: Path,*,allow_mock=False,seed=20261006) -> dict:
    if output.exists():raise FileExistsError(output)
    prior=binding_reference(source,reference,allow_mock=allow_mock)
    zh=binding_inputs(prior,language='zh');en=binding_inputs(prior,language='en')
    groups={'zh':zh,'en':en,'jev':en};order=[];hashes={};wire_hashes={};body_hashes={}
    output.mkdir(parents=True,exist_ok=False)
    for group,requests in groups.items():
        (output/group/'requests').mkdir(parents=True);(output/group/'wire_requests').mkdir()
        hashes[group]={};wire_hashes[group]={};body_hashes[group]={}
        jobs=[{'group':group,'name':r['name'],'cell':r['cell'],'decision_id':r['decision_id'],'image_count':0} for r in prior['rows']]
        random.Random(seed).shuffle(jobs);order.extend(jobs)
        for name,request in requests.items():
            wire=jev_payload(request) if group=='jev' else request
            write_json(output/group/'requests'/(name+'.json'),request);write_json(output/group/'wire_requests'/(name+'.json'),wire)
            hashes[group][name]=sha256_file(output/group/'requests'/(name+'.json'))
            wire_hashes[group][name]=sha256_file(output/group/'wire_requests'/(name+'.json'))
            body_hashes[group][name]=body_sha256(wire)
    result={'frozen_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'synthetic_fixture':allow_mock,
            'requests':groups,'planned_order':order,'request_sha256':hashes,'wire_request_sha256':wire_hashes,
            'http_body_sha256':body_hashes,'code_sha256':binding_code_hashes(),
            'freeze_tool_sha256':sha256_file(Path(__file__)),'reference_files_sha256':prior['files_sha256'],
            'seed':seed,'count':42,'model_had_control':False,'policy':'No retries or prompt edits after first inference. Groups zh, en, jev; within-group fixed color/state shuffle. HTTP body hashes exclude secret headers.'}
    write_json(output/'manifest.json',result);return result

def verify_study_request(frozen: dict,group: str,name: str,request: dict):
    if request!=frozen['requests'][group][name]:raise LabError('Frozen study input changed')
    wire=jev_payload(request) if group=='jev' else request
    if body_sha256(wire)!=frozen['http_body_sha256'][group][name]:raise LabError('Frozen study HTTP body changed')

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('source',type=Path);p.add_argument('reference',type=Path);p.add_argument('output',type=Path);a=p.parse_args()
    r=freeze_text_study(a.source,a.reference,a.output);print(json.dumps({k:v for k,v in r.items() if k!='requests'},ensure_ascii=False,indent=2))

if __name__=='__main__':main()
