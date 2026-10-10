import pytest
from circuit_workbench.nl_core import ground_plan
from circuit_workbench.nl_schema import GraphPattern, SearchPlan
from circuit_workbench.nl_search import required_evidence
from circuit_workbench.uploads import parse_upload
from tests.unit.test_nl_intent import composite


def stage_plan(stages=2):
    data = composite()
    data['devices'] = data['devices'][:3]
    data['edges'] = data['edges'][:9]
    data['signal_stages'] = [
        {'devices': ['a', 'b'], 'input_nets': ['in1', 'in2'], 'output_nets': ['first']},
        {'devices': ['g'], 'input_nets': ['first'], 'output_nets': ['out']}]
    if stages == 3:
        data['devices'].append({'alias': 'third', 'type': 'nmos'})
        data['nets'].append('last')
        data['edges'] += [{'device': 'third', 'terminal': t, 'net': n}
                          for t, n in [('gate', 'out'), ('drain', 'last')]]
        data['signal_stages'].append({'devices': ['third'], 'input_nets': ['out'], 'output_nets': ['last']})
    pattern = GraphPattern.model_validate(data)
    text = f'Find a {stages}-stage amplifier with a differential input stage.'
    return ground_plan(text, SearchPlan(required_pattern=pattern, required_pattern_source=text))


@pytest.mark.parametrize('bad', ['VB1', 'IB2', 'VCLK1', 'LOGICD1'])
def test_stage_interface_excludes_named_non_signal_controls(bad):
    record = parse_upload(f'M1 (first {bad} tail VSS) nmos4\nM2 (other INN tail VSS) nmos4\nM3 (OUT first VDD VDD) pmos4',
                          'wrong interface', f'{bad} INN OUT VDD VSS tail')
    assert required_evidence(record, stage_plan())[2]


def test_stage_output_is_not_an_external_bias_port():
    record = parse_upload('M1 (first INP tail VSS) nmos4\nM2 (other INN tail VSS) nmos4\nM3 (VB1 first VDD VDD) pmos4',
                          'bias output', 'INP INN VB1 VDD VSS tail')
    assert required_evidence(record, stage_plan())[2]


def test_diode_reference_and_current_mirror_branch_are_not_an_extra_gain_stage():
    record = parse_upload('M1 (first INP tail VSS) nmos4\nM2 (other INN tail VSS) nmos4\nM3 (mid first VDD VDD) pmos4\nM4 (mid mid VSS VSS) nmos4\nM5 (OUT mid VSS VSS) nmos4',
                          'mirror is not a third voltage stage', 'INP INN OUT VDD VSS tail')
    assert required_evidence(record, stage_plan(3))[2]


def test_cross_coupled_output_latch_is_not_a_linear_amplifier_output():
    record = parse_upload('M1 (first INP tail VSS) nmos4\nM2 (other INN tail VSS) nmos4\nM3 (OUT first VDD VDD) pmos4\nM4 (OUT OUTB VSS VSS) nmos4\nM5 (OUTB OUT VSS VSS) nmos4',
                          'regenerative output', 'INP INN OUT OUTB VDD VSS tail')
    assert required_evidence(record, stage_plan())[2]


def test_positive_two_stage_primary_interface_still_passes():
    record = parse_upload('M1 (first INP tail VSS) nmos4\nM2 (other INN tail VSS) nmos4\nM3 (OUT first VDD VDD) pmos4',
                          'positive', 'INP INN OUT VDD VSS tail')
    assert not required_evidence(record, stage_plan())[2]


def test_count_only_capacitors_in_the_same_wiring_sentence_do_not_invent_placement():
    text = 'Find a three-stage amplifier with a differential input stage feeding two common-source gain stages and at least 2 capacitors.'
    p = ground_plan(text, SearchPlan(required_pattern=stage_plan(3).required_pattern, required_pattern_source=text))
    assert not p.clarification_questions
    assert p.required_pattern is not None
    assert any(c.entity == 'capacitor' and c.operator == 'ge' and c.value == 2 for c in p.count_constraints)
