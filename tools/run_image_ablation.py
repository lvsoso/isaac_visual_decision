#!/usr/bin/env python3
"""Run42frozen input-matched0/1/2-image prompts, without a robot."""
from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from visual_lab.client import DecisionClient
from visual_lab.image_ablation import run_image_replay
from visual_lab.modality_prompts import PROMPT_POLICIES


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('source',type=Path);p.add_argument('--reference',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--endpoint',default='http://127.0.0.1:8766/v1/decisions')
    p.add_argument('--prompt-policy',choices=PROMPT_POLICIES,default='modality_aware_v1')
    p.add_argument('--legacy-reference',type=Path,help='Required for real modality-aware prompt correction; original42-request deletion replay')
    a=p.parse_args()
    result=run_image_replay(a.source,a.output,DecisionClient(a.endpoint),reference=a.reference,legacy_reference=a.legacy_reference,prompt_policy=a.prompt_policy)
    print(json.dumps({key:value for key,value in result.items() if key!='decisions'},ensure_ascii=False,indent=2))
    return 0 if result['complete'] else 2


if __name__=='__main__':raise SystemExit(main())
