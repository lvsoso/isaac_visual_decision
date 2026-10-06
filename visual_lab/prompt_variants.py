"""Frozen bilingual/target/spatial prompt contrasts; never a robot controller."""
from __future__ import annotations
import copy
import hashlib
import io
import json
import random
from pathlib import Path

from .audit import sha256_file, write_json
from .core import ACTIONS, LabError, ProtocolError, finite_number, parse_decision, vector3
from .factorial import GOAL_COLORS, factor_request, load_snapshots

VARIANTS = tuple(f'{language}_{form}' for form in ('neutral_raw', 'named_raw', 'named_relative') for language in ('en', 'zh'))
GUIDANCE_KEYS = ('source', 'goal_center_on_ground_world_m', 'placement_tool_target_world_m', 'controller_tool_frame',
                 'measured_tool_world_position_m', 'tool_to_placement_delta_m', 'tool_to_goal_horizontal_distance_m',
                 'tool_height_above_placement_m', 'tool_to_placement_distance_m', 'reference_warning')
STABLE_HEALTH_KEYS = ('is_mock', 'checkpoint', 'max_images', 'inference_py_sha256', 'config_sha256', 'temperature',
                      'device', 'dtype', 'max_length', 'vision_input_audit', 'bridge_source_sha256',
                      'protocol_source_sha256', 'model_files_sha256')
ZH_CRITERIA = {
    'pre_grasp': '将夹爪移到红色方块上方的高位对准姿态，以便拾取。适用于手指张开且夹爪尚未位于静止方块上方的情况。若方块已被携带，或夹爪已在其上方对准，则不要使用；此技能不会张开已闭合的手指。',
    'approach': '保持手指张开，下降到静止红色方块的拾取高度。适用于夹爪已在方块上方，但仍太高而无法在其周围闭合的情况。若手指闭合、方块已被携带，或张开的夹爪已在拾取高度，则不要使用。',
    'grasp': '在红色方块周围闭合手指。适用于手指张开，并在拾取高度围住静止方块的情况。若手指已闭合或方块已被携带，则不要使用。仅闭合手指不能证明抓取成功。',
    'lift': '抬高刚闭合的夹爪，检验方块是否被带离拾取处的地面。适用于手指已在方块周围闭合，但方块尚未在图像中明显升高的情况。若被夹持的方块已明显升高，包括位于目标上方时，则不要使用；反复抬高不会将其运到目标或释放它。',
    'transport': '将已升高且被夹持的方块水平运向地面方形轮廓线。适用于方块在闭合的手指之间明显升高，但水平方向尚未位于目标上方的情况。若方块被留在原处、手指张开，或被夹持的方块已在目标上方，则不要使用。',
    'lower': '将被夹持的方块向轮廓线标示目标处的放置高度下降。适用于已升高的被夹持方块在水平方向位于目标上方，但仍远高于该处地面的情况。若远离目标、没有夹持方块，或被夹持的方块已在放置高度，则不要使用。',
    'release': '张开手指，将方块留在轮廓线标示目标处并完成任务，随后自动回撤。适用于闭合的夹爪已将被夹持的方块降到目标上方的放置高度的情况。若远高于地面或远离目标，则不要使用；这不是通用的重试或张开技能。',
    'abort': '若方块丢失、重试需要在其他位置张开手指、观测互相矛盾，或没有可用技能能安全推进，则停止。',
}
ZH_INSTRUCTIONS = (
    '根据当前RGB图像和本体状态，恰好选择一个下一步技能。'
    '红色方块是操作对象，地面方形无碰撞轮廓线是目标。'
    '将每个技能可观察的使用条件和排除条件与当前场景匹配。'
    'previous_action和previous_result只是上下文，不是必须遵循的序列，也不能证明任务已取得进展。'
    'finger_joint_position_rad接近0.0表示手指张开；接近0.5表示手指闭合。'
    '闭合手指不能证明夹持：检查红色方块是否位于手指之间。'
    'ee_world_position_m指的是手指连杆，不是方块中心或抓取中心；不要将该连杆高度当作方块高度。'
    '第一次抬高之前，刚闭合的手指之间的方块仍可能停留在地面。'
    '已在图像中明显升高的被夹持方块不需要再次执行拾取抬高；判断它与目标的关系。'
    '图像不能证明接触或三维度量精度。当所需恢复操作不可用时选择abort。无需输出坐标或解释。'
    '图像顺序与camera_views中的image_index一致。可选的goal_guidance描述控制器模型工具点，绝不是方块中心；使用图像判断夹持情况。'
)
ZH_SOURCE = '配置目标加实测关节的控制器模型正向运动学；无方块真值'
ZH_WARNING = '放置目标和实测工具使用同一个控制器模型工具参考系，不是手指连杆或方块中心；相对放置高度是带符号的实测Z减目标Z；接近目标不能证明夹持'


def prompt_cells() -> list[dict]:
    return [{'id': color+'_'+variant, 'color': color, 'variant': variant, 'language': variant.split('_')[0],
             'named_color': 'named' in variant, 'representation': 'relative' if variant.endswith('relative') else 'raw',
             'round': VARIANTS.index(variant)//2, 'views': 2, 'coordinates': True}
            for variant in VARIANTS for color in GOAL_COLORS]


def cm(value) -> str:
    number = finite_number(value, 'spatial scalar')*100
    return f'{0.0 if abs(number)<.05 else number:.1f}'


def position_cm(value) -> str:
    return '('+', '.join(axis+'='+cm(number) for axis, number in zip('XYZ', vector3(value, 'spatial position')))+')'


def relative_state(state: dict, guidance: dict, language: str) -> None:
    """Only re-express permitted geometry; no thresholds/holding/action labels."""
    zh = language == 'zh'
    finger = state.pop('ee_world_position_m')
    state['ee_position_description'] = ('手指连杆世界坐标约'+position_cm(finger)+'厘米；不是抓取中心或方块中心。' if zh else
        'Finger-link world position approximately '+position_cm(finger)+' cm; not the grasp or cube center.')
    for view in state['camera_views']:
        position, look_at = view.pop('camera_position_world_m'), view.pop('look_at_world_m')
        view.pop('view_direction_world')
        azimuth = finite_number(view.pop('view_azimuth_deg'), 'camera azimuth')
        elevation = finite_number(view.pop('view_elevation_deg'), 'camera elevation')
        view['world_axes'] = '右手世界坐标系，Z向上，位置单位厘米' if zh else 'right-handed world coordinates, Z up, positions in centimeters'
        view['view_geometry_description'] = (f'相机世界位置约{position_cm(position)}厘米，朝向点约{position_cm(look_at)}厘米；视线方位角约{azimuth:.1f}度，仰角约{elevation:.1f}度。' if zh else
            f'Camera world position approximately {position_cm(position)} cm, looking at approximately {position_cm(look_at)} cm; view-ray azimuth approximately {azimuth:.1f} degrees and elevation {elevation:.1f} degrees.')
    goal = position_cm(guidance['goal_center_on_ground_world_m'])
    target = position_cm(guidance['placement_tool_target_world_m'])
    measured = position_cm(guidance['measured_tool_world_position_m'])
    delta = position_cm(guidance['tool_to_placement_delta_m'])
    horizontal = cm(guidance['tool_to_goal_horizontal_distance_m'])
    height = cm(guidance['tool_height_above_placement_m'])
    distance = cm(guidance['tool_to_placement_distance_m'])
    description = (f'配置的地面框中心世界坐标约{goal}厘米。放置工具目标约{target}厘米；实测模型工具点约{measured}厘米。'
        f'从工具点到放置工具目标的位移约{delta}厘米（世界轴，不是画面左右）。工具点与地面目标中心的水平距离约{horizontal}厘米。'
        f'工具点相对放置工具目标的高度差（带符号，实测Z减目标Z；正数在上方、负数在下方）约{height}厘米。到放置工具目标的直线距离约{distance}厘米。'
        '位置量以厘米保留一位小数，每量舍入误差最多0.05厘米；不判断是否对齐、接触或夹持。' if zh else
        f'Configured ground-outline center approximately {goal} cm in world coordinates. Placement tool target approximately {target} cm; measured model tool approximately {measured} cm. '
        f'Displacement from the tool to its placement target approximately {delta} cm along world axes, not image left/right. Horizontal distance from tool to ground-goal center approximately {horizontal} cm. '
        f'Tool height relative to placement tool target (signed measured Z minus target Z; positive is above, negative below) approximately {height} cm. Straight-line distance to placement tool target approximately {distance} cm. '
        'Positions/distances are rounded to one decimal centimeter, at most 0.05 cm rounding error per scalar; no alignment, contact or holding judgment.')
    state['goal_guidance'] = {'source': state['goal_guidance']['source'], 'controller_tool_frame': guidance['controller_tool_frame'],
                              'spatial_description': description, 'reference_warning': state['goal_guidance']['reference_warning']}


def prompt_request(pngs: list[bytes], state: dict, views: list[dict], guidance: dict, cell: dict) -> dict:
    if cell.get('variant') not in VARIANTS or cell.get('color') not in GOAL_COLORS or len(pngs) != 2 or len(views) != 2:
        raise ProtocolError('Require an approved prompt variant, color and two simultaneous views')
    clean_guidance = {key: copy.deepcopy(guidance[key]) for key in GUIDANCE_KEYS}
    for key in GUIDANCE_KEYS[1:]:
        if key in {'goal_center_on_ground_world_m', 'placement_tool_target_world_m', 'measured_tool_world_position_m', 'tool_to_placement_delta_m'}:
            vector3(clean_guidance[key], key)
        elif key in {'tool_to_goal_horizontal_distance_m', 'tool_height_above_placement_m', 'tool_to_placement_distance_m'}:
            finite_number(clean_guidance[key], key)
    request = factor_request(pngs, state, views, clean_guidance, {'views': 2, 'coordinates': True})
    evidence, question = request['state'], request['questions']['next_stage']
    zh = cell['variant'].startswith('zh_')
    if zh:
        if evidence['task'] != 'Place the red cube inside the square ground outline, then release it.':
            raise ProtocolError('Unknown task; cannot silently invent a translation')
        evidence['task'] = '将红色方块放入地面方形轮廓线内部，然后释放它。'
        evidence['observation'] = '同一冻结场景的当前同时RGB视图，不是时间序列帧；世界轴不是图像轴。'
        evidence['ee_reference'] = 'right_inner_finger连杆，不是夹爪的抓取中心'
        evidence['limitations'] = 'reached表示执行器或姿态收敛，不证明抓取；仅手指闭合不能证明夹持'
        for view in evidence['camera_views']:
            view['world_axes'] = '右手世界坐标系，Z向上，单位米'
            view['angle_definition'] = '从相机指向朝向点的视线；方位角从+X向+Y测量；仰角相对XY平面'
        evidence['goal_guidance']['source'] = ZH_SOURCE
        evidence['goal_guidance']['reference_warning'] = ZH_WARNING
        question['criteria'], question['instructions'] = dict(ZH_CRITERIA), ZH_INSTRUCTIONS
    if 'named' in cell['variant']:
        if zh:
            color = '蓝色' if cell['color'] == 'blue' else '黄色'
            evidence['task'] = evidence['task'].replace('地面方形', '地面'+color+'方形')
            question['instructions'] = question['instructions'].replace('地面方形无碰撞', '地面'+color+'方形无碰撞')
        else:
            evidence['task'] = evidence['task'].replace('square ground outline', cell['color']+' ground outline')
            question['instructions'] = question['instructions'].replace('square non-colliding ground outline', cell['color']+' non-colliding ground outline')
    if cell['variant'].endswith('relative'):
        relative_state(evidence, clean_guidance, 'zh' if zh else 'en')
    json.dumps(request, allow_nan=False)
    return request


def validate_capture(source: Path, *, allow_mock=False) -> tuple[dict, dict | None]:
    bundle = load_snapshots(source)
    manifest = json.loads((source/'manifest.json').read_text())
    if not allow_mock and (manifest.get('synthetic_fixture') or manifest.get('kind') != 'paired_factorial_capture'):
        raise LabError('Require production paired capture, not a synthetic fixture')
    review = None
    if not allow_mock:
        review = json.loads((source/'render_review.json').read_text())
        assets = {asset['path']:asset['sha256'] for record in bundle['records'] for images in record['images'].values() for asset in images}
        if (review.get('approved') is not True or review.get('reviewed_color_pairs') != 14
                or review.get('snapshots_sha256') != sha256_file(source/'snapshots.json') or review.get('source_images_sha256') != assets):
            raise LabError('Require pinned approval of all 14 color pairs and all 28 original PNGs')
    return bundle, review


def source_hashes(source: Path) -> dict:
    names = ['manifest.json', 'snapshots.json', 'summary.json']
    if (source/'render_review.json').exists(): names.append('render_review.json')
    return {name:sha256_file(source/name) for name in names}


def verify_response(pngs: list[bytes], raw: dict, health: dict, *, allow_mock=False):
    from PIL import Image
    parsed = parse_decision(raw, allow_mock=allow_mock)
    meta = raw['_bridge']
    hashes = [hashlib.sha256(png).hexdigest() for png in pngs]
    if meta.get('is_mock') is not bool(allow_mock) or meta.get('image_count') != 2 or meta.get('image_sha256s') != hashes:
        raise ProtocolError('Response ordered image hashes/count or real/mock mode mismatch')
    if not allow_mock:
        rgb = []
        for png in pngs:
            with Image.open(io.BytesIO(png)) as image: rgb.append(hashlib.sha256(image.convert('RGB').tobytes()).hexdigest())
        audit = raw.get('_vision_audit', {})
        tokens = audit.get('input_tokens')
        if (audit.get('normalized_rgb_sha256s') != rgb or len(audit.get('image_grid_thw', [])) != 2
                or type(tokens) is not int or not 0 < tokens <= health['max_length']):
            raise ProtocolError('Official processor image/token audit mismatch or truncation risk')
        if meta.get('inference_py_sha256') != health['inference_py_sha256'] or raw.get('calibration', {}).get('temperature') != health['temperature']:
            raise ProtocolError('Official model implementation/calibration provenance changed')
    return parsed


def summarize_prompts(rows: list[dict]) -> dict:
    cells = []
    for cell in prompt_cells():
        selected = sorted((row for row in rows if row['cell'] == cell['id']), key=lambda row:row['decision_id'])
        final = [row for row in selected if row['expected_action'] in {'lower', 'release'}]
        cells.append({**cell, 'num_decisions':len(selected), 'baseline_agreement':sum(row['proposed_action']==row['expected_action'] for row in selected),
                      'final_two_agreement':sum(row['proposed_action']==row['expected_action'] for row in final),
                      'proposed_actions':[row['proposed_action'] for row in selected],
                      'mean_expected_action_probability':sum(row['probabilities'][row['expected_action']] for row in selected)/len(selected) if selected else None})
    contrasts, by_id = [], {cell['id']:cell for cell in cells}
    row_map = {(row['cell'],row['decision_id']):row for row in rows}
    for color in GOAL_COLORS:
        pairs = [('language_'+form, 'en_'+form, 'zh_'+form) for form in ['neutral_raw', 'named_raw', 'named_relative']]
        pairs += [('color_identification_'+language, language+'_neutral_raw', language+'_named_raw') for language in ['en','zh']]
        pairs += [('spatial_representation_'+language, language+'_named_raw', language+'_named_relative') for language in ['en','zh']]
        for factor, low, high in pairs:
            a, b = by_id[color+'_'+low], by_id[color+'_'+high]
            if a['num_decisions'] != 7 or b['num_decisions'] != 7: continue
            stages=[]
            for stage in range(1,8):
                r0,r1=row_map[(a['id'],stage)],row_map[(b['id'],stage)]
                stages.append({'decision_id':stage, 'expected_action':r0['expected_action'], 'low_choice':r0['proposed_action'], 'high_choice':r1['proposed_action'],
                               'expected_probability_delta':r1['probabilities'][r1['expected_action']]-r0['probabilities'][r0['expected_action']]})
            contrasts.append({'id':color+'_'+factor, 'factor':factor, 'color':color, 'low_cell':a['id'], 'high_cell':b['id'],
                              'agreement_count_delta':b['baseline_agreement']-a['baseline_agreement'], 'final_two_count_delta':b['final_two_agreement']-a['final_two_agreement'],
                              'mean_expected_probability_delta':b['mean_expected_action_probability']-a['mean_expected_action_probability'], 'stages':stages})
    return {'cells':cells, 'conditional_contrasts':contrasts,
            'scope':'One already-observed fixed scene, seven correlated states; prompt diagnostics, not autonomous success, independent generalization or significance.'}


def check_reference(reference: Path, source: Path, requests: dict, health: dict) -> dict:
    if (reference/'INVALIDATED.json').exists(): raise LabError('Invalidated reference replay')
    manifest=json.loads((reference/'manifest.json').read_text())
    summary=json.loads((reference/'summary.json').read_text())
    if summary.get('complete') is not True or summary.get('api_completed') != 56 or summary.get('mock_backend') is not False:
        raise LabError('Require complete real 56-request reference replay')
    if any(manifest.get('source_'+name.split('.')[0]+'_sha256') != sha256_file(source/name) for name in ['manifest.json','snapshots.json','summary.json']):
        raise LabError('Reference capture hashes do not match')
    if any(manifest['model_health'].get(key) != health.get(key) for key in STABLE_HEALTH_KEYS):
        raise ProtocolError('Reference model/service provenance does not match')
    reference_rows=[]
    for row in summary['decisions']:
        if row['cell'] not in {'A0B1C1','A1B1C1'}: continue
        name=f"{row['cell']}_decision_{row['decision_id']:03d}"
        for directory,key in [('requests','request'),('responses','response')]:
            if sha256_file(reference/directory/(name+'.json')) != row[key+'_sha256']: raise LabError('Reference artifact hash mismatch')
        color='blue' if row['cell']=='A0B1C1' else 'yellow'
        new_name=f"{color}_en_neutral_raw_decision_{row['decision_id']:03d}"
        if json.loads((reference/'requests'/(name+'.json')).read_text()) != requests[new_name]:
            raise LabError('English neutral request does not reproduce reference exactly')
        reference_rows.append(copy.deepcopy(row))
    if len(reference_rows)!=14: raise LabError('Require all fourteen reference neutral decisions')
    return {'path':str(reference), 'files_sha256':{name:sha256_file(reference/name) for name in ['manifest.json','summary.json']}, 'neutral_rows':reference_rows}


def run_prompt_replay(source: Path, output: Path, client, *, reference: Path | None=None, seed=20261006, allow_mock=False) -> dict:
    source,output=source.resolve(),output.resolve()
    if output.exists(): raise FileExistsError(output)
    bundle,_=validate_capture(source,allow_mock=allow_mock)
    pinned=source_hashes(source)
    health=client.health(allow_mock=allow_mock)
    if health.get('busy'): raise ProtocolError('Model service is busy')
    if health.get('max_images',0)<2 or health.get('is_mock') is not bool(allow_mock): raise ProtocolError('Require two-image capability and correct real/mock mode')
    if not allow_mock and (not health.get('vision_input_audit') or health.get('device')!='cuda' or health.get('dtype')!='bfloat16'):
        raise ProtocolError('Require audited official CUDA/BF16 model service')
    requests,order={},[]
    cells=prompt_cells()
    for round_id in range(3):
        jobs=[]
        for record in bundle['records']:
            for cell in cells:
                if cell['round'] != round_id: continue
                pngs=[(source/asset['path']).read_bytes() for asset in record['images'][cell['color']]]
                name=f"{cell['id']}_decision_{record['decision_id']:03d}"
                requests[name]=prompt_request(pngs,record['model_state'],bundle['view_metadata'],record['goal_guidance'],cell)
                jobs.append({'name':name,'cell':cell['id'],'decision_id':record['decision_id']})
        random.Random(seed+round_id).shuffle(jobs)
        order.extend(jobs)
    reference_info=None
    if not allow_mock:
        if reference is None: raise LabError('Require pinned real reference replay')
        reference_info=check_reference(reference.resolve(),source,requests,health)
    output.mkdir(parents=True,exist_ok=False)
    (output/'requests').mkdir();(output/'responses').mkdir()
    for name,request in requests.items(): write_json(output/'requests'/(name+'.json'),request)
    request_hashes={name:sha256_file(output/'requests'/(name+'.json')) for name in requests}
    manifest={'kind':'paired_prompt_replay','source':str(source),'source_files_sha256':pinned,'model_health':health,'seed':seed,
              'cells':cells,'planned_order':order,'planned_request_sha256':request_hashes,'reference_replay':reference_info,
              'synthetic_fixture':allow_mock,'model_had_control':False,
              'source_sha256':{name:sha256_file(Path(__file__).with_name(name)) for name in ['prompt_variants.py','factorial.py','protocol.py','core.py']}}
    write_json(output/'manifest.json',manifest)
    rows,error=[],None
    try:
        with (output/'decisions.jsonl').open('x',encoding='utf-8') as journal:
            for job in order:
                name=job['name']
                if sha256_file(output/'requests'/(name+'.json')) != request_hashes[name]: raise LabError('Frozen request hash changed before inference')
                request=json.loads((output/'requests'/(name+'.json')).read_text())
                cell=next(cell for cell in cells if cell['id']==job['cell'])
                record=bundle['records'][job['decision_id']-1]
                pngs=[(source/asset['path']).read_bytes() for asset in record['images'][cell['color']]]
                raw,latency=client.predict(request)
                write_json(output/'responses'/(name+'.json'),raw)
                parsed=verify_response(pngs,raw,health,allow_mock=allow_mock)
                probabilities=parsed.probabilities
                row={**job,'expected_action':record['expected_action'],'proposed_action':parsed.action,'probabilities':probabilities,'confidence':parsed.confidence,
                     'top_probability_ties':[action for action in ACTIONS if probabilities[action]==max(probabilities.values())],
                     'http_latency_ms':latency,'input_tokens':raw.get('_vision_audit',{}).get('input_tokens'),
                     'image_sha256s':raw['_bridge']['image_sha256s'],'request_sha256':request_hashes[name],
                     'response_sha256':sha256_file(output/'responses'/(name+'.json'))}
                rows.append(row);journal.write(json.dumps(row,ensure_ascii=False,allow_nan=False)+'\n');journal.flush()
                print(f"{len(rows)}/84 {name}: {parsed.action}, reference={record['expected_action']}, {latency:.0f} ms",flush=True)
        final_health=client.health(allow_mock=allow_mock)
        write_json(output/'final_health.json',final_health)
        if any(health.get(key)!=final_health.get(key) for key in STABLE_HEALTH_KEYS): raise ProtocolError('Model/service provenance changed during replay')
        if source_hashes(source)!=pinned: raise LabError('Capture source hashes changed during replay')
        load_snapshots(source)
        if any(sha256_file(output/'requests'/(name+'.json'))!=digest for name,digest in request_hashes.items()): raise LabError('Frozen request hash changed during replay')
    except Exception as exc:
        error=f'{type(exc).__name__}: {exc}'
    result={'complete':len(rows)==84 and error is None,'api_completed':len(rows),'error':error,'mock_backend':allow_mock,
            'real_model_evaluated':not allow_mock and bool(rows),'model_had_control':False,**summarize_prompts(rows),'decisions':rows}
    write_json(output/'summary.json',result)
    return result
