#!/usr/bin/env python3
"""Audit and combine three frozen text-only groups; never invoke a model."""
import argparse,json,re,sys,tempfile
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from visual_lab.core import ACTIONS,LabError
from visual_lab.goal_binding import build_binding_report

def check_english_pair(intern: dict,jev: dict):
    expected={f'{c}_images_0_decision_{j:03d}' for c in ['blue','yellow'] for j in range(1,8)}
    if (intern['summary']['language']!='en' or jev['summary']['language']!='en'
            or intern['summary']['backend']!='intern' or jev['summary']['backend']!='jev'
            or set(intern['requests'])!=expected or set(jev['requests'])!=expected): raise LabError('Require complete English Intern/Jev input pair')
    for name in expected:
        a,b=intern['requests'][name],jev['requests'][name]
        if a!=b or a.get('images')!=[] or a['state'].get('camera_views')!=[]: raise LabError('English model input pair differs or contains images')

def build_study_report(source: Path,zh: Path,en: Path,jev: Path,output: Path) -> Path:
    output=output.resolve()
    if output.exists(): raise FileExistsError(output)
    output.parent.mkdir(parents=True,exist_ok=True);groups={}
    with tempfile.TemporaryDirectory(prefix='.text-report-audit-',dir=output.parent) as tmp:
        for name,replay in [('zh',zh),('en',en),('jev',jev)]:
            checked=build_binding_report(source,replay,Path(tmp)/(name+'.html'))
            groups[name]=json.loads(re.search(r'<script id="report-data" type="application/json">(.*?)</script>',checked.read_text(),re.S).group(1))
    check_english_pair(groups['en'],groups['jev'])
    if groups['zh']['summary']['language']!='zh' or groups['zh']['summary']['backend']!='intern': raise LabError('Require Chinese binding group')
    for name in ['en','jev']:
        if groups[name]['manifest']['reference']!=groups['zh']['manifest']['reference']: raise LabError('Reference evidence differs across groups')
    groups['jev']['wire_requests']={p.stem:json.loads(p.read_text()) for p in (jev/'wire_requests').glob('*.json')}
    payload={'groups':groups,'actions':list(ACTIONS),'scope':'Goal binding, translation and language-matched model comparison are separate factors; no robot control.'}
    encoded=json.dumps(payload,ensure_ascii=False,separators=(',',':'),allow_nan=False).replace('&',r'\u0026').replace('<',r'\u003c').replace('>',r'\u003e').replace('\u2028',r'\u2028').replace('\u2029',r'\u2029')
    lab=Path(__file__).resolve().parents[1]/'visual_lab';style=(lab/'factorial_report.html').read_text().split('<style>',1)[1].split('</style>',1)[0]
    content=(lab/'text_study_report.html').read_text().replace('{{STYLE}}',style).replace('{{DATA}}',encoded)
    with output.open('x') as f:f.write(content)
    return output

def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ['source','zh','en','jev']:p.add_argument(name,type=Path)
    p.add_argument('--output',type=Path,required=True);a=p.parse_args();print(build_study_report(a.source,a.zh,a.en,a.jev,a.output))

if __name__=='__main__':main()
