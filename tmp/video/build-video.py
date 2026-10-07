#!/usr/bin/env python3
"""把阶段总结报告的要点生成中文讲解视频。

只依赖 macOS 自带的 say（婷婷语音）、本机 Chrome（无头截图）与 FFmpeg。
幻灯片内容与旁白均摘自 tmp/项目阶段总结与开源方案对照报告.md，
不包含任何新实验数据；录像片段直接复用 docs/videos 中的既有接管录像。

用法（仓库根目录）：
    python3 tmp/video/build-video.py [--work 临时目录]
"""

import argparse
import json
import subprocess
import tempfile
import wave
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT_DIR = Path(__file__).resolve().parent
OUT_MP4 = OUT_DIR / "项目阶段总结讲解.mp4"
CLIP = ROOT / "docs/videos/intern_dual_control_blue_20261007.mp4"
FRAME = ROOT / "docs/videos/intern_dual_control_blue_20261007.jpg"
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"

W, H, FPS = 1920, 1080, 30
VOICE, RATE = "Tingting", 205
SAMPLE_RATE = 22050
GAP = 0.25  # 同一场景内两句旁白之间的停顿（秒）
LEAD, TAIL = 0.6, 0.8  # 场景开头留白与结尾留白（秒）
FADE = 0.35

# 录像场景中视频的位置与尺寸（原片 640×576）
CLIP_X, CLIP_Y, CLIP_H = 120, 150, 720
CLIP_W = round(640 * CLIP_H / 576 / 2) * 2

CSS = """
:root{--paper:#f5f5f5;--card:#fff;--ink:#2d3142;--muted:#4f5d75;--accent:#eb6c36;
--ok:#2e7d5b;--bad:#b23a3a;--line:#d9dce3}
*{box-sizing:border-box;margin:0;padding:0}
html,body{width:1920px;height:1080px;overflow:hidden}
body{background:var(--paper);color:var(--ink);
font-family:'PingFang SC','Hiragino Sans GB','Heiti SC',sans-serif;
padding:84px 120px 190px;display:flex;flex-direction:column}
.eyebrow{font-size:26px;letter-spacing:.12em;color:var(--accent);font-weight:600}
h1{font-size:64px;font-weight:600;margin:14px 0 44px;line-height:1.25}
.grow{flex:1;display:flex;flex-direction:column;justify-content:center}
.row{display:flex;gap:36px;align-items:stretch}
.card{background:var(--card);border:2px solid var(--line);border-radius:22px;padding:36px 40px;flex:1}
.card h2{font-size:40px;margin-bottom:16px}
.card p,.card li{font-size:31px;line-height:1.6;color:var(--muted)}
.card ul{list-style:none}
.card li::before{content:'· ';color:var(--accent)}
.big{font-size:88px;font-weight:700;line-height:1.1}
.ok{color:var(--ok)}.bad{color:var(--bad)}.acc{color:var(--accent)}
.chip{display:inline-block;background:var(--card);border:2px solid var(--line);border-radius:14px;
padding:14px 22px;font-size:32px;font-weight:600}
.arrow{font-size:38px;color:var(--muted);padding:0 10px}
.note{font-size:28px;color:var(--muted);margin-top:30px;line-height:1.6}
.tag{display:inline-block;font-size:24px;padding:4px 14px;border-radius:10px;background:#fbe6dc;color:var(--accent);font-weight:600}
"""


def page(eyebrow, title, body):
    """拼出一张 1920×1080 幻灯片的完整 HTML。

    Args:
        eyebrow: 标题上方的小字分节名。
        title: 幻灯片主标题。
        body: 主体 HTML 片段。

    Returns:
        完整 HTML 字符串。
    """
    return (f"<!doctype html><html lang='zh-CN'><head><meta charset='utf-8'><style>{CSS}</style></head>"
            f"<body><div class='eyebrow'>{eyebrow}</div><h1>{title}</h1>"
            f"<div class='grow'>{body}</div></body></html>")


def bar(label, value, color):
    """输入匹配重测的单行横条（满分 7）。"""
    return (f"<div style='display:flex;align-items:center;gap:28px;margin:18px 0'>"
            f"<div style='width:330px;font-size:34px;font-weight:600'>{label}</div>"
            f"<div style='flex:1;height:64px;background:#e6e8ee;border-radius:12px;position:relative'>"
            f"<div style='width:{value / 7 * 100:.1f}%;height:100%;background:{color};border-radius:12px'></div></div>"
            f"<div style='width:190px;font-size:40px;font-weight:700'>{value:g} / 7</div></div>")


STEPS = ["预抓取", "靠近", "闭爪", "抬起", "搬运", "放低", "松爪"]
steps_html = "".join(
    f"<span class='chip'>{s}</span>" + ("<span class='arrow'>→</span>" if i < len(STEPS) - 1 else "")
    for i, s in enumerate(STEPS))

# 每个场景：幻灯片 HTML + 旁白分句（每句同时作为字幕）
SCENES = [
    dict(
        html=(f"<!doctype html><html lang='zh-CN'><head><meta charset='utf-8'><style>{CSS}"
              "body{padding:0;flex-direction:row}</style></head><body>"
              "<div style='flex:1;padding:150px 0 0 120px'>"
              "<div class='eyebrow'>ISAAC 仿真机械臂视觉决策 · 阶段总结</div>"
              "<h1 style='font-size:92px;margin-top:30px'>让 AI 模型<br>指挥仿真机械臂</h1>"
              "<p style='font-size:38px;color:var(--muted);line-height:1.7'>做到了什么 · 没做到什么<br>和开源项目比，处在什么位置</p>"
              "<p style='font-size:28px;color:var(--muted);margin-top:60px'>资料截至 2026-10-07 · 基于项目阶段总结与开源方案对照报告</p></div>"
              f"<div style='width:820px;display:flex;align-items:center;padding-right:110px'>"
              f"<img src='{FRAME.as_uri()}' style='width:100%;border-radius:22px;border:2px solid var(--line)'></div>"
              "</body></html>"),
        lines=["这个视频用三分钟，讲清楚我们的阶段成果。",
               "我们在 Isaac 仿真里，让一个 AI 决策模型来指挥机械臂抓放方块。",
               "它做到了哪一步，没做到哪一步，和开源项目比又处在什么位置？"]),
    dict(
        html=page("01 · 为什么要引入模型", "做了动作，不等于做成了",
                  f"<div style='display:flex;align-items:center;flex-wrap:wrap;gap:6px'>{steps_html}</div>"
                  "<p class='note' style='margin-top:18px'>固定程序：不管实际情况，按顺序把七步走完</p>"
                  "<div class='row' style='margin-top:46px'>"
                  "<div class='card'><h2>固定程序的问题</h2><p>闭爪 ≠ 抓住了<br>到了目标附近 ≠ 该松手了</p></div>"
                  "<div class='card'><h2 class='acc'>本项目的做法</h2>"
                  "<p>观察画面和机器人状态 → 模型选下一步<br>→ 执行这一步 → 再观察，形成闭环</p></div></div>"),
        lines=["传统做法是一套固定程序：预抓取、靠近、闭爪、抬起、搬运、放低、松爪，按顺序走完。",
               "但做了动作，不等于真的做成了。",
               "比如闭上爪子，并不代表已经抓住了方块。",
               "所以我们想验证：每一步先让模型看画面和机器人状态，再由它决定下一步做什么。"]),
    dict(
        html=page("02 · 谁负责什么", "模型只管“选哪一步”",
                  "<div class='row'>"
                  "<div class='card' style='border-color:var(--accent)'><h2 class='acc'>决策模型</h2>"
                  "<p>看：两个相机画面 + 机器人状态<br>做：从 8 个选项里挑下一步</p>"
                  "<p style='font-size:26px;margin-top:14px'>七个动作 + “中止”</p></div>"
                  "<div class='card'><h2>传统控制器</h2>"
                  "<p>按<b>预先设定</b>的抓取点、放置点<br>完成具体移动</p>"
                  "<p style='font-size:26px;margin-top:14px'>模型不输出坐标、关节角</p></div>"
                  "<div class='card'><h2>独立裁判</h2>"
                  "<p>按规则检查终态<br>水平误差 ≤ 5 厘米<br>高度误差 ≤ 1.5 厘米</p>"
                  "<p style='font-size:26px;margin-top:14px'>模型自己说“完成”不算</p></div></div>"
                  "<p class='note'>方块真实位置只给裁判核验，不发给模型；但整个系统仍依赖预设坐标。</p>"),
        lines=["分工要先说清楚。",
               "模型只负责选下一步做哪个动作，从八个选项里挑一个。",
               "具体往哪儿移动、怎么移动，仍由传统控制器按预先设定的位置完成。",
               "最后由独立规则检查方块是否放到位，模型自己说完成了不算。"]),
    dict(
        html=page("03 · 怎么验证", "先当“影子”，过关才接管",
                  "<div class='row' style='align-items:center'>"
                  "<div class='card'><span class='tag'>第一步</span><h2 style='margin-top:16px'>影子模式</h2>"
                  "<p>机械臂照常按固定程序走<br>模型在旁边只提建议<br>统计七步里说对几步</p></div>"
                  "<div style='text-align:center;width:250px'><div class='big acc'>7/7</div>"
                  "<p style='font-size:28px;color:var(--muted)'>准入门槛<br>→</p></div>"
                  "<div class='card'><span class='tag'>第二步</span><h2 style='margin-top:16px'>接管模式</h2>"
                  "<p>模型的选择被直接执行<br>不删选项、不重选<br>不强制跳到下一步</p></div></div>"),
        lines=["验证分两步走。",
               "第一步叫影子模式：机械臂照常按固定程序走，模型在旁边只提建议，我们看它七步里能说对几步。",
               "只有七步全对，才进入第二步，让模型真正接管，它选什么就执行什么。"]),
    dict(
        html=page("04 · 摸索过程", "关键转折：换一种说法",
                  "<div class='row'>"
                  "<div class='card'><p>最初在线测试</p><div class='big bad'>3/7</div>"
                  "<p style='margin-top:12px'>后半段常选错</p></div>"
                  "<div class='card'><p>加第二视角、加辅助信息<br>（56 次推理）</p><div class='big'>≤ 5/7</div>"
                  "<p style='margin-top:12px'>“放低、松爪”始终选错</p></div>"
                  "<div class='card' style='border-color:var(--ok)'><p>中文 + 空间描述<br>（84 次推理中的一组）</p>"
                  "<div class='big ok'>7/7</div><p style='margin-top:12px'>蓝、黄两色都全对</p></div></div>"
                  "<p class='note'>空间描述：把原始数值改写成“在左侧、在上方”这类说法。"
                  "只说明本场景有效，不代表中文普遍优于英文。</p>"),
        lines=["调到合格并不顺利。",
               "最初模型只对了三步。",
               "加第二个视角、加辅助信息，最好也只对五步，最后的放低和松爪总是选错。",
               "转折点是提示语言：改用中文，并把位置写成在左侧、在上方这样的空间描述后，蓝黄两种颜色都七步全对。",
               "不过这只说明在这个场景里有效，不代表中文普遍更好。"]),
    dict(
        html=page("05 · 图片有没有用", "看两张图，判断最准",
                  "<div style='background:var(--card);border:2px solid var(--line);border-radius:22px;padding:40px 56px'>"
                  + bar("不给图，纯文字", 1, "#b9bfcc")
                  + bar("一张图", 5.5, "#8d97ab")
                  + bar("两个视角", 7, "#eb6c36")
                  + "</div><p class='note'>一张图：蓝 5/7、黄 6/7（图中取均值 5.5）。提示也随输入一起调整，"
                    "差值不能全算作图片的作用。</p>"),
        lines=["图片到底有没有用？",
               "我们修正提示后重新测了四十二次。",
               "不给图只对一步，一张图对五到六步，两个视角七步全对。",
               "所以最终选定了中文加双视角的方案。"]),
    dict(
        html=page("06 · 最终结果", "Intern 通过并接管成功，Jev 未过门槛",
                  "<div class='row'>"
                  "<div class='card' style='border-color:var(--ok)'><h2>Intern 决策模型（本地）</h2>"
                  "<p>影子模式：蓝 <b class='ok'>7/7</b> · 黄 <b class='ok'>7/7</b></p>"
                  "<p>接管：蓝、黄各 1 回合 <b class='ok'>成功</b><br>另加 1 回合录像，<b class='ok'>成功</b></p>"
                  "<p>最终水平误差约 <b>2.2 厘米</b>（标准 ≤ 5）</p></div>"
                  "<div class='card'><h2>Jev（对照模型）</h2>"
                  "<p>影子模式：蓝 <b class='bad'>5/7</b> · 黄 <b class='bad'>5/7</b></p>"
                  "<p>常在“闭爪”时建议预抓取<br>在“抬起”时建议搬运</p>"
                  "<p><b>未达门槛，不接管</b></p></div></div>"
                  "<p class='note'>三次接管都是同一个固定场景，蓝 / 黄只是目标框颜色不同。</p>"),
        lines=["最终结果是这样的。",
               "Intern 模型在线影子测试，蓝黄两色都七步全对。",
               "随后蓝、黄各接管一次，都把方块放到了位，误差约二点二厘米，标准是五厘米以内。",
               "对照模型 Jev 只对了五步，没有达到门槛，所以没有让它接管。"]),
    dict(
        clip=True,
        html=page("07 · 真实接管录像", "",
                  f"<div style='display:flex;gap:60px;height:100%'><div style='width:{CLIP_W}px'></div>"
                  "<div style='flex:1;display:flex;flex-direction:column;justify-content:center'>"
                  "<h1 style='margin:0 0 30px;font-size:56px'>模型逐步选择<br>机械臂执行</h1>"
                  "<div class='card'><ul>"
                  "<li>画面字幕来自实际执行记录</li>"
                  "<li>模型看两个视角，视频只展示一个</li>"
                  "<li>按仿真时间播放，约 11 秒</li>"
                  "<li>省略了每次约 17 秒的模型等待</li>"
                  "<li class='acc'>不代表实时控制速度</li></ul></div></div></div>"),
        lines=["这是模型接管的真实录像。",
               "画面里每一步的字幕，都来自实际执行记录。",
               "要说明的是，视频按仿真时间播放，省掉了模型每次约十七秒的思考等待，所以不代表实时速度。"]),
    dict(
        html=page("08 · 边界", "证明了什么，还没证明什么",
                  "<div class='row'>"
                  "<div class='card' style='border-color:var(--ok)'><h2 class='ok'>✓ 已经证明</h2><ul>"
                  "<li>看图、决策、执行、评分整条链路打通</li>"
                  "<li>提示与输入方式明显影响模型选择</li>"
                  "<li>固定场景中，模型能正确选择每一步</li>"
                  "<li>失败记录、输入输出、录像均可追溯</li></ul></div>"
                  "<div class='card' style='border-color:var(--bad)'><h2 class='bad'>✗ 还没证明</h2><ul>"
                  "<li>只靠看图找到物体、算出抓放位置</li>"
                  "<li>抓空、掉落、遮挡后的恢复</li>"
                  "<li>换场景、换任务的泛化能力</li>"
                  "<li>“成功率 100%”—— 只有 3 次接管</li></ul></div></div>"),
        lines=["边界需要特别强调。",
               "我们证明的是：在一个固定场景里，模型能根据画面选对下一步。",
               "还没证明的是：模型能只靠看图找到物体位置，以及抓空、掉落之后能否恢复。",
               "三次成功，也不等于成功率百分之百。"]),
    dict(
        html=page("09 · 开源对照", "看了 6 个机器人项目和 4 个决策模型",
                  "<div class='row'>"
                  "<div class='card'><div class='big acc' style='font-size:64px'>①</div>"
                  "<h2>有相机 ≠ 模型看了图</h2><p>很多项目先把画面转成文字，或直接用仿真真值</p></div>"
                  "<div class='card'><div class='big acc' style='font-size:64px'>②</div>"
                  "<h2>关键能力藏在程序里</h2><p>如先模拟 27 种动作的后果，再交给模型挑</p></div>"
                  "<div class='card'><div class='big acc' style='font-size:64px'>③</div>"
                  "<h2>“成功”各说各话</h2><p>完全松手、仍夹着、失手掉进盘里……不能放进同一个成功率</p></div></div>"
                  "<p class='note'>只核查固定版本的源码和公开记录，未运行外部模型或机器人。</p>"),
        lines=["我们还对照了六个开源机器人项目和四个决策模型，发现三件事。",
               "第一，演示里有摄像头，不代表模型真的看了图，很多项目是先把画面转成文字，或者直接用仿真真值。",
               "第二，关键能力常藏在程序里，比如先模拟各种动作的后果，再交给模型挑。",
               "第三，各家说的成功标准不一样，不能直接比成功率。"]),
    dict(
        html=page("10 · 总结", "分层路线已走通，下一步是“看图定位”",
                  "<div class='row'>"
                  "<div class='card' style='flex:1.3'><h2>模型控制的粒度（由粗到细）</h2>"
                  "<p><span class='chip' style='border-color:var(--accent);color:var(--accent)'>选技能 ← 本项目</span></p>"
                  "<p style='margin-top:14px'><span class='chip'>选移动方向 / 子目标</span></p>"
                  "<p style='margin-top:14px'><span class='chip'>从模拟预演中挑选</span></p>"
                  "<p style='margin-top:14px'><span class='chip'>低频策略 + 高频反射</span></p>"
                  "<p style='font-size:26px;margin-top:16px'>粒度不同，不能用调用次数比高低</p></div>"
                  "<div class='card'><h2 class='acc'>下一步</h2>"
                  "<p>视觉定位、动态调整目标<br>少量位置变化验证</p>"
                  "<p style='margin-top:20px'><span class='tag'>仅记入 TODO · 尚未开始</span></p></div></div>"),
        lines=["总结一下。",
               "本项目走的是模型选技能、程序负责动作的分层路线，链路已经打通，证据都可追溯。",
               "下一步的能力边界，是让模型靠看图定位、动态调整目标。",
               "这部分目前只记录在待办里，还没有开始做。"]),
]


def run(cmd):
    """执行外部命令，失败时直接抛错。"""
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def tts(text, path):
    """用婷婷语音合成单句 16 位单声道 WAV，返回 PCM 字节。"""
    run(["say", "-v", VOICE, "-r", str(RATE), "--file-format=WAVE",
         f"--data-format=LEI16@{SAMPLE_RATE}", "-o", str(path), text])
    with wave.open(str(path)) as f:
        return f.readframes(f.getnframes())


def ass_time(t):
    """秒数转 ASS 字幕时间格式 h:mm:ss.cc。"""
    cs = round(t * 100)
    return f"{cs // 360000}:{cs // 6000 % 60:02d}:{cs // 100 % 60:02d}.{cs % 100:02d}"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--work", help="中间文件目录，默认新建临时目录")
    work = Path(parser.parse_args().work or tempfile.mkdtemp(prefix="report-video-"))
    work.mkdir(parents=True, exist_ok=True)

    pcm = bytearray()
    events, segments = [], []
    t = 0.0
    silence = lambda sec: b"\0\0" * round(sec * SAMPLE_RATE)
    for i, scene in enumerate(SCENES):
        # 渲染幻灯片
        html_path, png = work / f"s{i:02d}.html", work / f"s{i:02d}.png"
        html_path.write_text(scene["html"], encoding="utf-8")
        run([CHROME, "--headless=new", "--hide-scrollbars", "--force-device-scale-factor=1",
             f"--window-size={W},{H}", f"--screenshot={png}", html_path.as_uri()])

        # 逐句合成旁白，并记录字幕时间
        start = t
        pcm += silence(LEAD)
        t += LEAD
        for j, line in enumerate(scene["lines"]):
            audio = tts(line, work / f"a{i:02d}_{j}.wav")
            dur = len(audio) / 2 / SAMPLE_RATE
            events.append((t, t + dur, line))
            pcm += audio + silence(GAP)
            t += dur + GAP
        pcm += silence(TAIL)
        t += TAIL
        # 录像场景至少要放完整段原片
        if scene.get("clip") and t - start < 13.0:
            pcm += silence(13.0 - (t - start))
            t = start + 13.0
        segments.append((png, t - start, scene.get("clip", False)))

    wav = work / "narration.wav"
    with wave.open(str(wav), "wb") as f:
        f.setnchannels(1)
        f.setsampwidth(2)
        f.setframerate(SAMPLE_RATE)
        f.writeframes(bytes(pcm))

    # 逐场景生成无声视频片段
    parts = []
    for i, (png, dur, clip) in enumerate(segments):
        out = work / f"v{i:02d}.mp4"
        fade = f"fade=t=in:st=0:d={FADE},fade=t=out:st={dur - FADE:.3f}:d={FADE}"
        if clip:
            graph = (f"[1:v]scale={CLIP_W}:{CLIP_H},setpts=PTS-STARTPTS,tpad=start_mode=clone:start_duration=1,"
                     f"tpad=stop_mode=clone:stop_duration={dur}[c];"
                     f"[0:v][c]overlay={CLIP_X}:{CLIP_Y}:eof_action=pass,{fade},format=yuv420p")
            cmd = ["ffmpeg", "-y", "-loop", "1", "-t", f"{dur:.3f}", "-i", str(png), "-i", str(CLIP),
                   "-filter_complex", graph]
        else:
            cmd = ["ffmpeg", "-y", "-loop", "1", "-t", f"{dur:.3f}", "-i", str(png),
                   "-vf", f"{fade},format=yuv420p"]
        run(cmd + ["-r", str(FPS), "-t", f"{dur:.3f}", "-c:v", "libx264", "-preset", "medium",
                   "-crf", "20", "-an", str(out)])
        parts.append(out)

    concat = work / "concat.txt"
    concat.write_text("".join(f"file '{p}'\n" for p in parts), encoding="utf-8")

    # 字幕：底部白字半透明底
    ass = work / "subs.ass"
    ass.write_text(
        "[Script Info]\nScriptType: v4.00+\nPlayResX: 1920\nPlayResY: 1080\nWrapStyle: 0\n\n"
        "[V4+ Styles]\nFormat: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, "
        "BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, "
        "Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding\n"
        "Style: Default,Hiragino Sans GB,46,&H00FFFFFF,&H00FFFFFF,&H40322D2D,&H40322D2D,0,0,0,0,"
        "100,100,0,0,3,14,0,2,200,200,52,1\n\n"
        "[Events]\nFormat: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n"
        + "".join(f"Dialogue: 0,{ass_time(a)},{ass_time(b)},Default,,0,0,0,,{text}\n"
                  for a, b, text in events),
        encoding="utf-8")

    run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(concat), "-i", str(wav),
         "-vf", f"ass={ass}", "-c:v", "libx264", "-preset", "medium", "-crf", "20",
         "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "128k", "-ar", "44100",
         "-shortest", "-movflags", "+faststart", str(OUT_MP4)])

    (OUT_DIR / "narration.json").write_text(json.dumps(
        [{"start": round(a, 2), "end": round(b, 2), "text": text} for a, b, text in events],
        ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{OUT_MP4}  {t:.1f}s  work={work}")


if __name__ == "__main__":
    main()
