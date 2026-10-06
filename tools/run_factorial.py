#!/usr/bin/env python3
"""Replay eight paired combinations (56 requests); no robot moves here."""
from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from visual_lab.client import DecisionClient
from visual_lab.factorial import run_replay


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('source', type=Path)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--endpoint', default='http://127.0.0.1:8765/v1/decisions')
    a = p.parse_args()
    result = run_replay(a.source, a.output, DecisionClient(a.endpoint))
    print(json.dumps({key: value for key, value in result.items() if key != 'decisions'}, indent=2))
    return 0 if result['complete'] else 2


if __name__ == '__main__':
    raise SystemExit(main())
