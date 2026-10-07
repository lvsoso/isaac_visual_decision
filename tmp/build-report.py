"""Rebuild the static report with installed Pandoc; no model or simulation."""

from pathlib import Path
import base64
import re
import subprocess

ROOT = Path(__file__).resolve().parent
STEM = "项目阶段总结与开源方案对照报告"
source = (ROOT / f"{STEM}.md").read_text(encoding="utf-8")
# Link inline citation codes to the sources already listed in the manuscript.
references = dict(re.findall(r"- \*\*(P\d+)\*\*：\[.*?\]\((.*?)\)", source))
references.update(re.findall(r"\| (R\d+) \| \[.*?\]\((.*?)\)", source))
references["R0"] = "../research/decision-embodied-20261007/index.html"
assert len(references) == 22
source = source.replace("[R7—R10]", "[R7]—[R10]")
source = re.sub(r"\[(P\d+|R\d+)\](?!\()",
                lambda m: f"[{m[1]}]({references[m[1]]})", source)
for slug in ("system-information-flow", "experiment-progression", "matched-input-results"):
    figure = (ROOT / "figures" / f"{slug}.html").read_text(encoding="utf-8")
    svg = re.search(r"<svg\b.*?</svg>", figure, re.S)
    assert svg is not None, slug
    placeholder = f"<!-- FIGURE: {slug} -->"
    assert source.count(placeholder) == 1, slug
    source = source.replace(placeholder, '<div class="diagram-container">\n' + svg[0] + '\n</div>')

result = subprocess.run(
    ["pandoc", "--from=markdown+raw_html", "--to=html5", "--standalone",
     "--toc", "--toc-depth=2", "--wrap=none", "--template=" + str(ROOT / "report-template.html"),
     "--metadata=pagetitle:Isaac视觉决策：项目总结与开源方案对照", "--metadata=lang:zh-CN"],
    input=source, text=True, capture_output=True, check=True,
)
page = result.stdout
# Pandoc nests all h2s under the manuscript h1. Flatten the reading-level TOC
# and place it after the introductory text rather than above the title.
headings = re.findall(r'<h2 id="([^"]+)">(.*?)</h2>', page)
assert len(headings) == 12
toc = '<nav aria-label="报告目录"><ul>' + ''.join(
    f'<li><a href="#{anchor}">{label}</a></li>' for anchor, label in headings) + '</ul></nav>'
page = re.sub(r'<nav aria-label="报告目录">.*?</nav>', lambda _: toc, page, flags=re.S)
details = re.search(r'<details class="toc".*?</details>', page, re.S)
assert details is not None
page = page.replace(details[0], "", 1)
page = page.replace('<h2 id=', details[0] + '\n<h2 id=', 1)
# Embed the existing representative still, not new footage or model input.
image = "../docs/videos/intern_dual_control_blue_20261007.jpg"
assert page.count(f'src="{image}"') == 1
encoded = base64.b64encode((ROOT / image).read_bytes()).decode("ascii")
page = page.replace(f'src="{image}"', f'src="data:image/jpeg;base64,{encoded}"')
# Wide source/evidence tables scroll locally; ordinary two-column tables fit.
page = re.sub(r"<table\b.*?</table>", lambda m: '<div class="table-container">' + m[0] + '</div>', page, flags=re.S)
(ROOT / f"{STEM}.html").write_text(page, encoding="utf-8")
print(f"Built {STEM}.html: 3 inline SVGs, 1 embedded still, no scripts or remote assets")
