"""Official SDK integration fixtures only; zero real network calls or private keys."""
import gzip,json,sys,tempfile
from pathlib import Path
import httpx2
from visual_lab.core import ACTIONS
from tools.diagnose_jev import run

root=Path(tempfile.mkdtemp(prefix='sdk-mock-cases-',dir=Path(sys.argv[1])));key=root/'fixture.key';key.write_text('CPU-fixture-secret');request=Path('test_reports/jev_first_request_20261007.json');results={}
for case in ['nonunit_sum','gzip','http_error','non_json','secret_echo','bad_schema','oversized']:
 raw={'model':'jev-1.13.0','answers':{'next_stage':{'type':'choice','choice':'pre_grasp','confidence':0.0,'probabilities':{a:.125 for a in ACTIONS}}},'usage':{'input_tokens':100,'output_tokens':20}}
 if case=='nonunit_sum':raw['answers']['next_stage']['probabilities']['abort']=0.0
 if case=='secret_echo':raw['debug']='CPU-fixture-secret'
 if case=='bad_schema':raw['answers']['next_stage']['probabilities']='not-a-map'
 body=json.dumps(raw).encode();status=422 if case=='http_error' else 200;headers={'x-typesafe-request-id':'CPU-fixture-id','content-type':'application/json'}
 if case=='gzip':body=gzip.compress(body);headers['content-encoding']='gzip'
 if case=='non_json':body=b'fixture invalid JSON'
 if case=='oversized':body=b'x'*(2*1024*1024+1)
 calls=[]
 def fake(req):calls.append(req);return httpx2.Response(status,headers=headers,content=body)
 result=run(request,root/case,key,transport=httpx2.MockTransport(fake));assert len(calls)==1 and result['network_attempts']==1
 if case in ['secret_echo','oversized']:assert not result['raw_body_available']
 else:assert result['raw_body_available']
 if case=='gzip':assert result['sdk_call_parsed'] and result['offline_sdk_parsed'],'Decoded compressed entity must not be decoded twice'
 if case=='nonunit_sum':assert result['sdk_call_parsed'] and not result['choice_audit']['project_valid'] and result['sdk_did_not_change_probabilities']
 if case in ['http_error','non_json','bad_schema']:assert not result['sdk_call_parsed']
 results[case]={'mock_calls':len(calls),'summary':result}
Path(sys.argv[2]).write_text(json.dumps({'synthetic_fixture':True,'real_api_calls':0,'sdk_version':'0.7.2','cases':results},indent=2)+'\n');print('Seven officialSDK MockTransport cases passed; zero real HTTP calls')
