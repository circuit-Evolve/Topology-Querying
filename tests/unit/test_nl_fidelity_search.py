import threading
import pytest
from circuit_workbench.nl_schema import PrototypeBatch
from circuit_workbench.nl_search import NaturalSearch,validate_prototypes,ranked_candidates
from circuit_workbench.uploads import parse_upload
from circuit_workbench.retrieval import Retrieval
from tests.unit.test_workbench import catalog
from tests.unit.test_nl_intent import grounded,PROMPT

FULL='M1 (first INP tail VSS) nmos4\nM2 (other INN tail VSS) nmos4\nM3 (out first VDD VDD) pmos4\nC1 (first out) capacitor'
PARTIAL='M1 (first INP tail VSS) nmos4\nM2 (other INN tail VSS) nmos4\nM3 (out separate VDD VDD) pmos4\nC1 (separate out) capacitor'

def setup(tmp_path,complete=False):
    db=catalog(tmp_path)
    for text in ([FULL,PARTIAL] if complete else [PARTIAL]):
        record=parse_upload(text,'fixture','INP INN out VDD VSS tail')
        db.add_upload(record,text,{'description':'fixture'})
    class Neo:
        def candidate_query(self,query,params):
            # Deliberately stale superset: local source eligibility must reject it.
            return {'rows':[{'circuit_id':r['id']} for r in db.list(limit=100)['items']],'truncated':False}
    return db,Neo()

def batch():
    return PrototypeBatch(prototypes=[{'name':str(i),'description':'draft','netlist':text,'ports':'INP INN out VDD VSS tail','rationale':'fixture'} for i,text in enumerate([FULL,FULL+'\nR1 (out VSS) resistor',PARTIAL,'M1 (a INP t VSS) nmos4\nM2 (b INN t VSS) nmos4'])])

def test_incomplete_prototype_anchors_are_rejected_against_the_same_plan():
    from circuit_workbench.nl_core import ground_plan
    accepted,diagnostics=validate_prototypes(batch(),ground_plan(PROMPT,grounded()))
    assert len(accepted)==2 and len(diagnostics)==2

@pytest.mark.parametrize('mode',['patterns','prototypes'])
def test_complete_connected_requirements_gate_both_modes(tmp_path,mode):
    db,neo=setup(tmp_path,complete=True)
    generate=lambda contract,*args:grounded() if contract.__name__=='SearchPlan' else batch()
    result=NaturalSearch(db,neo,Retrieval(db),generate).run({'text':PROMPT,'strategy':mode},threading.Event(),lambda s:None)
    assert len(result['items'])==1
    assert db.row(result['items'][0]['id'])['netlist']==FULL
    assert result['items'][0]['required_blocks']

def test_zero_full_matches_stays_zero_with_separate_partial_evidence(tmp_path):
    db,neo=setup(tmp_path)
    result=NaturalSearch(db,neo,Retrieval(db),lambda *a:grounded()).run({'text':PROMPT},threading.Event(),lambda s:None)
    assert result['items']==[] and result['total']==0
    assert result['partial_items']
    assert all(x['missing_requirements'] for x in result['partial_items'])

def test_specific_complete_pattern_beats_small_subblock_coverage():
    weak={'row':{'id':'pair'},'matches':[{}],'required_witness':None,'pattern_coverage':1.,'pattern_specificity':4,'input_evidence':2,'score':.02}
    full={'row':{'id':'connected'},'matches':[{}],'required_witness':None,'pattern_coverage':.4,'pattern_specificity':11,'input_evidence':2,'score':.01}
    assert ranked_candidates([weak,full],'patterns')[0]['row']['id']=='connected'

def test_passive_terminal_orientation_does_not_change_connectivity():
    from circuit_workbench.nl_search import pattern_witness
    from tests.unit.test_nl_intent import composite
    from circuit_workbench.nl_schema import GraphPattern
    r=parse_upload(FULL.replace('C1 (first out)','C1 (out first)'),'same physical wiring')
    assert pattern_witness(r,GraphPattern.model_validate(composite())) is not None

def test_owned_query_budget_can_exceed_console_without_allowing_writes():
    from circuit_workbench.neo4j import validate_cypher
    text='MATCH (c:Circuit)'+(' '*25000)+'RETURN c.id AS circuit_id'
    with pytest.raises(ValueError):validate_cypher(text)
    assert validate_cypher(text,max_length=100000)
    with pytest.raises(ValueError):validate_cypher('MATCH (c) DELETE c',max_length=100000)

def test_mirror_load_cannot_appear_as_a_separate_gain_stage_by_net_alias_collision():
    from circuit_workbench.nl_search import pattern_witness
    from circuit_workbench.nl_schema import GraphPattern
    from tests.unit.test_nl_intent import composite
    one_stage='M1 (first INP tail VSS) nmos4\nM2 (out INN tail VSS) nmos4\nM3 (first first VDD VDD) pmos4\nM4 (out first VDD VDD) pmos4\nC1 (out first) capacitor'
    assert pattern_witness(parse_upload(one_stage,'single mirror-loaded differential stage'),GraphPattern.model_validate(composite())) is None
