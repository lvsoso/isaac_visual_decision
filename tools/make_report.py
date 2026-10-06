#!/usr/bin/env python3
"""Build local HTML timeline + decisions.csv from actual saved run events."""
from __future__ import annotations
import argparse
import csv
import html
import json
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from visual_lab.core import ACTIONS


def build_report(root: Path):
    root = root.resolve()
    events = [json.loads(line) for line in (root/"events.jsonl").read_text().splitlines() if line.strip()]
    summary = json.loads((root/"summary.json").read_text())
    observations = {e["decision_id"]: e for e in events if e["kind"] == "observation"}
    decisions = [e for e in events if e["kind"] == "decision"]
    fields = ["decision_id", "mode", "model", "is_mock", "proposed_action", "executed_action", "confidence", "http_latency_ms"] + ["p_"+a for a in ACTIONS]
    with (root/"decisions.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fields)
        writer.writeheader()
        for d in decisions:
            row = {k: d.get(k) for k in fields[:8]}
            row.update({"p_"+a: (d.get("probabilities") or {}).get(a) for a in ACTIONS})
            writer.writerow(row)
    esc = lambda value: html.escape(json.dumps(value, ensure_ascii=False, indent=2))
    synthetic = bool(summary.get("mock_backend") or summary.get("synthetic_fixture"))
    introduction = ("警告：这是合成契约测试。图片、状态和决策均为测试夹具，不是 Isaac 相机、神经网络输出或机器人效果。"
                    if synthetic else "图片来自该回合保存的相机观测。baseline 未调用模型；shadow 只记录建议；visual 才让模型控制阶段。")
    content = ["<!doctype html><html lang='zh'><meta charset='utf-8'><title>视觉决策实验记录</title>",
        "<style>body{font:16px/1.65 system-ui;max-width:1150px;margin:32px auto;padding:0 20px;color:#17212e;background:#f5f7fa}h1{font-size:28px}section{background:white;padding:20px;margin:20px 0;border:1px solid #cbd5e1;border-radius:8px}img{width:min(100%,640px);height:auto}pre{white-space:pre-wrap;overflow-wrap:anywhere;font-size:13px}table{border-collapse:collapse}td,th{padding:5px 15px;border-bottom:1px solid #ddd;text-align:left}</style>",
        f"<h1>视觉决策抓放 · 实验记录</h1><p><strong>{introduction}</strong></p>",
        f"<section><h2>回合结果</h2><pre>{esc(summary)}</pre></section>"]
    if (root/"rollout.mp4").exists():
        content.append("<section><video src='rollout.mp4' controls width='800'></video><p>视频按仿真时间播放，不包含模型等待时间。</p></section>")
    by_id = {d["decision_id"]: d for d in decisions}
    for i, obs in observations.items():
        d = by_id.get(i)
        path = html.escape(obs["image"], quote=True)
        content.append(f"<section><h2>观测 {i}</h2><img src='{path}' alt='该回合保存的输入图像'>")
        if d:
            content.append(f"<p>模型建议：<b>{html.escape(str(d.get('proposed_action')))}</b>　实际执行：<b>{html.escape(str(d['executed_action']))}</b></p>")
            content.append("<table><tr><th>动作</th><th>返回的概率</th></tr>")
            for action, prob in (d.get("probabilities") or {}).items():
                content.append(f"<tr><td>{html.escape(action)}</td><td>{prob:.6f}</td></tr>")
            content.append("</table>")
        content.append(f"<details><summary>模型输入状态（baseline/capture 只保存，未发送）</summary><pre>{esc(obs['model_state'])}</pre></details>")
        content.append(f"<details><summary>仅供评估的仿真真值（未送入模型）</summary><pre>{esc(obs['private_ground_truth'])}</pre></details></section>")
    evidence = [e for e in events if e["kind"] in {"phase_end", "error", "setup_error"}]
    content.append(f"<section><h2>阶段执行与错误记录</h2><pre>{esc(evidence)}</pre></section>")
    content.append("</html>")
    (root/"report.html").write_text("\n".join(content), encoding="utf-8")
    return root/"report.html"


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("run_dir", type=Path)
    a = p.parse_args()
    print(build_report(a.run_dir))

if __name__ == "__main__":
    main()
