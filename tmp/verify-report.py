"""Bounded local document checks; never calls a model, GPU host, or simulator."""

import concurrent.futures
import hashlib
import html
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import subprocess
import tempfile
import time
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parent
STEM = "项目阶段总结与开源方案对照报告"
SKILL = Path.home() / ".config/opencode/skills/diagram-design"
CHROME = Path("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")
FIGURES = [ROOT / "figures" / f"{slug}.html" for slug in
           ("system-information-flow", "experiment-progression", "matched-input-results")]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


class Document(HTMLParser):
    def __init__(self):
        super().__init__()
        self.ids = []
        self.links = []
        self.scripts = 0

    def handle_starttag(self, tag, attrs):
        values = dict(attrs)
        if "id" in values:
            self.ids.append(values["id"])
        if tag == "a" and "href" in values:
            self.links.append(values["href"])
        self.scripts += tag == "script"


page = ROOT / f"{STEM}.html"
before = sha(page)
subprocess.run(["python3", str(ROOT / "build-report.py")], check=True)
assert before == sha(page), "Report rebuild differs"
link_count = 0
for path in [page, *FIGURES]:
    doc = Document()
    doc.feed(path.read_text())
    assert len(set(doc.ids)) == len(doc.ids), path
    assert doc.scripts == 0, path
    for link in doc.links:
        url = urlsplit(link)
        if url.scheme or url.netloc:
            assert url.scheme == "https", link
            continue
        target = path.parent / unquote(url.path) if url.path else path
        assert target.exists(), (path, link)
        if url.fragment and target.suffix == ".html":
            other = Document()
            other.feed(target.read_text())
            assert unquote(url.fragment) in other.ids, (path, link)
        link_count += 1
skill_checks = []
for path in FIGURES:
    result = subprocess.run(["python3", str(SKILL / "scripts/self_check.py"), str(path)],
                            capture_output=True, text=True, check=True)
    skill_checks.append({"file": str(path.relative_to(REPO)), "result": result.stdout.strip()})

# Verify the bar chart lengths against the archived real-response summary.
archived = json.loads((REPO / "test_reports/gpu_modality_prompts_20261006.json").read_text())
assert archived["api_completed"] == 42 and not archived["model_had_control"]
cells = sorted(archived["summary"]["cells"], key=lambda c: (c["views"], c["color"]))
real_counts = [cell["baseline_agreement"] for cell in cells]
assert real_counts == [1, 1, 5, 6, 7, 7]
widths = re.findall(r'<rect x="304" y="(?:168|236|304|372|440|508)" width="(\d+)"', FIGURES[2].read_text())
assert [int(width) / 112 for width in widths] == real_counts
assert "| 单图，明确只有第一相机 | 5/7 | 6/7 |" in (ROOT / f"{STEM}.md").read_text()

folder = Path(tempfile.mkdtemp(prefix="ivd-summary-report-",
    dir="/private/var/folders/38/gc519q3j3p96d90ybwr3whvm0000gq/T/opencode"))
check_script = r"""<script>window.addEventListener('load',()=>{const checks=[];
const check=(name,value)=>{if(!value)throw Error(name);checks.push(name)};
try{const svgs=[...document.querySelectorAll('svg')];
check('SVG count',svgs.length===EXPECTED);
check('no global horizontal overflow',document.documentElement.scrollWidth<=innerWidth+1);
check('accessible SVG labels',svgs.every(s=>s.getAttribute('role')==='img'&&s.getAttribute('aria-labelledby').split(' ').every(id=>document.getElementById(id))));
check('local SVG scrolling and width contract',svgs.every(s=>{const c=s.parentElement,w=s.viewBox.baseVal.width;return c.classList.contains('diagram-container')&&getComputedStyle(c).overflowX==='auto'&&parseFloat(getComputedStyle(s).minWidth)===w}));
for(const s of svgs){const c=s.parentElement;if(c.scrollWidth>c.clientWidth){c.scrollLeft=c.scrollWidth-c.clientWidth;check('reachable diagram right edge',c.scrollLeft>0);c.scrollLeft=0}}
const bboxes=svgs.map(s=>[...s.querySelectorAll('text')].map(t=>({text:t.textContent,b:t.getBBox()})));
check('SVG labels remain within canvas',bboxes.every((texts,i)=>texts.every(({b})=>b.x>=0&&b.y>=0&&b.x+b.width<=svgs[i].viewBox.baseVal.width&&b.y+b.height<=svgs[i].viewBox.baseVal.height)));
check('no SVG text-to-text overlap',bboxes.every(texts=>texts.every(({b:a},i)=>texts.slice(i+1).every(({b})=>!(a.x<b.x+b.width-.5&&b.x<a.x+a.width-.5&&a.y<b.y+b.height-.5&&b.y<a.y+a.height-.5)))));
check('CJK readable type floor',svgs.every(s=>[...s.querySelectorAll('text')].every(t=>!/[\u3400-\u9fff]/.test(t.textContent)||parseFloat(getComputedStyle(t).fontSize)>=12)));
check('no remote resource elements',[...document.querySelectorAll('[src],link[href]')].every(e=>(e.getAttribute('src')||e.getAttribute('href')).startsWith('data:')));
if(EXPECTED===3){check('embedded real still',document.images.length===1&&document.images[0].complete&&document.images[0].naturalWidth===640);check('7 main chapters plus summary and appendices',document.querySelectorAll('article h2').length===12);check('12 visible chapter navigation links',[...document.querySelectorAll('.toc nav a')].length===12&&[...document.querySelectorAll('.toc nav a')].every(a=>a.getBoundingClientRect().height>0));check('deferred scope retained',document.body.textContent.includes('暂缓，不启动新实验'));check('print styles present',document.querySelector('style').textContent.includes('@media print'));}
const o=document.createElement('pre');o.id='report-check';o.hidden=true;o.textContent=JSON.stringify({passed:true,checks,viewport:[innerWidth,innerHeight],fontFallback:getComputedStyle(svgs[0].querySelector('text')).fontFamily});document.body.append(o);
}catch(e){const o=document.createElement('pre');o.id='report-check';o.textContent=JSON.stringify({passed:false,error:String(e),checks});document.body.append(o)}});</script>"""


def browser(item):
    name, path, width, expected = item
    fixture = path.read_text().replace("style-src 'unsafe-inline';", "style-src 'unsafe-inline'; script-src 'unsafe-inline';")
    fixture = fixture.replace("</body>", check_script.replace("EXPECTED", str(expected)) + "</body>")
    local = folder / f"{name}.html"
    local.write_text(fixture)
    dom, shot, err = [folder / f"{name}.{suffix}" for suffix in ("dom.html", "png", "stderr.log")]
    command = [str(CHROME), "--headless", "--no-first-run", "--no-default-browser-check",
               "--disable-gpu", "--disable-background-networking", "--disable-component-update",
               "--user-data-dir=" + str(folder / f"{name}-profile"), "--window-size=" + str(width) + ",1100",
               "--virtual-time-budget=2000", "--screenshot=" + str(shot), "--dump-dom", local.as_uri()]
    process = None
    try:
        with dom.open("w") as out, err.open("w") as errors:
            process = subprocess.Popen(command, stdout=out, stderr=errors)
            deadline = time.monotonic() + 60
            while True:
                match = re.search(r'<pre id="report-check"[^>]*>(.*?)</pre>', dom.read_text(), re.S)
                if match and shot.exists() and shot.stat().st_size:
                    result = json.loads(html.unescape(match[1]))
                    assert result["passed"], result
                    result["screenshot_sha256"] = sha(shot)
                    return name, result
                assert process.poll() is None, f"{name}: browser ended before checks"
                if time.monotonic() > deadline:
                    raise TimeoutError(name)
                time.sleep(.1)
    finally:
        if process is not None and process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)


cases = [("report-desktop", page, 1440, 3), ("report-narrow", page, 500, 3)]
cases += [(p.stem, p, 1440, 1) for p in FIGURES]
with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
    results = dict(pool.map(browser, cases))
report = {"kind": "static_document_verification", "scope": "Document only; not model quality or new GPU validation",
          "report_sha256": sha(page), "deterministic_rebuild": True, "local_links_checked": link_count,
          "diagram_skill_checks": skill_checks, "chart_counts": [1, 1, 5, 6, 7, 7],
          "browser": results, "fixture_dir": str(folder), "extra_model_calls": 0,
          "extra_isaac_runs": 0, "print_pdf_not_verified": True,
          "lifecycle": "Owned browser processes are bounded and cleaned; no claim of natural clean CLI exit"}
(ROOT / "verification.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
print(json.dumps(report, ensure_ascii=False, indent=2))
