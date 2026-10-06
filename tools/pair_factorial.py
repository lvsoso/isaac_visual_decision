#!/usr/bin/env python3
"""Validate equal physical trajectories and actual color pixels before pairing."""
from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from visual_lab.factorial import pair_static_captures


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('blue', type=Path)
    p.add_argument('yellow', type=Path)
    p.add_argument('--output', type=Path, required=True)
    a = p.parse_args()
    result = pair_static_captures(a.blue, a.yellow, a.output)
    print(json.dumps(result, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
