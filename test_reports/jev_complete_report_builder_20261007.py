"""Offline rebuild: historical28 Intern plus independent34 Jev14, never infer."""
import argparse,json,re,tempfile
from pathlib import Path
from tools.make_text_study_report import build_study_report
from visual_lab.audit import sha256_file

def build(source,history,jev,wire,frozen,lifecycle,output):
    if output.exists():raise FileExistsError(output)
    with tempfile.TemporaryDirectory(prefix='.jev-complete-build-',dir=output.parent) as folder:
        intermediate=build_study_report(source,history/'30_goal_name_binding',history/'31_english_bound_intern',jev,Path(folder)/'combined.html')
        content=intermediate.read_text()
    match=re.search(r'<script id="report-data" type="application/json">(.*?)</script>',content,re.S)
    payload=json.loads(match.group(1));freeze=json.loads(frozen.read_text());life=json.loads(lifecycle.read_text())
    assert life['complete'] and life['api_completed']==life['actual_transport_attempts']==14
    assert life['validation_policy']=='jev_sdk_basic_v1'
    payload['new_jev_run']={'lifecycle':life,'frozen_manifest_sha256':sha256_file(frozen),
        'frozen_manifest':{k:v for k,v in freeze.items() if k not in ['requests','wire_requests']},
        'scope':'Reuse28historical Intern decisions;14new Jev decisions in independent34batch. Old failed32 and diagnostic33 excluded from scores.'}
    payload['groups']['jev']['http_evidence']={p.name:{'actual_request_body_text':(p/'request.body').read_text(),
        'raw_response_body_text':(p/'response.body').read_text(),'metadata':json.loads((p/'response_meta.json').read_text())} for p in sorted(wire.iterdir())}
    encoded=json.dumps(payload,ensure_ascii=False,allow_nan=False,separators=(',',':')).replace('&',r'\u0026').replace('<',r'\u003c').replace('>',r'\u003e').replace('\u2028',r'\u2028').replace('\u2029',r'\u2029')
    content=content[:match.start(1)]+encoded+content[match.end(1):]
    replacements={
        '42次新真实推理 · 三个分组 · 0图片':'28条既有Intern + 14条新Jev · 完整三组 · 0图片',
        '01 / 三组新结果与旧中文参考':'01 / 三组结果与旧中文参考',
        '导出42条新决策CSV':'导出42条对照决策CSV',
        '中文Intern目标绑定14次，英文Intern14次，英文Jev14次。英文两模型收到相同state / questions，所有数值与八候选保持不变。原中文14份工件仅作历史对照。':'中文Intern目标绑定14次、英文Intern14次复用已完成30/31组工件；英文Jev另开34组完成14次真实API调用。英文两模型的state / questions、数值与八候选完全相同。Jev使用jev_sdk_basic_v1，只读取官方返回值；无重试。旧32失败与33诊断不计入本报告成绩。',
        'Jev的confidence是归一化分布统计，不等于Intern的最高候选概率，也不证明在本任务上已校准。':'Jev的confidence保留官方返回值，不用概率和、argmax或公式差异拒绝结果；它不等于Intern的最高候选概率，也不证明本任务已校准。',
        "pretty(Object.fromEntries(Object.entries(D.groups).map(([g,p])=>[g,{manifest:p.manifest,final_health:p.final_health,summary:p.summary}])))":"pretty({new_jev_run:D.new_jev_run,groups:Object.fromEntries(Object.entries(D.groups).map(([g,p])=>[g,{manifest:p.manifest,final_health:p.final_health,summary:p.summary,http_evidence:p.http_evidence}]))})",
    }
    for old,new in replacements.items():
        assert old in content,old;content=content.replace(old,new)
    with output.open('x') as f:f.write(content)
    return output

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ['source','history','jev','wire','frozen','lifecycle','output']:parser.add_argument('--'+name,type=Path,required=True)
    args=parser.parse_args();print(build(**vars(args)))
