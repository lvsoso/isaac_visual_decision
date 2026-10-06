"""Immutable run directories and explicit observation/decision/action records."""
from __future__ import annotations
import csv
import hashlib
import json
import os
import platform
import sys
from pathlib import Path
from datetime import datetime, timezone
from .core import ACTIONS


def sha256_file(path: str | Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def write_json(path: Path, value: dict) -> None:
    temp = path.with_suffix(path.suffix + ".tmp")
    with temp.open("w", encoding="utf-8") as f:
        json.dump(value, f, indent=2, ensure_ascii=False, allow_nan=False)
        f.write("\n")
    os.replace(temp, path)


class AuditLog:
    def __init__(self, directory: Path, manifest: dict):
        self.root = Path(directory).expanduser().resolve()
        # 禁止覆盖已有实验；没有“自动追加到上一回合”的歧义。
        self.root.mkdir(parents=True, exist_ok=False)
        (self.root / "images").mkdir()
        (self.root / "requests").mkdir()
        (self.root / "responses").mkdir()
        (self.root / "frames").mkdir()
        manifest = dict(manifest)
        manifest.update({"created_utc": datetime.now(timezone.utc).isoformat(),
                         "python": sys.version, "platform": platform.platform()})
        write_json(self.root / "manifest.json", manifest)
        self._events = (self.root / "events.jsonl").open("w", encoding="utf-8", buffering=1)

    def event(self, kind: str, **data) -> None:
        row = {"kind": kind, "utc": datetime.now(timezone.utc).isoformat(), **data}
        self._events.write(json.dumps(row, ensure_ascii=False, allow_nan=False) + "\n")
        self._events.flush()

    def observation(self, index: int, png: bytes, state: dict, private_ground_truth: dict) -> Path:
        path = self.root / "images" / f"decision_{index:03d}.png"
        path.write_bytes(png)
        self.event("observation", decision_id=index, image=str(path.relative_to(self.root)),
                   image_sha256=hashlib.sha256(png).hexdigest(), model_state=state,
                   private_ground_truth=private_ground_truth)
        return path

    def request(self, index: int, value: dict) -> None:
        # 保存确切请求，便于离线回放。图片也单独存一份；无认证 token。
        write_json(self.root / "requests" / f"decision_{index:03d}.json", value)

    def response(self, index: int, value: dict) -> None:
        write_json(self.root / "responses" / f"decision_{index:03d}.json", value)

    def summary(self, value: dict) -> None:
        write_json(self.root / "summary.json", value)
        flat = {k: v for k, v in value.items() if not isinstance(v, (dict, list))}
        for axis, number in zip("xyz", value.get("final_cube_position_m", [])):
            flat[f"final_cube_{axis}_m"] = number
        with (self.root / "episodes.csv").open("w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=list(flat))
            writer.writeheader()
            writer.writerow(flat)

    def close(self) -> None:
        if not self._events.closed:
            self._events.close()
