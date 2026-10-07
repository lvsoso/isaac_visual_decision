#!/usr/bin/env python3
"""Create a self-contained audited42-request image/prompt conditions report."""
from __future__ import annotations
import argparse
import base64
import copy
import html
import json
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from visual_lab.audit import sha256_file
from visual_lab.core import ACTIONS, LabError
from visual_lab.image_ablation import IMAGE_HEALTH_KEYS, image_cells, image_request, summarize_images, summarize_text_revision, verify_image_response
from visual_lab.prompt_variants import source_hashes, validate_capture


def build_image_report(source: Path, replay: Path, output: Path, *, allow_mock=False) -> Path:
    source,replay,output=source.resolve(),replay.resolve(),output.resolve()
    if output.exists(): raise FileExistsError(output)
    if (replay/'INVALIDATED.json').exists(): raise LabError('Invalidated image replay')
    summary=json.loads((replay/'summary.json').read_text())
    manifest=json.loads((replay/'manifest.json').read_text())
    policy=manifest.get('prompt_policy','legacy_deletion')
    if summary.get('prompt_policy','legacy_deletion')!=policy: raise LabError('Prompt policy metadata mismatch')
    if summary.get('complete') is not True or summary.get('api_completed')!=42 or len(summary.get('decisions',[]))!=42:
        raise LabError('Require complete42-request image replay')
    if summary.get('mock_backend') is not bool(allow_mock) or manifest.get('synthetic_fixture') is not bool(allow_mock) or manifest['model_health'].get('is_mock') is not bool(allow_mock):
        raise LabError('Refuse mock/synthetic results unless explicitly requested')
    if summary.get('model_had_control') is not False or manifest.get('model_had_control') is not False:
        raise LabError('Image ablation must not control a robot')
    final=json.loads((replay/'final_health.json').read_text())
    if any(final.get(key)!=manifest['model_health'].get(key) for key in IMAGE_HEALTH_KEYS) or final['requests_completed']-manifest['model_health']['requests_completed']!=42:
        raise LabError('Final service provenance/count mismatch')
    bundle,review=validate_capture(source,allow_mock=allow_mock)
    if source_hashes(source)!=manifest['source_files_sha256']: raise LabError('Capture source hash mismatch')
    cells={cell['id']:cell for cell in image_cells(policy)}
    if manifest.get('cells')!=image_cells(policy): raise LabError('Frozen image design mismatch')
    expected={(cell,stage) for cell in cells for stage in range(1,8)}
    if {(row['cell'],row['decision_id']) for row in summary['decisions']}!=expected:
        raise LabError('Require every distinct cell/stage pair')
    if [(row['name'],row['cell'],row['decision_id']) for row in summary['decisions']]!=[(job['name'],job['cell'],job['decision_id']) for job in manifest['planned_order']]:
        raise LabError('Frozen inference order mismatch')
    regenerated=summarize_images(summary['decisions'],prompt_policy=policy)
    if any(summary[key]!=regenerated[key] for key in ['cells','conditional_contrasts']): raise LabError('Summary computed metrics mismatch')
    if summary.get('legacy_text_contrasts',[])!=summarize_text_revision(summary['decisions'],manifest.get('legacy_text_reference')):
        raise LabError('Legacy text prompt contrasts mismatch')
    assets,requests,responses={},{},{}
    for record in bundle['records']:
        for images in record['images'].values():
            for asset in images:
                assets[asset['path']]={'sha256':asset['sha256'],'data':'data:image/png;base64,'+base64.b64encode((source/asset['path']).read_bytes()).decode('ascii')}
    for row in summary['decisions']:
        name=f"{row['cell']}_decision_{row['decision_id']:03d}"
        for directory,key in [('requests','request'),('responses','response')]:
            if sha256_file(replay/directory/(name+'.json'))!=row[key+'_sha256']: raise LabError('Replay artifact hash mismatch: '+name)
        if row['request_sha256']!=manifest['planned_request_sha256'][name]: raise LabError('Frozen request hash mismatch')
        request=json.loads((replay/'requests'/(name+'.json')).read_text())
        raw=json.loads((replay/'responses'/(name+'.json')).read_text())
        record=bundle['records'][row['decision_id']-1]
        cell=cells[row['cell']]
        all_paths=[asset['path'] for asset in record['images'][cell['color']]]
        all_pngs=[(source/path).read_bytes() for path in all_paths]
        if request!=image_request(all_pngs,record['model_state'],bundle['view_metadata'],record['goal_guidance'],cell,prompt_policy=policy):
            raise LabError('Actual request differs from frozen prompt-policy construction')
        paths=all_paths[:cell['views']]
        parsed=verify_image_response(all_pngs[:cell['views']],raw,manifest['model_health'],allow_mock=allow_mock)
        if (parsed.action!=row['proposed_action'] or parsed.probabilities!=row['probabilities'] or parsed.confidence!=row['confidence']
                or row['expected_action']!=record['expected_action'] or row['image_count']!=cell['views']
                or row['image_sha256s']!=raw['_bridge']['image_sha256s']):
            raise LabError('Response/reference/summary mismatch')
        stored=copy.deepcopy(request);stored.pop('images');stored['image_paths']=paths
        requests[name],responses[name]=stored,raw
    payload={'summary':summary,'manifest':manifest,'final_health':final,'review':review,'actions':list(ACTIONS),'assets':assets,
             'requests':requests,'responses':responses,'records':[{'decision_id':r['decision_id'],'expected_action':r['expected_action']} for r in bundle['records']],
             'source_paths':{'capture':str(source),'replay':str(replay)},'synthetic_fixture':allow_mock}
    encoded=json.dumps(payload,ensure_ascii=False,allow_nan=False,separators=(',',':'))
    encoded=encoded.replace('&',r'\u0026').replace('<',r'\u003c').replace('>',r'\u003e').replace('\u2028',r'\u2028').replace('\u2029',r'\u2029')
    lab=Path(__file__).resolve().parents[1]/'visual_lab'
    style=(lab/'factorial_report.html').read_text().split('<style>',1)[1].split('</style>',1)[0]
    status='合成契约测试 · 非真实模型 / 非GPU证据' if allow_mock else ('真实模型 · 提示适配 · 固定42请求 · 无控制权' if policy=='modality_aware_v1' else '旧机械删图 · 无图提示失配 · 非公平纯文本基线')
    content=(lab/'image_report.html').read_text().replace('{{STYLE}}',style).replace('{{STATUS}}',html.escape(status)).replace('{{DATA}}',encoded)
    output.parent.mkdir(parents=True,exist_ok=True)
    with output.open('x',encoding='utf-8') as stream:stream.write(content)
    return output


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('source',type=Path);p.add_argument('replay',type=Path);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();print(build_image_report(a.source,a.replay,a.output))


if __name__=='__main__':main()
