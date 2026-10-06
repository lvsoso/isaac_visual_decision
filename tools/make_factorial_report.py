#!/usr/bin/env python3
"""Build an offline eight-cell HTML report from verified original run artifacts."""
from __future__ import annotations
import argparse
import base64
import copy
import hashlib
import html
import json
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from visual_lab.audit import sha256_file
from visual_lab.core import ACTIONS, LabError, parse_decision
from visual_lab.factorial import factor_cells, load_snapshots


def build_factorial_report(source: Path, replay: Path, output: Path, *, allow_mock=False) -> Path:
    source, replay, output = source.resolve(), replay.resolve(), output.resolve()
    if output.exists():
        raise FileExistsError(output)
    bundle = load_snapshots(source)
    manifest = json.loads((replay/'manifest.json').read_text())
    summary = json.loads((replay/'summary.json').read_text())
    if summary.get('complete') is not True or summary.get('api_completed') != 56 or len(summary.get('decisions', [])) != 56:
        raise LabError('Require a complete 56-decision experiment')
    if bool(summary.get('mock_backend')) != bool(allow_mock) or manifest['model_health'].get('is_mock') is not bool(allow_mock):
        raise LabError('Refuse mock/synthetic data unless explicitly requested')
    capture_manifest = json.loads((source/'manifest.json').read_text())
    if not allow_mock and (capture_manifest.get('synthetic_fixture') or capture_manifest.get('kind') != 'paired_factorial_capture'):
        raise LabError('Refuse synthetic/non-production capture provenance')
    for name in ['manifest.json', 'snapshots.json', 'summary.json']:
        if manifest['source_'+name.split('.')[0]+'_sha256'] != sha256_file(source/name):
            raise LabError('Source hash mismatch: '+name)
    review = None
    if not allow_mock:
        review = json.loads((source/'render_review.json').read_text())
        if review.get('approved') is not True or review.get('reviewed_color_pairs') != 14 or review.get('snapshots_sha256') != sha256_file(source/'snapshots.json'):
            raise LabError('Require pinned approval of all 14 actual color pairs')
    cells = {cell['id']: cell for cell in factor_cells()}
    if {cell['id'] for cell in summary['cells']} != set(cells):
        raise LabError('Require all eight factorial cells')
    assets, requests, responses = {}, {}, {}
    for record in bundle['records']:
        for color_assets in record['images'].values():
            for asset in color_assets:
                png = (source/asset['path']).read_bytes()
                if hashlib.sha256(png).hexdigest() != asset['sha256']:
                    raise LabError('Image hash mismatch')
                assets[asset['path']] = {'sha256': asset['sha256'],
                    'data': 'data:image/png;base64,'+base64.b64encode(png).decode('ascii')}
    for row in summary['decisions']:
        cell = cells[row['cell']]
        name = f"{row['cell']}_decision_{row['decision_id']:03d}"
        for directory, key in [('requests', 'request'), ('responses', 'response')]:
            if sha256_file(replay/directory/(name+'.json')) != row[key+'_sha256']:
                raise LabError('Replay artifact hash mismatch: '+name)
        request = json.loads((replay/'requests'/(name+'.json')).read_text())
        raw = json.loads((replay/'responses'/(name+'.json')).read_text())
        decision = parse_decision(raw, allow_mock=allow_mock)
        if decision.action != row['proposed_action'] or decision.probabilities != row['probabilities']:
            raise LabError('Response/summary decision mismatch')
        record = bundle['records'][row['decision_id']-1]
        paths = [asset['path'] for asset in record['images'][cell['color']][:cell['views']]]
        if [image['data'] for image in request['images']] != [assets[path]['data'].split(',', 1)[1] for path in paths]:
            raise LabError('Request image bytes do not match the original capture')
        stored = copy.deepcopy(request)
        stored.pop('images')  # Deduplicate 28 PNGs; exact images remain in assets.
        stored['image_paths'] = paths
        requests[name], responses[name] = stored, raw
    if len(requests) != 56:
        raise LabError('Require 56 distinct cell/stage pairs')
    payload = {'summary': summary, 'manifest': manifest, 'review': review, 'actions': list(ACTIONS),
               'assets': assets, 'requests': requests, 'responses': responses,
               'records': [{key: record[key] for key in ['decision_id', 'expected_action', 'images']} for record in bundle['records']],
               'view_metadata': bundle['view_metadata'],
               'source_paths': {'capture': str(source), 'replay': str(replay)},
               'synthetic_fixture': allow_mock}
    # JSON script content is data, never HTML; prevent closing-script injection.
    encoded = json.dumps(payload, ensure_ascii=False, allow_nan=False, separators=(',', ':'))
    encoded = encoded.replace('&', '\\u0026').replace('<', '\\u003c').replace('>', '\\u003e').replace('\u2028', '\\u2028').replace('\u2029', '\\u2029')
    template = Path(__file__).resolve().parents[1]/'visual_lab/factorial_report.html'
    status = '合成契约测试 · 非真实模型 / 非GPU证据' if allow_mock else '真实模型 · 原始RGB · 模型无控制权'
    content = template.read_text().replace('{{STATUS}}', html.escape(status)).replace('{{DATA}}', encoded)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open('x', encoding='utf-8') as stream:
        stream.write(content)
    return output


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('source', type=Path)
    p.add_argument('replay', type=Path)
    p.add_argument('--output', type=Path, required=True)
    a = p.parse_args()
    print(build_factorial_report(a.source, a.replay, a.output))


if __name__ == '__main__':
    main()
