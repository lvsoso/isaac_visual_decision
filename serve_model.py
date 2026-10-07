#!/usr/bin/env python3
"""在独立的模型 Python 环境运行，不要用 Isaac Sim 的 python.sh。"""
from __future__ import annotations
import argparse
import json
import os
from visual_lab.server import OfficialEngine, MockEngine, DecisionBridge, make_http_server


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--checkpoint", help="Complete local Intern-Decision HF snapshot")
    p.add_argument("--trust-model-code", action="store_true", help="Explicitly permit importing the reviewed checkpoint/inference.py")
    p.add_argument("--expected-inference-sha256")
    p.add_argument("--device", default="cuda")
    p.add_argument("--dtype", choices=["bfloat16", "float16", "float32"], default="bfloat16")
    p.add_argument("--max-length", type=int, default=8192)
    p.add_argument("--temperature", type=float, default=None, help="Omit to retain this checkpoint's own calibration; NOT a robot success probability")
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=8765)
    p.add_argument("--mock", action="store_true", help="NO MODEL: protocol fixture, forbidden by real simulator modes")
    p.add_argument("--allow-text-only-ablation", action="store_true", help="EXPERIMENT ONLY: allow empty images; default simulator bridge still requires RGB")
    a = p.parse_args()
    token = os.getenv("DECISION_API_TOKEN")
    if a.host not in {"127.0.0.1", "localhost"} and not token:
        p.error("Non-loopback serving requires DECISION_API_TOKEN; SSH tunnelling is preferred")
    if a.mock and a.checkpoint:
        p.error("--mock and --checkpoint cannot be combined")
    if not a.mock and not a.checkpoint:
        p.error("Provide --checkpoint, or explicitly select --mock for contract testing")
    engine = MockEngine() if a.mock else OfficialEngine(a.checkpoint, trust_model_code=a.trust_model_code,
        expected_sha=a.expected_inference_sha256, device=a.device, dtype=a.dtype,
        max_length=a.max_length, temperature=a.temperature)
    bridge = DecisionBridge(engine, token, allow_text_only=a.allow_text_only_ablation)
    server = make_http_server(a.host, a.port, bridge)
    print(json.dumps(bridge.health(), ensure_ascii=False, indent=2), flush=True)
    print(f"Listening on http://{a.host}:{server.server_port}; one inference at a time", flush=True)
    try:
        server.serve_forever(poll_interval=0.25)
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()

if __name__ == "__main__":
    main()
