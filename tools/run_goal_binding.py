#!/usr/bin/env python3
"""Replay14frozen text-only goal identity requests; never run a robot."""
import argparse,json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from visual_lab.client import DecisionClient
from visual_lab.goal_binding import run_binding_replay,build_binding_report
from visual_lab.jev import JevClient

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('source',type=Path);p.add_argument('--reference',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--language',choices=['zh','en'],default='zh');p.add_argument('--backend',choices=['intern','jev'],default='intern');p.add_argument('--key-file',type=Path)
    p.add_argument('--endpoint',default='http://127.0.0.1:8766/v1/decisions');a=p.parse_args()
    if a.backend=='jev' and a.language!='en':p.error('This frozen Jev comparison requires English')
    client=JevClient(key_file=a.key_file) if a.backend=='jev' else DecisionClient(a.endpoint)
    result=run_binding_replay(a.source,a.reference,a.output,client,language=a.language)
    print(json.dumps({k:v for k,v in result.items() if k!='decisions'},ensure_ascii=False,indent=2))
    if result['complete']:build_binding_report(a.source,a.output,a.output/'report.html')
    return 0 if result['complete'] else 2

if __name__=='__main__':raise SystemExit(main())
