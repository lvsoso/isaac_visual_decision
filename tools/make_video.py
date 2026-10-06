#!/usr/bin/env python3
"""Encode actual captured simulator frames with a locally installed ffmpeg."""
import argparse
import json
import shutil
import subprocess
from pathlib import Path


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("run_dir", type=Path)
    a = p.parse_args()
    root = a.run_dir.resolve()
    frames = sorted((root/"frames").glob("frame_*.png"))
    if not frames:
        p.error("No video frames. Run Isaac with --record-every 6; decision snapshots alone are not a video.")
    if not shutil.which("ffmpeg"):
        p.error("ffmpeg not found; install it separately. PNG files are still usable.")
    manifest = json.loads((root/"manifest.json").read_text())
    interval = manifest["record_every"]
    if interval <= 0:
        p.error("Invalid recording interval")
    fps = 1 / (manifest["config"]["physics_dt"] * interval)
    output = root/"rollout.mp4"
    subprocess.run(["ffmpeg", "-n", "-framerate", str(fps), "-i", str(root/"frames/frame_%06d.png"),
                    "-c:v", "libx264", "-pix_fmt", "yuv420p", "-vf", "pad=ceil(iw/2)*2:ceil(ih/2)*2", str(output)], check=True)
    print(f"{output}\nPlayback is simulation time; API waits and final partial sampling intervals are not represented.")

if __name__ == "__main__":
    main()
