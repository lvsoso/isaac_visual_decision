"""Text-only TypeSafe Choice transport; explicit pinned model, no automatic retries."""
from __future__ import annotations
import copy,json,os,time,urllib.error,urllib.request
from pathlib import Path
from .client import MAX_RESPONSE_BYTES,ModelAPIError
from .core import ACTIONS,ProtocolError,parse_decision

JEV_MODEL='jev-1.13.0'
JEV_URL='https://api.typesafe.ai/v1/systemone'

class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs): return None

def jev_payload(request: dict) -> dict:
    if (set(request)!={'state','images','questions'} or request['images']!=[]
            or request['state'].get('camera_views')!=[] or tuple(request['questions']['next_stage']['criteria'])!=ACTIONS):
        raise ProtocolError('Jev comparison requires canonical empty-image request and unchanged eight candidates')
    return {'model':JEV_MODEL,'state':copy.deepcopy(request['state']),'questions':copy.deepcopy(request['questions'])}

def verify_jev_response(raw: dict):
    parsed=parse_decision(raw)
    if parsed.model!=JEV_MODEL or parsed.mock: raise ProtocolError('Require pinned real Jev model')
    expected=(max(parsed.probabilities.values())-1/len(ACTIONS))/(1-1/len(ACTIONS))
    if abs(parsed.confidence-expected)>1e-3: raise ProtocolError('Jev Choice confidence formula mismatch')
    usage=raw.get('usage',{})
    if any(type(usage.get(k)) is not int or usage[k]<0 for k in ['input_tokens','output_tokens']):
        raise ProtocolError('Jev token usage audit missing or invalid')
    return parsed

class JevClient:
    backend='jev'
    def __init__(self,*,token=None,key_file=None,timeout=60):
        self.token=(Path(key_file).expanduser().read_text().strip() if key_file is not None else
                    token if token is not None else os.getenv('TYPESAFE_API_KEY'))
        if not self.token or '\n' in self.token or '\r' in self.token: raise ProtocolError('Require TypeSafe API key without line breaks')
        if timeout<=0: raise ProtocolError('Require positive HTTP timeout')
        self.timeout=timeout;self.requests_completed=0;self.attempts=0;self.models=None;self.last_response=None
        self.opener=urllib.request.build_opener(urllib.request.ProxyHandler({}),NoRedirect())
    def _request(self,url,data=None):
        payload=json.dumps(data,ensure_ascii=False,allow_nan=False).encode() if data is not None else None
        req=urllib.request.Request(url,data=payload,headers={'Authorization':'Bearer '+self.token,'Accept':'application/json','Content-Type':'application/json'})
        try:
            with self.opener.open(req,timeout=self.timeout) as response: raw=response.read(MAX_RESPONSE_BYTES+1)
        except urllib.error.HTTPError as exc:
            raise ModelAPIError(f'TypeSafe HTTP {exc.code}; response body intentionally omitted') from None
        except (urllib.error.URLError,TimeoutError,OSError):
            raise ModelAPIError('TypeSafe transport failed; details intentionally omitted') from None
        if len(raw)>MAX_RESPONSE_BYTES: raise ModelAPIError('TypeSafe response exceeds size limit')
        try: result=json.loads(raw)
        except (ValueError,UnicodeDecodeError): raise ModelAPIError('TypeSafe returned invalid JSON') from None
        if not isinstance(result,dict): raise ModelAPIError('TypeSafe response is not an object')
        if self.token in json.dumps(result,ensure_ascii=False):
            raise ModelAPIError('TypeSafe response contains private authentication data; body omitted')
        return result
    def health(self,*,allow_mock=False):
        if self.models is None:
            result=self._request('https://api.typesafe.ai/v1/models')
            if not isinstance(result.get('models'),list) or not result['models']: raise ProtocolError('TypeSafe model listing missing')
            self.models=[{k:item.get(k) for k in ['name','release_date']} for item in result['models']]
        return {'backend':'jev','model':JEV_MODEL,'endpoint':JEV_URL,'is_mock':False,'supports_text_only':True,
                'busy':False,'requests_completed':self.requests_completed,'http_prediction_attempts':self.attempts,
                'model_listing':self.models,'counter_scope':'This client only, not vendor-global service count'}
    def predict(self,request):
        self.last_response=None
        data=jev_payload(request);self.attempts+=1;start=time.perf_counter();raw=self._request(JEV_URL,data)
        self.last_response=copy.deepcopy(raw)  # Safe JSON only: _request rejects secret echoes.
        verify_jev_response(raw);self.requests_completed+=1
        return raw,(time.perf_counter()-start)*1000
