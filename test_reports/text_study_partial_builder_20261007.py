"""Rebuild a clearly partial offline evidence report; never call a model."""
import json,re,sys,tempfile
from pathlib import Path
from visual_lab.goal_binding import build_binding_report
from visual_lab.audit import write_json
ROOT=Path('/Users/Zhuanz/Documents/zb/share-2026-10-03/2/isaac_visual_decision');folder=Path('/private/var/folders/38/gc519q3j3p96d90ybwr3whvm0000gq/T/opencode/ivd-text-study-os9yxtix');E=folder/'evidence';source=folder.parent/'ivd-static-evidence-t3lfk5gj/25_static_paired_capture';output=ROOT/'docs/reports/text_study_partial_20261007.html'
assert not output.exists();groups={}
with tempfile.TemporaryDirectory(prefix='partial-rebuild-',dir=folder) as tmp:
 for g,batch in [('zh','30_goal_name_binding'),('en','31_english_bound_intern')]:
  path=build_binding_report(source,E/batch,Path(tmp)/(g+'.html'));groups[g]=json.loads(re.search(r'<script id="report-data" type="application/json">(.*?)</script>',path.read_text(),re.S).group(1))
failure=json.loads((ROOT/'test_reports/jev_failure_20261007.json').read_text());failure['actual_first_wire_request']=json.loads((ROOT/'test_reports/jev_first_request_20261007.json').read_text())
assert failure['inference_attempts']==1 and not failure['raw_response_retained']
payload={'groups':groups,'actions':groups['zh']['actions'],'halted_jev':failure,'scope':'Partial study:28Intern valid responses, Jev1attempt rejected with missing raw body. No Jev score or model comparison.'}
encoded=json.dumps(payload,ensure_ascii=False,separators=(',',':'),allow_nan=False).replace('&',r'\u0026').replace('<',r'\u003c').replace('>',r'\u003e').replace('\u2028',r'\u2028').replace('\u2029',r'\u2029')
lab=ROOT/'visual_lab';style=(lab/'factorial_report.html').read_text().split('<style>',1)[1].split('</style>',1)[0];content=(lab/'text_study_report.html').read_text()
replacements={
 '无图目标绑定与Jev英文对照':'无图目标绑定：部分结果 / Jev未完成',
 '42次新真实推理 · 三个分组 · 0图片':'28次Intern已验证 · Jev未完成 · 0图片',
 '名称绑定、语言、模型，分开比较。':'名称绑定与语言已有结果，Jev尚无有效结果。',
 '中文Intern目标绑定14次，英文Intern14次，英文Jev14次。英文两模型收到相同state / questions，所有数值与八候选保持不变。原中文14份工件仅作历史对照。':'中文Intern目标绑定14次、英文Intern14次完成。英文Jev14份输入已预冻结，但第一份响应触发概率范围 / 总和校验后立即停止；原始正文未保存，没有可展示的概率值，不能区分API数据问题与接口兼容问题。没有重试，其余13份未发送。',
 '01 / 三组新结果与旧中文参考':'01 / 两组已完成结果与旧中文参考',
 '导出42条新决策CSV':'导出28条Intern决策CSV',
 '<option value="model">英文Intern → 英文Jev</option>':'',
 "['old','zh','en','jev']":"['old','zh','en']",
 "['zh','en','jev']":"['zh','en']",
 "choose('jev','blue',6)":"choose('zh','blue',6)",
 'text_42_decisions.csv':'text_28_intern_decisions.csv',
 '三组冻结设计 / 模型来源 / SHA256 / 首尾计数':'已完成组设计 / SHA256 / 首尾计数；Jev失败日志与确切发送正文（没有返回正文）',
 "pretty(Object.fromEntries(Object.entries(D.groups).map(([g,p])=>[g,{manifest:p.manifest,final_health:p.final_health,summary:p.summary}])))":"pretty({halted_jev:D.halted_jev,completed_groups:Object.fromEntries(Object.entries(D.groups).map(([g,p])=>[g,{manifest:p.manifest,final_health:p.final_health,summary:p.summary}]))})",
}
for old,new in replacements.items():
 assert old in content,old;content=content.replace(old,new)
content=content.replace('{{STYLE}}',style).replace('{{DATA}}',encoded)
output.write_text(content);print(output)
