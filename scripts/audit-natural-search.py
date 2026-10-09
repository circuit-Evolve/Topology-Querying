#!/usr/bin/env python3
"""Real-provider audit with independent, hand-derived structural oracles.

Oracles are evaluation-only, never supplied to the model/retriever. Function and
performance still require researcher judgement. No corpus mutation/ingestion.
"""
import argparse,json,time,urllib.request,urllib.error
from pathlib import Path
from circuit_ingest.models import CircuitRecord
from circuit_workbench.nl_schema import GraphPattern,SearchPlan
from circuit_workbench.nl_search import pattern_witness,meets_plan,required_evidence

ROOT=Path(__file__).resolve().parents[1]

def stage_patterns(compensated=True):
    # Independent gate/drain/source path: external input pair -> distinct gain
    # transistor -> output; cap between first-stage node and output, directly or
    # with a series resistor. This establishes wiring, not operating-point gain.
    patterns=[]
    for input_type in ('nmos','pmos'):
        for gain_type in ('nmos','pmos'):
            for rc in (False,True):
                devices=[{'alias':a,'type':t} for a,t in [('a',input_type),('b',input_type),('g',gain_type),('c','capacitor')]]
                triples=[('a','source','tail'),('a','gate','in1'),('a','drain','first'),('b','source','tail'),('b','gate','in2'),('b','drain','other'),('g','gate','first'),('g','drain','out'),('g','source','supply'),('c','p','comp' if rc else 'first'),('c','n','out')]
                if rc:devices.append({'alias':'r','type':'resistor'});triples.extend([('r','p','comp'),('r','n','first')])
                patterns.append(GraphPattern(devices=devices,nets=list(dict.fromkeys(n for _,_,n in triples)),edges=[{'device':d,'terminal':t,'net':n} for d,t,n in triples],distinct_nets=[('in1','in2'),('first','out'),('tail','first'),('supply','out'),('supply','first'),('in1','first'),('in2','other')],net_conditions=[{'net':'in1','condition':'external'},{'net':'in2','condition':'external'},{'net':'tail','condition':'not_rail'}]))
    if not compensated:
        reduced=[]
        for pattern in patterns[::2]:
            data=pattern.model_dump();data['devices']=data['devices'][:3];data['edges']=data['edges'][:9]
            reduced.append(GraphPattern.model_validate(data))
        return reduced
    return patterns

def oracles(kind):
    if kind=='two_stage':return stage_patterns()
    if kind=='cascade':return stage_patterns(False)
    if kind=='mirror':
        return [GraphPattern(devices=[{'alias':'a','type':'nmos'},{'alias':'b','type':'nmos'}],nets=['ref','source','out'],edges=[{'device':d,'terminal':t,'net':n} for d,t,n in [('a','drain','ref'),('a','gate','ref'),('a','source','source'),('b','gate','ref'),('b','source','source'),('b','drain','out')]],distinct_nets=[('ref','out'),('source','out')])]
    if kind=='pair':
        p=stage_patterns()[0].model_dump();p['devices']=p['devices'][:2];p['edges']=p['edges'][:6];p['nets']=['tail','in1','in2','first','other'];p['distinct_nets']=[('in1','in2'),('in1','first'),('in2','other')]
        # This literal request says shared sources, not a non-rail coupled tail.
        # Do not add an unrequested condition to the independent oracle.
        p['net_conditions']=[c for c in p['net_conditions'] if c['condition']=='external']
        return [GraphPattern.model_validate(p)]
    if kind=='rc':
        return [GraphPattern(devices=[{'alias':'r','type':'resistor'},{'alias':'c','type':'capacitor'}],nets=['a','junction','b'],edges=[{'device':d,'terminal':t,'net':n} for d,t,n in [('r','p','a'),('r','n','junction'),('c','p','junction'),('c','n','b')]],distinct_nets=[('a','b'),('a','junction'),('b','junction')])]
    return []

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--case',action='append');parser.add_argument('--provider',default='codex');parser.add_argument('--model',default='');parser.add_argument('--base',default='http://127.0.0.1:8766');parser.add_argument('--limit',type=int,default=10);parser.add_argument('--offline',action='store_true');parser.add_argument('--direct',action='store_true',help='Diagnostic real-service run that captures plans before database errors')
    args=parser.parse_args();cases=json.loads((ROOT/'tests/fixtures/search-audit.json').read_text());cases=[c for c in cases if not args.case or c['id'] in args.case]
    output=ROOT/'output/search-fidelity';output.mkdir(parents=True,exist_ok=True)
    def api(path,payload=None):
        req=urllib.request.Request(args.base+path,data=json.dumps(payload).encode() if payload is not None else None,headers={'Content-Type':'application/json'})
        return json.load(urllib.request.urlopen(req,timeout=30))
    for attempt in range(50):
        try:api('/api/status');break
        except OSError:
            if attempt==49:raise SystemExit('Start Circuit Atlas before running the audit.')
            time.sleep(.2)
    for case in cases:
        started=time.monotonic()
        if args.offline:
            saved=json.loads((output/(case['id']+'.json')).read_text())
            if 'result' not in saved:
                print(case['id'],'NOT VERIFIED: previous provider error',flush=True);continue
            result=saved['result']
        elif args.direct:
            import threading
            from circuit_workbench.settings import Settings
            from circuit_workbench.catalog import Catalog
            from circuit_workbench.neo4j import Neo4jService
            from circuit_workbench.retrieval import Retrieval
            from circuit_workbench.nl_search import NaturalSearch
            from circuit_workbench.nl_providers import validated_generate
            s=Settings.local();catalog=Catalog(s.state,s.corpus,s.upstream);neo=Neo4jService(s,catalog);retrieval=Retrieval(catalog);retrieval.build()
            def capture(contract,*args):
                value=validated_generate(contract,*args);(output/(case['id']+'-'+contract.__name__+'.json')).write_text(value.model_dump_json(indent=2));return value
            try:result=NaturalSearch(catalog,neo,retrieval,capture).run({'text':case['text'],'strategy':case['strategy'],'provider':args.provider,'model':args.model,'limit':args.limit},threading.Event(),lambda stage:print(case['id'],stage,flush=True))
            except Exception as exc:
                print(case['id'],'ERROR CLASS',type(exc).__name__,'CODE',getattr(exc,'code',''),flush=True);raise
            finally:neo.driver.close()
        else:
            job=api('/api/natural/jobs',{'text':case['text'],'strategy':case['strategy'],'provider':args.provider,'model':args.model,'limit':args.limit})
            while job['state'] in {'queued','running'}:
                time.sleep(.5);job=api('/api/natural/jobs/'+job['id'])
            if job['state']!='complete':
                (output/(case['id']+'.json')).write_text(json.dumps({'case':case,'job':job},indent=2));print(case['id'],'ERROR',job.get('error'),flush=True);continue
            result=job['result']
        plan=SearchPlan.model_validate(result['plan']);expected=oracles(case.get('oracle'));checks=[]
        for item in result['items']:
            detail=api('/api/circuits/'+item['id']);record=CircuitRecord.model_validate(api('/api/circuits/'+item['id']+'/record'))
            own=any(pattern_witness(record,p) for p in expected) if expected else None
            checks.append({'id':item['id'],'counts':meets_plan(record,detail['metadata'],plan),'mandatory_wiring':not required_evidence(record,plan)[2],'independent_oracle':own,'netlist':detail['netlist'],'assets':detail['assets']})
        ids=[x['id'] for x in checks];failures=[]
        if result.get('clarification_questions') and not case.get('expects_clarification'):failures.append('clarification: '+str(result['clarification_questions']))
        if case.get('expects_clarification') and not result.get('clarification_questions'):failures.append('expected contradiction clarification')
        if len(ids)<case.get('minimum',0):failures.append('expected nonempty results')
        if len(ids)>case.get('maximum',100):failures.append('expected no full result')
        if any(x in ids for x in case.get('exclude',[])):failures.append('excluded counterexample returned')
        if case.get('expected_any') and not any(x in ids for x in case['expected_any']):failures.append('known witness not in displayed top K (recall/ranking issue, not necessarily absence)')
        if any(not c['counts'] or not c['mandatory_wiring'] or c['independent_oracle'] is False for c in checks):failures.append('source/oracle verification failed')
        if case.get('needs_unverified') and not plan.unverified_requirements:failures.append('missing unsupported-spec disclosure')
        if len(result.get('partial_items',[]))<case.get('partial_minimum',0):failures.append('expected separately labelled partial results')
        evidence={'case':case,'result':result,'source_checks':checks,'failures':failures,'elapsed_seconds':round(time.monotonic()-started,1)}
        (output/(case['id']+'.json')).write_text(json.dumps(evidence,indent=2));print(case['id'],len(ids),'full',len(result.get('partial_items',[])),'partial',ids[:3],failures,flush=True)

if __name__=='__main__':main()
