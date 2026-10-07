"""One authorized SDK call with raw evidence capture; never relax replay validation."""
from __future__ import annotations
import copy,datetime,hashlib,json,math
from decimal import Decimal
from pathlib import Path
from .audit import write_json
from .client import MAX_RESPONSE_BYTES
from .core import ACTIONS,LabError
from .jev import JEV_MODEL,JEV_URL,verify_jev_response

SDK_VERSION='0.7.2'
ORIGINAL_REQUEST_SHA256='26700b30b63147c7a542b41fb6e7aa61b923fdcebc3afceaaffa113058b4d245'
RESPONSE_HEADERS=('content-type','content-encoding','date','x-typesafe-request-id','x-request-id','retry-after')

def utc():return datetime.datetime.now(datetime.timezone.utc).isoformat()

class DiagnosticCapture:
    def __init__(self,output: Path,request: dict,*,token: str):
        if (not token or set(request)!={'model','state','questions'} or request['model']!=JEV_MODEL
                or request['state'].get('camera_views')!=[] or tuple(request['questions']['next_stage']['criteria'])!=ACTIONS):
            raise LabError('Require pinned original no-image Choice request and private token')
        self.output=output;self.expected=copy.deepcopy(request);self.token=token;self.attempts=0
        output.mkdir(parents=True,exist_ok=False)
        write_json(output/'planned_request.json',request)
        write_json(output/'manifest.json',{'kind':'independent_single_jev_sdk_diagnostic','created_utc':utc(),
                   'model':JEV_MODEL,'sdk_version':SDK_VERSION,'max_network_attempts':1,'sdk_retries':0,
                   'endpoint':JEV_URL,'model_had_control':False,'new_isaac_process_started':False,
                   'source_sha256':{name:hashlib.sha256(Path(__file__).with_name(name).read_bytes()).hexdigest()
                                    for name in ['jev_diagnostic.py','jev.py','core.py']},
                   'policy':'Not part of old32batch; no remaining13calls, normalization or scoring-rule changes.'})

    def before_send(self,request):
        if self.attempts or (self.output/'CALL_STARTED.json').exists():raise LabError('One-call diagnostic budget already consumed')
        if request.method!='POST' or str(request.url)!=JEV_URL:raise LabError('Diagnostic endpoint is not the fixed official HTTPS POST')
        try:payload=json.loads(request.content)
        except (ValueError,UnicodeDecodeError):raise LabError('SDK request is not JSON') from None
        if payload!=self.expected or tuple(payload['questions']['next_stage']['criteria'])!=ACTIONS:
            raise LabError('SDK changed the frozen request or candidate order')
        # No request headers are persisted; the body must not contain authentication.
        if self.token in json.dumps(payload,ensure_ascii=False):raise LabError('Private data in outgoing diagnostic body')
        with (self.output/'CALL_STARTED.json').open('x') as f:
            json.dump({'started_utc':utc(),'budget':1,'request_body_sha256':hashlib.sha256(request.content).hexdigest()},f)
        self.attempts=1
        (self.output/'request.body').write_bytes(request.content)
        write_json(self.output/'request.json',payload)

    def record_response(self,status: int,headers,body: bytes):
        if self.attempts!=1:raise LabError('Cannot archive a response before the authorized request')
        if len(body)>MAX_RESPONSE_BYTES:raise LabError('Diagnostic response exceeds size limit')
        # Parse only for privacy checks here, not business validity. Keep exact bytes otherwise.
        if self.token.encode() in body:raise LabError('Private authentication echo; body not saved')
        try:decoded=json.loads(body)
        except (ValueError,UnicodeDecodeError):decoded=None
        if decoded is not None and self.token in json.dumps(decoded,ensure_ascii=False):
            raise LabError('Private authentication echo; body not saved')
        allowed={k:str(headers[k]) for k in RESPONSE_HEADERS if k in headers and self.token not in str(headers[k])}
        (self.output/'response.body').write_bytes(body)
        write_json(self.output/'response_meta.json',{'received_utc':utc(),'status_code':status,'headers':allowed,
                   'request_id':allowed.get('x-typesafe-request-id'),'byte_count':len(body),
                   'body_sha256':hashlib.sha256(body).hexdigest(),'saved_before_sdk_and_project_validation':True,
                   'body_representation':'Exact decoded HTTP response entity supplied to the SDK, not TLS/chunk/compressed-wire bytes'})

def audit_choice_response(raw: dict) -> dict:
    """Describe each contract separately; keep original values, never renormalize."""
    answer=raw.get('answers',{}).get('next_stage',{});probabilities=answer.get('probabilities',{})
    if not isinstance(probabilities,dict):probabilities={}
    numeric=all(type(v) in (int,float) for v in probabilities.values())
    finite=bool(probabilities) and numeric and all(math.isfinite(v) for v in probabilities.values())
    total=math.fsum(probabilities.values()) if finite else None
    decimal_total=str(sum((Decimal(str(v)) for v in probabilities.values()),Decimal(0))) if finite else None
    maximum=max(probabilities.values()) if finite else None
    safe={a:(repr(v) if type(v) is float and not math.isfinite(v) else v) for a,v in probabilities.items()}
    result={'model':raw.get('model'),'usage':raw.get('usage'),'choice':answer.get('choice'),'confidence':answer.get('confidence'),
            'probabilities':safe,'all_finite':finite,'missing_candidates':[a for a in ACTIONS if a not in probabilities],
            'extra_candidates':[a for a in probabilities if a not in ACTIONS],
            'out_of_range':{a:v for a,v in probabilities.items() if type(v) in (int,float) and math.isfinite(v) and not 0<=v<=1},
            'probability_sum':total,'probability_sum_decimal':decimal_total,'sum_error':total-1 if total is not None else None,
            'project_sum_tolerance':.001,'sum_within_project_tolerance':total is not None and abs(total-1)<=.001,
            'top_probability_ties':[a for a in ACTIONS if finite and probabilities.get(a)==maximum],
            'selected_is_argmax':finite and probabilities.get(answer.get('choice'))==maximum,
            'expected_confidence':(maximum-1/len(ACTIONS))/(1-1/len(ACTIONS)) if maximum is not None else None,
            'normalization_applied':False,'project_valid':False,'project_error':None}
    if type(answer.get('confidence')) in (int,float) and math.isfinite(answer['confidence']) and maximum is not None:
        result['confidence_formula_error']=answer['confidence']-result['expected_confidence']
    try:verify_jev_response(raw);result['project_valid']=True
    except Exception as exc:result['project_error']=f'{type(exc).__name__}: {exc}'
    return result
