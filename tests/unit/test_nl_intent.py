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


def test_unrequested_equality_between_stage_polarities_is_not_silent():
    text='Show me a two-stage op amp with fewer than 15 transistors.'
    patterns=[]
    for kind in ('nmos','pmos'):
        pattern=composite()
        for device in pattern['devices']:
            if device['type'] in {'nmos','pmos'}:device['type']=kind
        pattern['signal_stages']=[{'devices':['a','b'],'input_nets':['in1','in2'],'output_nets':['first']},
                                 {'devices':['g'],'input_nets':['first'],'output_nets':['out']}]
        patterns.append(pattern)
    raw=SearchPlan.model_validate({'required_blocks':[{'name':'Model stage alternatives','source_quote':text,'alternatives':patterns}]})
    result=ground_plan(text,raw)
    assert any('polarity' in q.lower() for q in result.clarification_questions)


def test_explicit_same_polarity_request_is_not_a_missing_variant():
    text='Find a two-stage amplifier using the same polarity in both stages.'
    patterns=[]
    for kind in ('nmos','pmos'):
        pattern=composite()
        for device in pattern['devices']:
            if device['type'] in {'nmos','pmos'}:device['type']=kind
        pattern['signal_stages']=[{'devices':['a','b'],'input_nets':['in1','in2'],'output_nets':['first']},
                                 {'devices':['g'],'input_nets':['first'],'output_nets':['out']}]
        patterns.append(pattern)
    raw=SearchPlan.model_validate({'required_blocks':[{'name':'Same-polarity stages','source_quote':text,'alternatives':patterns}]})
    assert not ground_plan(text,raw).clarification_questions

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


def test_complete_quote_cannot_hide_a_wrong_explicit_terminal_connection():
    pattern=composite()
    for edge in pattern['edges']:
        if edge['device']=='g' and edge['terminal']=='gate':edge['net']='tail'
    p=ground_plan(PROMPT,grounded(pattern=pattern))
    assert p.clarification_questions and not p.required_blocks


def test_complete_quote_cannot_hide_a_wrong_passive_endpoint():
    pattern=composite();pattern['edges'][-2]['net']='tail'
    p=ground_plan(PROMPT,grounded(pattern=pattern))
    assert p.clarification_questions and not p.required_blocks


def test_terminal_guard_is_not_specific_to_mos_or_the_audit_prompts():
    text='Find a circuit with an NPN collector connected to a PNP base.'
    pattern={'devices':[{'alias':'a','type':'npn'},{'alias':'b','type':'pnp'}],
             'nets':['link','out'],'edges':[{'device':'a','terminal':'collector','net':'link'},
             {'device':'b','terminal':'collector','net':'link'},{'device':'b','terminal':'base','net':'out'}]}
    p=ground_plan(text,grounded(text,pattern))
    assert p.clarification_questions and not p.required_blocks
    pattern['edges'][-1]['net']='link';pattern['nets'].remove('out')
    p=ground_plan(text,grounded(text,pattern))
    assert not p.clarification_questions and p.required_blocks


def test_optional_component_does_not_erase_mandatory_presence():
    p=ground_plan('Find a circuit with a resistor and an optional capacitor.',SearchPlan())
    assert {c.entity for c in p.count_constraints}=={'resistor'}


def test_optional_component_does_not_erase_preceding_mandatory_wiring():
    p=ground_plan('Find NMOS transistors sharing a source and an optional capacitor.',SearchPlan())
    assert p.clarification_questions
    assert any(c.entity=='nmos' for c in p.count_constraints)


def test_preferred_stage_count_does_not_conflict_with_mandatory_stage_count():
    from circuit_workbench.nl_intent import intent_audit
    audit=intent_audit('Find a two-stage amplifier, preferably a three-stage amplifier.')
    assert audit['signal_stage_count']==2 and not audit['ambiguous_stages']


def test_optional_stage_count_does_not_become_a_hard_requirement():
    from circuit_workbench.nl_intent import intent_audit
    assert intent_audit('Find an amplifier, preferably two-stage.')['signal_stage_count'] is None


@pytest.mark.parametrize('omitted',['supply','signal_not_rail'])
def test_complete_quote_cannot_drop_an_explicit_supply_or_signal_connection(omitted):
    text='Find a transistor whose gate connects to an external input net, drain connects to a supply rail, and source connects to a distinct external output net.'
    pattern={'devices':[{'alias':'m','type':'nmos'}],'nets':['input','drain','output'],
        'edges':[{'device':'m','terminal':t,'net':n} for t,n in [('gate','input'),('drain','drain'),('source','output')]],
        'net_conditions':[{'net':'input','condition':'external'},{'net':'output','condition':'external'}]}
    if omitted=='signal_not_rail':pattern['net_conditions'].append({'net':'drain','condition':'supply'})
    else:
        pattern['net_conditions'] += [{'net':'input','condition':'not_rail'},{'net':'output','condition':'not_rail'}]
    p=ground_plan(text,grounded(text,pattern))
    assert p.clarification_questions and not any(b.source_quote for b in p.required_blocks)


def test_explicit_supply_and_external_signals_keep_the_complete_pattern():
    text='Find a transistor whose gate connects to an external input net, drain connects to a supply rail, and source connects to a distinct external output net.'
    pattern={'devices':[{'alias':'m','type':'nmos'}],'nets':['input','drain','output'],
        'edges':[{'device':'m','terminal':t,'net':n} for t,n in [('gate','input'),('drain','drain'),('source','output')]],
        'net_conditions':[{'net':'input','condition':'external'},{'net':'input','condition':'not_rail'},
                          {'net':'output','condition':'external'},{'net':'output','condition':'not_rail'},
                          {'net':'drain','condition':'supply'}]}
    p=ground_plan(text,grounded(text,pattern))
    assert not p.clarification_questions and p.required_blocks


def test_explicit_external_clock_cannot_be_only_an_arbitrary_external_control():
    text='Find a transistor controlled by an external clock net.'
    pattern={'devices':[{'alias':'m','type':'nmos'}],'nets':['control'],
        'edges':[{'device':'m','terminal':'gate','net':'control'}],
        'net_conditions':[{'net':'control','condition':'external'}]}
    result=ground_plan(text,grounded(text,pattern))
    assert result.clarification_questions


def test_clock_named_control_remains_only_structural_naming_evidence():
    text='Find a transistor controlled by an external clock net.'
    pattern={'devices':[{'alias':'m','type':'nmos'}],'nets':['control'],
        'edges':[{'device':'m','terminal':'gate','net':'control'}],
        'net_conditions':[{'net':'control','condition':'external'},{'net':'control','condition':'clock_named'}]}
    result=ground_plan(text,grounded(text,pattern))
    assert not result.clarification_questions and result.required_blocks


def test_controlled_family_adjective_does_not_invent_an_explicit_terminal_clause():
    from circuit_workbench.nl_intent import intent_audit
    assert intent_audit('Find voltage-controlled oscillator candidates.')['wiring']==[]


def test_count_only_passives_do_not_need_invented_placement_inside_a_signal_chain():
    text='Find a two-stage amplifier with a differential input stage feeding a separate common-source stage. Require at least 2 capacitors and fewer than 20 transistors.'
    pattern=composite();pattern['devices']=pattern['devices'][:-1];pattern['edges']=pattern['edges'][:-2]
    pattern['signal_stages']=[{'devices':['a','b'],'input_nets':['in1','in2'],'output_nets':['first']},
                              {'devices':['g'],'input_nets':['first'],'output_nets':['out']}]
    result=ground_plan(text,grounded(text,pattern))
    assert not result.clarification_questions and result.required_blocks
    assert any(c.entity=='capacitor' and c.operator=='ge' and c.value==2 for c in result.count_constraints)


@pytest.mark.parametrize('other_type',['nmos','pmos'])
@pytest.mark.parametrize('text',[
    'Find one NMOS whose gate connects to an external input net, drain connects to a supply rail, and source connects to a distinct external output net.',
    'Find another NMOS whose gate connects to an external input net and drain connects to a supply rail and source connects to a distinct external output net.',
])
def test_one_transistors_requested_terminal_roles_cannot_be_split_across_devices(other_type,text):
    p={'devices':[{'alias':'a','type':'nmos'},{'alias':'b','type':other_type}],
       'nets':['input','link','supply','output'],
       'edges':[{'device':d,'terminal':t,'net':n} for d,t,n in [('a','gate','input'),('a','source','link'),('b','gate','link'),('b','drain','supply'),('b','source','output')]],
       'net_conditions':[{'net':'input','condition':'external'},{'net':'input','condition':'not_rail'},{'net':'output','condition':'external'},{'net':'output','condition':'not_rail'},{'net':'supply','condition':'supply'}]}
    result=ground_plan(text,grounded(text,p))
    assert result.clarification_questions


def test_named_differential_input_pair_is_not_an_unrelated_internal_pair():
    from circuit_workbench.nl_search import required_evidence
    from circuit_workbench.uploads import parse_upload
    text='Find comparator candidates containing a differential input pair.'
    pattern={'devices':[{'alias':'a','type':'nmos'},{'alias':'b','type':'nmos'}],
        'nets':['in_a','in_b','tail','out_a','out_b'],
        'edges':[{'device':d,'terminal':t,'net':n} for d,t,n in [('a','gate','in_a'),('b','gate','in_b'),('a','source','tail'),('b','source','tail'),('a','drain','out_a'),('b','drain','out_b')]]}
    plan=ground_plan(text,grounded(text,pattern))
    external=parse_upload('M1 (out_a INP tail VSS) nmos4\nM2 (out_b INN tail VSS) nmos4','external input pair','INP INN VSS')
    internal=parse_upload('M1 (out_a private_a tail VSS) nmos4\nM2 (out_b private_b tail VSS) nmos4','internal pair','VSS')
    assert not plan.clarification_questions and required_evidence(external,plan)[2]==[]
    assert required_evidence(internal,plan)[2]
