#!/usr/bin/env python3
"""Create a self-contained, verified 84-request prompt comparison HTML."""
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
from visual_lab.prompt_variants import prompt_cells, prompt_request, source_hashes, summarize_prompts, validate_capture, verify_response


def build_prompt_report(source: Path,replay: Path,output: Path,*,allow_mock=False) -> Path:
    source,replay,output=source.resolve(),replay.resolve(),output.resolve()
    if output.exists(): raise FileExistsError(output)
    if (replay/'INVALIDATED.json').exists(): raise LabError('Invalidated prompt replay')
    summary=json.loads((replay/'summary.json').read_text())
    manifest=json.loads((replay/'manifest.json').read_text())
    if summary.get('complete') is not True or summary.get('api_completed')!=84 or len(summary.get('decisions',[]))!=84:
        raise LabError('Require complete 84-request prompt replay')
    if summary.get('mock_backend') is not bool(allow_mock) or manifest['model_health'].get('is_mock') is not bool(allow_mock):
        raise LabError('Refuse mock/synthetic results unless explicitly requested')
    bundle,review=validate_capture(source,allow_mock=allow_mock)
    if source_hashes(source)!=manifest['source_files_sha256']: raise LabError('Capture source hash mismatch')
    cells={cell['id']:cell for cell in prompt_cells()}
    if manifest.get('cells')!=prompt_cells(): raise LabError('Frozen prompt design mismatch')
    expected={(cell,stage) for cell in cells for stage in range(1,8)}
    actual={(row['cell'],row['decision_id']) for row in summary['decisions']}
    if actual!=expected: raise LabError('Require every distinct cell/stage pair')
    regenerated=summarize_prompts(summary['decisions'])
    if any(summary[key]!=regenerated[key] for key in ['cells','conditional_contrasts']): raise LabError('Summary computed metrics mismatch')
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
        paths=[asset['path'] for asset in record['images'][cell['color']]]
        pngs=[(source/path).read_bytes() for path in paths]
        if request!=prompt_request(pngs,record['model_state'],bundle['view_metadata'],record['goal_guidance'],cell):
            raise LabError('Actual request differs from frozen prompt construction')
        parsed=verify_response(pngs,raw,manifest['model_health'],allow_mock=allow_mock)
        if parsed.action!=row['proposed_action'] or parsed.probabilities!=row['probabilities'] or row['expected_action']!=record['expected_action']:
            raise LabError('Response/reference/summary mismatch')
        stored=copy.deepcopy(request);stored.pop('images');stored['image_paths']=paths
        requests[name],responses[name]=stored,raw
    payload={'summary':summary,'manifest':manifest,'review':review,'actions':list(ACTIONS),'assets':assets,'requests':requests,'responses':responses,
             'records':[{'decision_id':r['decision_id'],'expected_action':r['expected_action']} for r in bundle['records']],
             'source_paths':{'capture':str(source),'replay':str(replay)},'synthetic_fixture':allow_mock}
    encoded=json.dumps(payload,ensure_ascii=False,allow_nan=False,separators=(',',':'))
    encoded=encoded.replace('&','\\u0026').replace('<','\\u003c').replace('>','\\u003e').replace('\u2028','\\u2028').replace('\u2029','\\u2029')
    lab=Path(__file__).resolve().parents[1]/'visual_lab'
    style=(lab/'factorial_report.html').read_text().split('<style>',1)[1].split('</style>',1)[0]
    status='合成契约测试 · 非真实模型 / 非GPU证据' if allow_mock else '真实模型 · 原始RGB · 固定84请求 · 模型无控制权'
    content=(lab/'prompt_report.html').read_text().replace('{{STYLE}}',style).replace('{{STATUS}}',html.escape(status)).replace('{{DATA}}',encoded)
    output.parent.mkdir(parents=True,exist_ok=True)
    with output.open('x',encoding='utf-8') as stream: stream.write(content)
    return output


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('source',type=Path);p.add_argument('replay',type=Path);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();print(build_prompt_report(a.source,a.replay,a.output))


if __name__=='__main__': main()
