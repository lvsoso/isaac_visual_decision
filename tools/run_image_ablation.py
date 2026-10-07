#!/usr/bin/env python3
"""Run42frozen0/1/2-original-image Chinese spatial prompts, without a robot."""
from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from visual_lab.client import DecisionClient
from visual_lab.image_ablation import run_image_replay


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('source',type=Path);p.add_argument('--reference',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--endpoint',default='http://127.0.0.1:8766/v1/decisions')
    a=p.parse_args()
    result=run_image_replay(a.source,a.output,DecisionClient(a.endpoint),reference=a.reference)
    print(json.dumps({key:value for key,value in result.items() if key!='decisions'},ensure_ascii=False,indent=2))
    return 0 if result['complete'] else 2


if __name__=='__main__':raise SystemExit(main())
