#!/usr/bin/env python3
"""NO ISAAC / NO VLM: exercise the HTTP+runner+logging contract with fixtures."""
from __future__ import annotations
import argparse
import json
import sys
import threading
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from visual_lab.server import MockEngine, DecisionBridge, make_http_server
from visual_lab.client import DecisionClient
from visual_lab.runner import run_episode
from visual_lab.audit import AuditLog
from visual_lab.core import load_config
from visual_lab.png import encode_rgb_bytes


class SyntheticScene:
    """Not a simulator: state changes below are deliberately scripted test fixtures."""
    frames = 0
    recorded_frames = 0
    def __init__(self):
        self.cube = [0.5, 0.0, 0.025]
        self.finger = 0.0
    def capture(self):
        return encode_rgb_bytes(2, 2, bytes([128,128,128] * 4))
    def proprioception(self):
        return {"ee_world_position_m": [0.5, 0.0, 0.6], "finger_joint_position_rad": self.finger}
    def private_truth(self):
        return {"cube_world_position_m": self.cube, "synthetic_fixture": True}
    def execute(self, action):
        self.frames += 60
        if action == "grasp":
            self.finger = 0.5
        if action == "release":
            self.finger = 0.0
            self.cube = [0.5, 0.5, 0.025]
        return {"action": action, "status": "reached", "frames": 60}
    def settle(self):
        self.frames += 120


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--output", required=True, type=Path)
    a = p.parse_args()
    root = Path(__file__).resolve().parents[1]
    config = load_config(root/"configs/default.json")
    server = make_http_server("127.0.0.1", 0, DecisionBridge(MockEngine()))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    log = AuditLog(a.output, {"mode": "mock", "synthetic_fixture": True, "config": config, "record_every": 0})
    try:
        client = DecisionClient(f"http://127.0.0.1:{server.server_port}/v1/decisions", timeout=10)
        result = run_episode(SyntheticScene(), config, "mock", log, client, allow_mock=True)
        result["synthetic_fixture"] = True
        result["note"] = "Contract test only. No physics, rendering, visual understanding or model quality was tested."
        log.summary(result)
        assert result["api_completed"] == 7 and not result["real_model_evaluated"]
        print(json.dumps(result, indent=2, ensure_ascii=False))
    finally:
        log.close()
        server.shutdown()
        server.server_close()
        thread.join(timeout=3)

if __name__ == "__main__":
    main()
