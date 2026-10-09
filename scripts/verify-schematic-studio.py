#!/usr/bin/env python3
"""Run a real local Studio job and print structural checks/artifact identifiers."""
import argparse
import json
import time
import urllib.request


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source',default='')
    parser.add_argument('--prompt',default='Draw a two-transistor NMOS current mirror with exactly 2 transistors, an external reference-current input and one output. No performance claims.')
    parser.add_argument('--polish',action='store_true')
    parser.add_argument('--provider',choices=['codex','claude','ollama'],default='codex')
    parser.add_argument('--model',default='')
    parser.add_argument('--base',default='http://127.0.0.1:8766')
    args=parser.parse_args()
    def api(path,payload=None):
        request=urllib.request.Request(args.base+path,data=json.dumps(payload).encode() if payload else None,headers={'Content-Type':'application/json'})
        return json.load(urllib.request.urlopen(request,timeout=15))
    payload={'mode':'library' if args.source else 'prompt','source_id':args.source,'prompt':args.prompt,'polish':args.polish,'provider':args.provider,'model':args.model}
    for attempt in range(50):
        try:
            if api('/api/status').get('application')=='circuit-atlas':break
        except OSError:
            if attempt==49:raise SystemExit('Start Circuit Atlas before running this check.')
            time.sleep(.2)
    job=api('/api/studio/jobs',payload);started=time.monotonic()
    while job['state'] in {'queued','running'}:
        time.sleep(.5);job=api('/api/studio/jobs/'+job['id'])
    if job['state']!='complete':raise SystemExit(job['error'] or job['state'])
    result=job['result']
    print('artifact',result['id'],'seconds',round(time.monotonic()-started,1))
    print('source',result['source'])
    print('checks',result['checks'])
    print('warnings',result['warnings'])
    print('netlist\n'+result['netlist'])
    print('preview',args.base+'/#studio/artifact/'+result['id'])


if __name__=='__main__':main()
