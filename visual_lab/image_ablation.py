"""Delete only images from frozen Chinese spatial prompts; never control a robot."""
from __future__ import annotations
import base64
import copy
import hashlib
import io
import json
import random
from pathlib import Path

from .audit import sha256_file, write_json
from .core import ACTIONS, LabError, ProtocolError, parse_decision
from .factorial import GOAL_COLORS, load_snapshots
from .prompt_variants import STABLE_HEALTH_KEYS, prompt_request, source_hashes, validate_capture, verify_response
from .protocol import validate_request
from .server import VISION_TOKENS

IMAGE_HEALTH_KEYS = (*STABLE_HEALTH_KEYS, 'text_input_audit', 'supports_text_only_ablation')
REFERENCE_HEALTH_KEYS = tuple(key for key in STABLE_HEALTH_KEYS if key not in {'bridge_source_sha256', 'protocol_source_sha256'})


def image_cells() -> list[dict]:
    return [{'id':f'{color}_images_{views}', 'color':color, 'views':views, 'variant':'zh_named_relative'}
            for color in GOAL_COLORS for views in range(3)]


def image_request(pngs: list[bytes], state: dict, views: list[dict], guidance: dict, cell: dict) -> dict:
    count = cell.get('views')
    if type(count) is not int or count not in range(3):
        raise ProtocolError('Require exactly zero, one or two images')
    request = prompt_request(pngs, state, views, guidance, {'variant':'zh_named_relative', 'color':cell['color']})
    request['images'] = request['images'][:count]
    validate_request(request, allow_empty_images=True)
    return request


def verify_image_response(pngs: list[bytes], raw: dict, health: dict, *, allow_mock=False):
    from PIL import Image
    parsed = parse_decision(raw, allow_mock=allow_mock)
    meta = raw.get('_bridge', {})
    hashes = [hashlib.sha256(png).hexdigest() for png in pngs]
    if (meta.get('is_mock') is not bool(allow_mock) or meta.get('image_count') != len(pngs)
            or meta.get('image_sha256s') != hashes):
        raise ProtocolError('Response actual image count/order/hash or real/mock mode mismatch')
    if not allow_mock:
        audit = raw.get('_vision_audit', {})
        tokens = audit.get('input_tokens')
        if type(tokens) is not int or not 0 < tokens <= health['max_length']:
            raise ProtocolError('Official input token audit missing or truncation risk')
        rgb = []
        for png in pngs:
            with Image.open(io.BytesIO(png)) as image: rgb.append(hashlib.sha256(image.convert('RGB').tobytes()).hexdigest())
        if audit.get('normalized_rgb_sha256s') != rgb or len(audit.get('image_grid_thw', [])) != len(pngs):
            raise ProtocolError('Official image RGB/processor grid count/order mismatch')
        if not pngs:
            counts = audit.get('vision_token_counts', {})
            if (audit.get('encoding_path') != 'tokenizer_only' or set(counts) != set(VISION_TOKENS)
                    or any(type(value) is not int or value != 0 for value in counts.values())
                    or meta.get('image_sha256') is not None):
                raise ProtocolError('No-image input requires tokenizer-only audit with zero visual tokens')
        elif audit.get('encoding_path') != 'processor_images':
            raise ProtocolError('Images must reach the official processor')
        if (meta.get('inference_py_sha256') != health['inference_py_sha256']
                or raw.get('calibration', {}).get('temperature') != health['temperature']):
            raise ProtocolError('Official implementation/calibration provenance changed')
    return parsed


def summarize_images(rows: list[dict]) -> dict:
    cells = []
    for cell in image_cells():
        selected = sorted((row for row in rows if row['cell'] == cell['id']), key=lambda row:row['decision_id'])
        final = [row for row in selected if row['expected_action'] in {'lower', 'release'}]
        cells.append({**cell, 'num_decisions':len(selected), 'baseline_agreement':sum(row['proposed_action']==row['expected_action'] for row in selected),
                      'final_two_agreement':sum(row['proposed_action']==row['expected_action'] for row in final),
                      'proposed_actions':[row['proposed_action'] for row in selected],
                      'mean_expected_action_probability':sum(row['probabilities'][row['expected_action']] for row in selected)/len(selected) if selected else None})
    by_id = {cell['id']:cell for cell in cells}
    row_map = {(row['cell'],row['decision_id']):row for row in rows}
    contrasts = []
    for color in GOAL_COLORS:
        for low,high in [(0,1),(1,2),(0,2)]:
            a,b = by_id[f'{color}_images_{low}'],by_id[f'{color}_images_{high}']
            if a['num_decisions'] != 7 or b['num_decisions'] != 7: continue
            stages = []
            for stage in range(1,8):
                r0,r1 = row_map[(a['id'],stage)],row_map[(b['id'],stage)]
                stages.append({'decision_id':stage, 'expected_action':r0['expected_action'], 'low_choice':r0['proposed_action'], 'high_choice':r1['proposed_action'],
                               'expected_probability_delta':r1['probabilities'][r1['expected_action']]-r0['probabilities'][r0['expected_action']]})
            contrasts.append({'id':f'{color}_images_{low}_to_{high}', 'factor':f'images_{low}_to_{high}', 'color':color,
                              'low_cell':a['id'], 'high_cell':b['id'], 'agreement_count_delta':b['baseline_agreement']-a['baseline_agreement'],
                              'final_two_count_delta':b['final_two_agreement']-a['final_two_agreement'],
                              'mean_expected_probability_delta':b['mean_expected_action_probability']-a['mean_expected_action_probability'], 'stages':stages})
    return {'cells':cells, 'conditional_contrasts':contrasts,
            'scope':'Image deletion diagnostic on one already-observed scene with seven correlated states; not image understanding, autonomous success or independent generalization.'}


def check_image_reference(reference: Path, source: Path, requests: dict, health: dict) -> dict:
    if (reference/'INVALIDATED.json').exists(): raise LabError('Invalidated reference replay')
    manifest = json.loads((reference/'manifest.json').read_text())
    summary = json.loads((reference/'summary.json').read_text())
    if (summary.get('complete') is not True or summary.get('api_completed') != 84 or summary.get('mock_backend') is not False
            or len(summary.get('decisions', [])) != 84):
        raise LabError('Require complete real 84-request prompt reference')
    if manifest.get('source_files_sha256') != source_hashes(source): raise LabError('Reference capture hashes do not match')
    if any(manifest['model_health'].get(key) != health.get(key) for key in REFERENCE_HEALTH_KEYS):
        raise ProtocolError('Reference official model provenance does not match')
    reference_rows = []
    for row in summary['decisions']:
        if row['cell'] not in {'blue_zh_named_relative','yellow_zh_named_relative'}: continue
        name = f"{row['cell']}_decision_{row['decision_id']:03d}"
        for directory,key in [('requests','request'),('responses','response')]:
            if sha256_file(reference/directory/(name+'.json')) != row[key+'_sha256']: raise LabError('Reference artifact hash mismatch')
        color = row['cell'].split('_')[0]
        new_name = f"{color}_images_2_decision_{row['decision_id']:03d}"
        expected_bytes = (json.dumps(requests[new_name],ensure_ascii=False,indent=2,allow_nan=False)+'\n').encode('utf-8')
        old_request = reference/'requests'/(name+'.json')
        if old_request.read_bytes() != expected_bytes: raise LabError('Dual-image request bytes do not reproduce reference exactly')
        pngs = [base64.b64decode(item['data'],validate=True) for item in requests[new_name]['images']]
        parsed = verify_response(pngs,json.loads((reference/'responses'/(name+'.json')).read_text()),manifest['model_health'])
        if parsed.action != row['proposed_action'] or parsed.probabilities != row['probabilities']: raise LabError('Reference response/summary mismatch')
        reference_rows.append(copy.deepcopy(row))
    if {(row['cell'],row['decision_id']) for row in reference_rows} != {(color+'_zh_named_relative',stage) for color in GOAL_COLORS for stage in range(1,8)} or len(reference_rows)!=14:
        raise LabError('Require all fourteen distinct reference dual decisions')
    return {'path':str(reference), 'files_sha256':{name:sha256_file(reference/name) for name in ['manifest.json','summary.json']},
            'dual_rows':reference_rows, 'old_bridge_source_sha256':manifest['model_health'].get('bridge_source_sha256'),
            'old_protocol_source_sha256':manifest['model_health'].get('protocol_source_sha256'),
            'note':'Bridge/protocol changed only for explicit no-image support/auditing; official model/template/config/temperature remain pinned.'}


def image_source_hashes() -> dict:
    return {name:sha256_file(Path(__file__).with_name(name)) for name in ['image_ablation.py','prompt_variants.py','factorial.py','protocol.py','core.py','server.py']}


def run_image_replay(source: Path, output: Path, client, *, reference: Path | None=None, seed=20261006, allow_mock=False) -> dict:
    source,output = source.resolve(),output.resolve()
    if output.exists(): raise FileExistsError(output)
    bundle,_ = validate_capture(source,allow_mock=allow_mock)
    pinned,code = source_hashes(source),image_source_hashes()
    health = client.health(allow_mock=allow_mock)
    if health.get('busy'): raise ProtocolError('Model service is busy')
    if (health.get('max_images',0)<2 or not health.get('supports_text_only_ablation') or health.get('is_mock') is not bool(allow_mock)):
        raise ProtocolError('Require explicit text-only ablation and two-image capability with correct real/mock mode')
    if not allow_mock and (not health.get('vision_input_audit') or not health.get('text_input_audit') or health.get('device')!='cuda' or health.get('dtype')!='bfloat16'):
        raise ProtocolError('Require audited official CUDA/BF16 image and text service')
    requests,order = {},[]
    cells = image_cells()
    for record in bundle['records']:
        for cell in cells:
            pngs = [(source/asset['path']).read_bytes() for asset in record['images'][cell['color']]]
            name = f"{cell['id']}_decision_{record['decision_id']:03d}"
            requests[name] = image_request(pngs,record['model_state'],bundle['view_metadata'],record['goal_guidance'],cell)
            order.append({'name':name,'cell':cell['id'],'decision_id':record['decision_id']})
    random.Random(seed).shuffle(order)
    reference_info = None
    if not allow_mock:
        if reference is None: raise LabError('Require pinned real prompt reference replay')
        reference_info = check_image_reference(reference.resolve(),source,requests,health)
    output.mkdir(parents=True,exist_ok=False)
    (output/'requests').mkdir();(output/'responses').mkdir()
    for name,request in requests.items(): write_json(output/'requests'/(name+'.json'),request)
    hashes = {name:sha256_file(output/'requests'/(name+'.json')) for name in requests}
    manifest = {'kind':'paired_image_ablation','source':str(source),'source_files_sha256':pinned,'model_health':health,'seed':seed,
                'cells':cells,'planned_order':order,'planned_request_sha256':hashes,'reference_replay':reference_info,
                'synthetic_fixture':allow_mock,'model_had_control':False,'source_sha256':code,
                'design':'Only images change; zh_named_relative state/questions including two-camera text are identical across image counts.'}
    write_json(output/'manifest.json',manifest)
    rows,error = [],None
    try:
        with (output/'decisions.jsonl').open('x',encoding='utf-8') as journal:
            for job in order:
                name = job['name']
                if sha256_file(output/'requests'/(name+'.json')) != hashes[name]: raise LabError('Frozen request hash changed before inference')
                request = json.loads((output/'requests'/(name+'.json')).read_text())
                cell = next(cell for cell in cells if cell['id']==job['cell'])
                record = bundle['records'][job['decision_id']-1]
                pngs = [(source/asset['path']).read_bytes() for asset in record['images'][cell['color']][:cell['views']]]
                raw,latency = client.predict(request)
                write_json(output/'responses'/(name+'.json'),raw)
                parsed = verify_image_response(pngs,raw,health,allow_mock=allow_mock)
                probabilities = parsed.probabilities
                row = {**job,'image_count':cell['views'],'expected_action':record['expected_action'],'proposed_action':parsed.action,
                       'probabilities':probabilities,'confidence':parsed.confidence,
                       'top_probability_ties':[action for action in ACTIONS if probabilities[action]==max(probabilities.values())],
                       'http_latency_ms':latency,'input_tokens':raw.get('_vision_audit',{}).get('input_tokens'),
                       'encoding_path':raw.get('_vision_audit',{}).get('encoding_path'),
                       'image_sha256s':raw['_bridge']['image_sha256s'],'request_sha256':hashes[name],
                       'response_sha256':sha256_file(output/'responses'/(name+'.json'))}
                rows.append(row);journal.write(json.dumps(row,ensure_ascii=False,allow_nan=False)+'\n');journal.flush()
                print(f"{len(rows)}/42 {name}: {parsed.action}, reference={record['expected_action']}, {latency:.0f} ms",flush=True)
        final = client.health(allow_mock=allow_mock)
        write_json(output/'final_health.json',final)
        if any(health.get(key)!=final.get(key) for key in IMAGE_HEALTH_KEYS): raise ProtocolError('Model/service provenance changed during replay')
        if final['requests_completed']-health['requests_completed']!=42 or final.get('busy'): raise ProtocolError('Unexpected completed request count or busy service')
        if source_hashes(source)!=pinned or image_source_hashes()!=code: raise LabError('Capture or code source hashes changed during replay')
        load_snapshots(source)
        if any(sha256_file(output/'requests'/(name+'.json'))!=digest for name,digest in hashes.items()): raise LabError('Frozen request hash changed during replay')
    except Exception as exc:
        error = f'{type(exc).__name__}: {exc}'
    result = {'complete':len(rows)==42 and error is None,'api_completed':len(rows),'error':error,'mock_backend':allow_mock,
              'real_model_evaluated':not allow_mock and bool(rows),'model_had_control':False,**summarize_images(rows),'decisions':rows}
    write_json(output/'summary.json',result)
    return result
