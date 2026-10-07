"""Single-field goal identity correction and frozen14-request text-only replay."""
from __future__ import annotations
import copy,html,json,random
from pathlib import Path
from .audit import sha256_file,write_json
from .core import ACTIONS,LabError,ProtocolError
from .image_ablation import IMAGE_HEALTH_KEYS,image_request,image_source_hashes,verify_image_response
from .prompt_variants import validate_capture,source_hashes
from .protocol import validate_request

def binding_request(request: dict,color: str) -> dict:
    word={'blue':'蓝色','yellow':'黄色'}.get(color)
    if (word is None or request.get('images')!=[] or request['state'].get('camera_views')!=[]
            or request['state'].get('task')!=f'将红色方块放入地面{word}方形轮廓线内部，然后释放它。'
            or not isinstance(request['state'].get('goal_guidance',{}).get('spatial_description'),str)):
        raise ProtocolError('Require known task/color, no images/cameras and spatial description')
    result=copy.deepcopy(request)
    result['state']['goal_guidance']['spatial_description']=(f'task中的{word}方形轮廓线就是本goal_guidance中配置的地面框；“内部”指该轮廓线围成的地面区域。'+result['state']['goal_guidance']['spatial_description'])
    validate_request(result,allow_empty_images=True)
    return result

def binding_code_hashes():
    return {**image_source_hashes(),**{n:sha256_file(Path(__file__).with_name(n)) for n in ['goal_binding.py','text_english.py','jev.py']}}

def binding_reference(source: Path,reference: Path,*,allow_mock=False) -> dict:
    bundle,_=validate_capture(source,allow_mock=allow_mock)
    if (reference/'INVALIDATED.json').exists(): raise LabError('Invalidated reference')
    m=json.loads((reference/'manifest.json').read_text());s=json.loads((reference/'summary.json').read_text())
    if (not s.get('complete') or s.get('api_completed')!=42 or len(s.get('decisions',[]))!=42 or s.get('prompt_policy')!='modality_aware_v1'
            or s.get('mock_backend') is not bool(allow_mock) or m.get('synthetic_fixture') is not bool(allow_mock)):
        raise LabError('Require complete correctly marked modality-aware reference')
    if m['source_files_sha256']!=source_hashes(source): raise LabError('Reference capture hash mismatch')
    rows=[];requests={};responses={}
    for row in s['decisions']:
        if row['image_count']!=0: continue
        name=row['name'];record=bundle['records'][row['decision_id']-1];color=row['cell'].split('_')[0]
        for directory,key in [('requests','request'),('responses','response')]:
            if sha256_file(reference/directory/(name+'.json'))!=row[key+'_sha256']: raise LabError('Reference artifact hash mismatch')
        old=json.loads((reference/'requests'/(name+'.json')).read_text());raw=json.loads((reference/'responses'/(name+'.json')).read_text())
        pngs=[(source/a['path']).read_bytes() for a in record['images'][color]]
        expected=image_request(pngs,record['model_state'],bundle['view_metadata'],record['goal_guidance'],{'color':color,'views':0},prompt_policy='modality_aware_v1')
        parsed=verify_image_response([],raw,m['model_health'],allow_mock=allow_mock)
        if old!=expected or row['expected_action']!=record['expected_action'] or parsed.action!=row['proposed_action'] or parsed.probabilities!=row['probabilities']:
            raise LabError('Reference construction/response mismatch')
        rows.append(copy.deepcopy(row));requests[name]=old;responses[name]=raw
    if len(rows)!=14 or {(r['cell'],r['decision_id']) for r in rows}!={(f'{c}_images_0',j) for c in ['blue','yellow'] for j in range(1,8)}:
        raise LabError('Require14distinct no-image reference decisions')
    return {'rows':rows,'requests':requests,'responses':responses,'model_health':m['model_health'],
            'files_sha256':{n:sha256_file(reference/n) for n in ['manifest.json','summary.json']}}

def binding_inputs(reference: dict,*,language='zh') -> dict:
    if language not in {'zh','en'}: raise ProtocolError('Unknown binding language')
    requests={}
    for row in reference['rows']:
        color=row['cell'].split('_')[0];request=binding_request(reference['requests'][row['name']],color)
        if language=='en':
            from .text_english import english_request
            request=english_request(request,color)
        requests[row['name']]=request
    return requests

def binding_summary(rows: list[dict],reference: dict) -> list[dict]:
    cells=[]
    for color in ['blue','yellow']:
        selected=sorted((r for r in rows if r['cell']==color+'_images_0'),key=lambda r:r['decision_id'])
        old=[r for r in reference['rows'] if r['cell']==color+'_images_0']
        cells.append({'id':color+'_images_0','color':color,'num_decisions':len(selected),
                      'baseline_agreement':sum(r['proposed_action']==r['expected_action'] for r in selected),
                      'old_agreement':sum(r['proposed_action']==r['expected_action'] for r in old),
                      'proposed_actions':[r['proposed_action'] for r in selected]})
    return cells

def run_binding_replay(source: Path,reference: Path,output: Path,client,*,language='zh',allow_mock=False,seed=20261006) -> dict:
    source,reference,output=source.resolve(),reference.resolve(),output.resolve()
    if output.exists(): raise FileExistsError(output)
    prior=binding_reference(source,reference,allow_mock=allow_mock);requests=binding_inputs(prior,language=language)
    health=client.health(allow_mock=allow_mock);jev=getattr(client,'backend',None)=='jev'
    if health.get('busy') or health.get('is_mock') is not bool(allow_mock): raise ProtocolError('Require idle correctly marked service')
    if jev:
        if allow_mock or language!='en' or health.get('model')!='jev-1.13.0': raise ProtocolError('Require real pinned English Jev')
    else:
        if not health.get('supports_text_only_ablation'): raise ProtocolError('Require explicit text-only experimental service')
        if any(health.get(k)!=prior['model_health'].get(k) for k in IMAGE_HEALTH_KEYS): raise ProtocolError('Reference model provenance changed')
        if not allow_mock and (health.get('device')!='cuda' or health.get('dtype')!='bfloat16' or not health.get('text_input_audit')):
            raise ProtocolError('Require audited official CUDA/BF16')
    output.mkdir(parents=True,exist_ok=False);(output/'requests').mkdir();(output/'responses').mkdir()
    for name,request in requests.items():write_json(output/'requests'/(name+'.json'),request)
    order=[{'name':r['name'],'cell':r['cell'],'decision_id':r['decision_id'],'image_count':0} for r in prior['rows']];random.Random(seed).shuffle(order)
    hashes={name:sha256_file(output/'requests'/(name+'.json')) for name in requests};code=binding_code_hashes()
    if jev:
        from .jev import jev_payload
        (output/'wire_requests').mkdir()
        for name,request in requests.items():write_json(output/'wire_requests'/(name+'.json'),jev_payload(request))
    m={'kind':'goal_name_binding','language':language,'backend':'jev' if jev else 'intern','source_files_sha256':source_hashes(source),
       'source_sha256':code,'reference':prior,'model_health':health,'planned_order':order,'planned_request_sha256':hashes,
       'wire_request_sha256':{name:sha256_file(output/'wire_requests'/(name+'.json')) for name in requests} if jev else {},
       'synthetic_fixture':allow_mock,'model_had_control':False,'seed':seed,
       'scope':'Chinese single-field goal binding; English translation and language-matched model comparison are separate factors.'}
    write_json(output/'manifest.json',m);rows=[];error=None
    try:
        with (output/'decisions.jsonl').open('x') as journal:
            for job in order:
                name=job['name']
                if sha256_file(output/'requests'/(name+'.json'))!=hashes[name]: raise LabError('Frozen request hash changed')
                raw,latency=client.predict(json.loads((output/'requests'/(name+'.json')).read_text()));write_json(output/'responses'/(name+'.json'),raw)
                if jev:
                    from .jev import verify_jev_response
                    parsed=verify_jev_response(raw)
                else:parsed=verify_image_response([],raw,health,allow_mock=allow_mock)
                old=next(r for r in prior['rows'] if r['name']==name)
                row={**job,'expected_action':old['expected_action'],'proposed_action':parsed.action,'probabilities':parsed.probabilities,
                     'confidence':parsed.confidence,'confidence_kind':'normalized_choice_confidence' if jev else 'official_choice_probability',
                     'top_probability_ties':[a for a in ACTIONS if parsed.probabilities[a]==max(parsed.probabilities.values())],
                     'http_latency_ms':latency,'input_tokens':raw.get('usage',{}).get('input_tokens') if jev else raw.get('_vision_audit',{}).get('input_tokens'),
                     'request_sha256':hashes[name],'response_sha256':sha256_file(output/'responses'/(name+'.json'))}
                rows.append(row);journal.write(json.dumps(row,ensure_ascii=False,allow_nan=False)+'\n');journal.flush()
                print(f"{len(rows)}/14 {language}/{m['backend']} {name}: {parsed.action} reference={old['expected_action']}",flush=True)
        final=client.health(allow_mock=allow_mock);write_json(output/'final_health.json',final)
        if final['requests_completed']-health['requests_completed']!=14 or final.get('busy'): raise ProtocolError('Unexpected14-request counter or busy service')
        keys=('model','endpoint','model_listing') if jev else IMAGE_HEALTH_KEYS
        if any(health.get(k)!=final.get(k) for k in keys): raise ProtocolError('Service provenance changed')
        if binding_code_hashes()!=code or source_hashes(source)!=m['source_files_sha256']: raise LabError('Source hash changed')
        if any(sha256_file(output/'requests'/(n+'.json'))!=h for n,h in hashes.items()): raise LabError('Frozen request hash changed')
        if jev and any(sha256_file(output/'wire_requests'/(n+'.json'))!=h for n,h in m['wire_request_sha256'].items()): raise LabError('Wire request hash changed')
    except Exception as exc:error=f'{type(exc).__name__}: {exc}'
    result={'complete':len(rows)==14 and error is None,'api_completed':len(rows),'error':error,'language':language,'backend':m['backend'],
            'mock_backend':allow_mock,'model_had_control':False,'cells':binding_summary(rows,prior),'decisions':rows}
    write_json(output/'summary.json',result);return result

def build_binding_report(source: Path,replay: Path,output: Path,*,allow_mock=False) -> Path:
    source,replay,output=source.resolve(),replay.resolve(),output.resolve()
    if output.exists(): raise FileExistsError(output)
    m=json.loads((replay/'manifest.json').read_text());s=json.loads((replay/'summary.json').read_text())
    if (not s.get('complete') or s.get('api_completed')!=14 or len(s['decisions'])!=14 or s.get('mock_backend') is not bool(allow_mock)
            or m.get('synthetic_fixture') is not bool(allow_mock) or m.get('model_had_control') is not False): raise LabError('Require complete correctly marked14-request offline replay')
    validate_capture(source,allow_mock=allow_mock)
    if source_hashes(source)!=m['source_files_sha256']: raise LabError('Capture hash mismatch')
    requests={};responses={};constructed=binding_inputs(m['reference'],language=m['language'])
    if s['cells']!=binding_summary(s['decisions'],m['reference']): raise LabError('Summary metrics mismatch')
    if [(r['name'],r['decision_id']) for r in s['decisions']]!=[(j['name'],j['decision_id']) for j in m['planned_order']]: raise LabError('Frozen order mismatch')
    final=json.loads((replay/'final_health.json').read_text())
    if final['requests_completed']-m['model_health']['requests_completed']!=14: raise LabError('Final14-request count mismatch')
    for r in s['decisions']:
        name=r['name']
        for directory,key in [('requests','request'),('responses','response')]:
            if sha256_file(replay/directory/(name+'.json'))!=r[key+'_sha256']: raise LabError('Actual artifact hash mismatch')
        request=json.loads((replay/'requests'/(name+'.json')).read_text());raw=json.loads((replay/'responses'/(name+'.json')).read_text())
        if request!=constructed[name] or r['request_sha256']!=m['planned_request_sha256'][name]: raise LabError('Frozen construction/hash mismatch')
        if m['backend']=='jev':
            from .jev import verify_jev_response,jev_payload
            if sha256_file(replay/'wire_requests'/(name+'.json'))!=m['wire_request_sha256'][name] or json.loads((replay/'wire_requests'/(name+'.json')).read_text())!=jev_payload(request): raise LabError('Jev wire hash/construction mismatch')
            parsed=verify_jev_response(raw)
        else:parsed=verify_image_response([],raw,m['model_health'],allow_mock=allow_mock)
        if parsed.action!=r['proposed_action'] or parsed.probabilities!=r['probabilities'] or parsed.confidence!=r['confidence']: raise LabError('Response/summary mismatch')
        requests[name]=request;responses[name]=raw
    payload={'summary':s,'manifest':m,'final_health':final,'requests':requests,'responses':responses,'actions':list(ACTIONS),'synthetic_fixture':allow_mock}
    encoded=json.dumps(payload,ensure_ascii=False,allow_nan=False,separators=(',',':')).replace('&',r'\u0026').replace('<',r'\u003c').replace('>',r'\u003e').replace('\u2028',r'\u2028').replace('\u2029',r'\u2029')
    lab=Path(__file__).resolve().parent;style=(lab/'factorial_report.html').read_text().split('<style>',1)[1].split('</style>',1)[0]
    status='合成CPU契约 · 非真实模型证据' if allow_mock else '真实模型 · '+m['backend']+' / '+m['language']+' · 14请求 · 无控制'
    content=(lab/'binding_report.html').read_text().replace('{{STYLE}}',style).replace('{{STATUS}}',html.escape(status)).replace('{{DATA}}',encoded)
    output.parent.mkdir(parents=True,exist_ok=True)
    with output.open('x') as f:f.write(content)
    return output
