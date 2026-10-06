#!/usr/bin/env python3
"""Single real-image API probe. No robot moves; refuse mock unless explicit."""
from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from visual_lab.client import DecisionClient
from visual_lab.core import model_state, parse_decision
from visual_lab.protocol import make_request


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("image", type=Path)
    p.add_argument("--endpoint", default="http://127.0.0.1:8765/v1/decisions")
    p.add_argument("--state-json", type=Path, help="Actual model_state from the same image's observation; no fabricated proprioception")
    p.add_argument("--events", type=Path, help="Read state from the observation matching this PNG filename in events.jsonl")
    p.add_argument("--allow-mock", action="store_true")
    p.add_argument("--output", type=Path)
    a = p.parse_args()
    if a.state_json and a.events:
        p.error("Choose --state-json OR --events")
    if a.state_json:
        state = json.loads(a.state_json.read_text())
    elif a.events:
        matches = [r for line in a.events.read_text().splitlines() if line.strip()
                   for r in [json.loads(line)] if r.get("kind") == "observation" and Path(r.get("image", "")).name == a.image.name]
        if len(matches) != 1:
            p.error("Cannot find exactly one matching observation in --events")
        import hashlib
        if hashlib.sha256(a.image.read_bytes()).hexdigest() != matches[0]["image_sha256"]:
            p.error("Image bytes do not match the logged observation")
        state = matches[0]["model_state"]
    else:
        # Honest absence: do not invent a robot position for an arbitrary image.
        state = {"task": "Place the red cube inside the blue ground outline.",
                 "proprioception": "not supplied; answer only from this single image", "previous_action": None}
    client = DecisionClient(a.endpoint)
    health = client.health(allow_mock=a.allow_mock)
    raw, ms = client.predict(make_request(a.image.read_bytes(), state))
    parsed = parse_decision(raw, allow_mock=a.allow_mock)
    result = {"health": health, "http_latency_ms": ms, "response": raw, "parsed_action": parsed.action,
              "robot_was_moved": False}
    text = json.dumps(result, ensure_ascii=False, indent=2)
    print(text)
    if a.output:
        with a.output.open("x", encoding="utf-8") as f:
            f.write(text+"\n")

if __name__ == "__main__":
    main()
