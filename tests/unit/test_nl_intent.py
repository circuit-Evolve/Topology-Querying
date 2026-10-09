import pytest
from circuit_workbench.nl_schema import SearchPlan,GraphPattern
from circuit_workbench.nl_core import ground_plan

PROMPT='Find amplifier candidates with two NMOS sharing a source, a PMOS gate connected to an NMOS drain, and a capacitor between that gate and the PMOS drain.'

def composite():
    return {'devices':[{'alias':a,'type':t} for a,t in [('a','nmos'),('b','nmos'),('g','pmos'),('c','capacitor')]],
            'nets':['tail','in1','in2','first','other','out','supply'],
            'edges':[{'device':d,'terminal':t,'net':n} for d,t,n in [('a','source','tail'),('a','gate','in1'),('a','drain','first'),('b','source','tail'),('b','gate','in2'),('b','drain','other'),('g','gate','first'),('g','drain','out'),('g','source','supply'),('c','p','first'),('c','n','out')]],
            'distinct_nets':[['in1','in2'],['first','out'],['tail','first'],['supply','out']]}

def grounded(text=PROMPT,pattern=None,quote=None):
    return SearchPlan.model_validate({'required_blocks':[{'name':'Explicit connected structure','source_quote':text if quote is None else quote,'alternatives':[pattern or composite()]}]})

def test_explicit_composite_block_is_hard_not_demoted():
    p=ground_plan(PROMPT,grounded())
    assert not p.clarification_questions
    assert len(p.required_blocks)==1
    assert any(c.entity=='capacitor' and c.operator=='ge' and c.value==1 for c in p.count_constraints)

def test_missing_model_structure_cannot_silently_search_only_a_subblock():
    p=ground_plan(PROMPT,SearchPlan())
    assert p.clarification_questions

@pytest.mark.parametrize('quote',['two NMOS sharing a source','a fabricated connected request'])
def test_incomplete_or_forged_quote_cannot_ground_whole_structure(quote):
    p=ground_plan(PROMPT,grounded(quote=quote))
    assert p.clarification_questions and not p.required_blocks

def test_quote_does_not_allow_missing_physical_device_in_pattern():
    pattern=composite();pattern['devices']=pattern['devices'][:3];pattern['edges']=pattern['edges'][:-2]
    p=ground_plan(PROMPT,grounded(pattern=pattern))
    assert p.clarification_questions

def test_independent_disconnected_patterns_cannot_claim_connected_structure():
    pattern=composite();pattern['nets']+=['x','y'];pattern['edges'][-2]['net']='x';pattern['edges'][-1]['net']='y'
    p=ground_plan(PROMPT,grounded(pattern=pattern))
    assert p.clarification_questions

@pytest.mark.parametrize('text,want',[
    ('Find a circuit with a resistor and a capacitor',{'resistor','capacitor'}),
    ('Find a circuit with an optional capacitor',set()),
    ('Find a circuit without capacitors',set()),
    ('Find a circuit with no capacitors',set()),
])
def test_device_presence_is_independent_of_model_and_not_optional_or_negative(text,want):
    p=ground_plan(text,SearchPlan())
    assert {c.entity for c in p.count_constraints if c.operator=='ge' and c.value==1}==want

def test_negative_count_clause_does_not_erase_positive_wiring():
    text=PROMPT[:-1]+' and no inductors.'
    p=ground_plan(text,SearchPlan())
    assert p.clarification_questions
    assert any(c.entity=='capacitor' and c.operator=='ge' for c in p.count_constraints)

def test_curated_embedded_mirror_does_not_replace_complete_quoted_pattern():
    text=PROMPT[:-1]+' using a current mirror.'
    model=grounded(text=text);model.required_blocks[0].name='Full amplifier with current mirror'
    result=ground_plan(text,model)
    assert any(b.source_quote==text for b in result.required_blocks)

def test_compound_device_modifiers_are_not_discrete_device_counts():
    p=ground_plan('Find an NMOS mirror with a diode-connected reference transistor',SearchPlan())
    assert not any(c.entity=='diode' for c in p.count_constraints)

def test_named_stage_count_needs_distinct_chained_signal_stages_not_an_atomic_pair():
    text='Find a two-stage op-amp with a capacitor.'
    p=ground_plan(text,SearchPlan())
    assert p.clarification_questions

def test_connected_signal_stage_assignment_can_ground_named_stage_count():
    text='Find a two-stage op-amp with a capacitor.'
    pattern=composite();pattern['signal_stages']=[{'devices':['a','b'],'input_nets':['in1','in2'],'output_nets':['first']},{'devices':['g'],'input_nets':['first'],'output_nets':['out']}]
    result=ground_plan(text,grounded(text,pattern))
    assert not result.clarification_questions and result.required_blocks
    assert {c.net for c in result.required_blocks[0].alternatives[0].net_conditions if c.condition=='external'}>={'in1','in2','out'}

def test_a_transistor_cannot_be_reused_as_two_distinct_stages():
    pattern=composite();pattern['signal_stages']=[{'devices':['a'],'input_nets':['in1'],'output_nets':['first']},{'devices':['a'],'input_nets':['in1'],'output_nets':['first']}]
    with pytest.raises(ValueError):GraphPattern.model_validate(pattern)

def test_later_stage_output_cannot_be_an_earlier_gain_devices_output_node():
    pattern=composite();pattern['signal_stages']=[{'devices':['a','b'],'input_nets':['in1','in2'],'output_nets':['first']},{'devices':['g'],'input_nets':['first'],'output_nets':['out']}]
    for edge in pattern['edges']:
        if edge['device']=='b' and edge['terminal']=='drain':edge['net']='out'
    pattern['nets'].remove('other')
    with pytest.raises(ValueError):GraphPattern.model_validate(pattern)

def test_explicit_differential_input_cannot_be_reduced_to_one_control_input():
    text='Find a two-stage amplifier with a differential input stage and a capacitor.'
    pattern=composite();pattern['signal_stages']=[{'devices':['a'],'input_nets':['in1'],'output_nets':['first']},{'devices':['g'],'input_nets':['first'],'output_nets':['out']}]
    p=ground_plan(text,grounded(text,pattern))
    assert p.clarification_questions and not p.required_blocks
