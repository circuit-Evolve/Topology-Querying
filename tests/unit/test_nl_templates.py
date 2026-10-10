import threading
import pytest
from circuit_workbench.nl_schema import SearchPlan
from circuit_workbench.nl_search import NaturalSearch, required_evidence
from circuit_workbench.uploads import parse_upload
from circuit_workbench.retrieval import Retrieval
from tests.unit.test_nl_fidelity_search import setup


@pytest.mark.parametrize('text', [
    'Find a two-stage amplifier with a capacitor between the two inputs.',
    'Find NMOS source followers with a gate connected to the output net.',
])
def test_rules_decline_wiring_they_do_not_represent(text):
    from circuit_workbench.nl_templates import deterministic_plan
    assert deterministic_plan(text) is None


def test_optional_degeneration_does_not_become_a_hard_resistor_requirement():
    from circuit_workbench.nl_templates import deterministic_plan
    plan = deterministic_plan('Find a differential amplifier. Source degeneration is optional.')
    ordinary = parse_upload('M1 (A INP tail VSS) nmos4\nM2 (B INN tail VSS) nmos4',
                            'differential pair', 'INP INN A B VSS')
    assert not required_evidence(ordinary, plan)[2]


@pytest.mark.parametrize('provider', ['codex', 'ollama', 'claude'])
def test_common_structural_search_does_not_need_a_provider_or_installed_model(tmp_path, provider):
    db, neo = setup(tmp_path, complete=True)
    calls = []
    def generate(*args):
        calls.append(args)
        return SearchPlan()
    result = NaturalSearch(db, neo, Retrieval(db), generate).run(
        {'text': 'Find two-stage amplifier candidates with a capacitor and fewer than 9 transistors.', 'provider': provider},
        threading.Event(), lambda _: None)
    assert calls == []
    assert len(result['items']) == 1
    assert result['interpreter'] == 'deterministic rules'
    assert result['items'][0]['tier'] == 'structural candidate'
    assert result['items'][0]['pattern_coverage'] > 0
    assert result['structural_matches'] == 1


def test_uncovered_custom_terminal_wiring_uses_the_selected_converter(tmp_path):
    db, neo = setup(tmp_path)
    calls = []
    def generate(*args):
        calls.append(args)
        return SearchPlan()
    result = NaturalSearch(db, neo, Retrieval(db), generate).run(
        {'text': 'Find a two-stage amplifier whose first NMOS gate connects to the final PMOS source.'},
        threading.Event(), lambda _: None)
    assert calls
    assert not result['items'] and result['clarification_questions']


def test_common_planner_keeps_all_mixed_gain_polarities():
    from circuit_workbench.nl_templates import deterministic_plan
    plan = deterministic_plan('Find a two-stage op amp with at least 2 capacitors and fewer than 27 transistors.')
    patterns = plan.required_blocks[0].alternatives
    pairs = {(p.devices[0].type, p.devices[2].type) for p in patterns}
    assert pairs >= {('nmos', 'nmos'), ('nmos', 'pmos'), ('pmos', 'nmos'), ('pmos', 'pmos'), ('npn', 'pnp')}
    assert {(x.entity, x.operator, x.value) for x in plan.count_constraints} >= {('capacitor', 'ge', 2), ('transistor', 'lt', 27)}


@pytest.mark.parametrize('extra', [
    ' with a folded-cascode first stage',
    ' with a single-ended input',
    ' and a resistor between the transistor gate and source',
    ' where the supply is connected to the output',
    ' and a compensation capacitor between the source and drain',
])
def test_unknown_topology_or_added_wiring_is_not_silently_dropped(extra):
    from circuit_workbench.nl_templates import deterministic_plan
    assert deterministic_plan('Find a two-stage op amp' + extra) is None


def test_clocked_comparator_rules_bind_real_analog_inputs_to_the_same_latch_path():
    from circuit_workbench.nl_templates import deterministic_plan
    plan = deterministic_plan('Find clocked comparator candidates with a differential input pair and regenerative latch, an external clock net controlling the tail or reset transistors, and fewer than 23 transistors.')
    good = 'M1 (Q INP tail VSS) nmos4\nM2 (QB INN tail VSS) nmos4\nM3 (Q QB VSS VSS) nmos4\nM4 (QB Q VSS VSS) nmos4\nM5 (tail CLK VSS VSS) nmos4'
    record = parse_upload(good, 'clocked comparator', 'INP INN Q QB CLK VSS')
    assert not required_evidence(record, plan)[2]
    digital = parse_upload(good.replace('INP', 'LOGICD1').replace('INN', 'LOGICD2'), 'logic latch', 'LOGICD1 LOGICD2 Q QB CLK VSS')
    assert required_evidence(digital, plan)[2]
    disconnected = good.replace('M3 (Q QB', 'M3 (R RB').replace('M4 (QB Q', 'M4 (RB R')
    assert required_evidence(parse_upload(disconnected, 'unrelated latch', 'INP INN Q QB R RB CLK VSS'), plan)[2]


def test_optional_stage_preference_does_not_exclude_a_single_stage_with_a_mirror():
    from circuit_workbench.nl_templates import deterministic_plan
    plan = deterministic_plan('Find differential amplifiers containing a current mirror with fewer than 18 transistors. Preferably use two stages; a capacitor is optional.')
    r = parse_upload('M1 (ref INP tail VSS) nmos4\nM2 (OUT INN tail VSS) nmos4\nM3 (ref ref VDD VDD) pmos4\nM4 (OUT ref VDD VDD) pmos4', 'one-stage amplifier', 'INP INN OUT VDD VSS')
    assert not required_evidence(r, plan)[2]
    assert not any(c.entity == 'capacitor' for c in plan.count_constraints)


def test_performance_is_never_fabricated_by_the_rule_engine():
    from circuit_workbench.nl_templates import deterministic_plan
    plan = deterministic_plan('Find a two-stage OTA with gain above 73 dB and phase margin at least 62 degrees, with a capacitor.')
    text = ' '.join(u.requirement for u in plan.unverified_requirements).lower()
    assert 'gain' in text and 'phase margin' in text
    assert not plan.property_constraints


def test_complete_three_stage_variants_fit_owned_query_budget_without_dropping_alternatives(tmp_path):
    from circuit_workbench.neo4j import validate_cypher
    db, neo = setup(tmp_path)
    positive = 'M1 (first INP tail VSS) nmos4\nM2 (other INN tail VSS) nmos4\nM3 (mid first VDD VDD) pmos4\nM4 (out mid VSS VSS) nmos4\nC1 (first out) capacitor\nC2 (mid out) capacitor'
    db.add_upload(parse_upload(positive, 'three-stage fixture', 'INP INN out VDD VSS'), positive, {'description': 'fixture'})
    original = neo.candidate_query
    queries = []
    def checked(query, parameters):
        validate_cypher(query, max_length=100000)
        queries.append(query)
        return original(query, parameters)
    neo.candidate_query = checked
    result = NaturalSearch(db, neo, Retrieval(db), lambda *args: SearchPlan()).run(
        {'text': 'Find a three-stage amplifier with a differential input stage feeding two common-source gain stages and at least 2 capacitors.'},
        threading.Event(), lambda _: None)
    assert result['interpreter'] == 'deterministic rules'
    assert len(result['plan']['required_blocks'][0]['alternatives']) == 16
    assert len(result['items']) == 1
    assert len(queries) >= 4


def test_hard_cypher_is_scoped_to_exact_canonical_candidates_not_the_whole_corpus(tmp_path):
    db, neo = setup(tmp_path, complete=True)
    original = neo.candidate_query
    params_seen = []
    def capture(query, parameters):
        params_seen.append(parameters)
        return original(query, parameters)
    neo.candidate_query = capture
    result = NaturalSearch(db, neo, Retrieval(db), lambda *args: SearchPlan()).run(
        {'text': 'Find a two-stage amplifier with a compensation capacitor between the stage outputs and fewer than 9 transistors.'},
        threading.Event(), lambda _: None)
    assert len(result['items']) == 1
    assert params_seen[0]['eligible_ids'] == [result['items'][0]['id']]


def test_stage_preference_does_not_become_required_during_actual_search(tmp_path):
    db, neo = setup(tmp_path)
    one = 'M1 (ref INP tail VSS) nmos4\nM2 (OUT INN tail VSS) nmos4\nM3 (ref ref VDD VDD) pmos4\nM4 (OUT ref VDD VDD) pmos4'
    db.add_upload(parse_upload(one, 'single-stage with mirror', 'INP INN OUT VDD VSS'), one, {'description': 'fixture'})
    result = NaturalSearch(db, neo, Retrieval(db), lambda *args: SearchPlan()).run(
        {'text': 'Find differential amplifiers containing a current mirror with fewer than 6 transistors. Preferably use two stages.'},
        threading.Event(), lambda _: None)
    assert len(result['items']) == 1
    assert db.row(result['items'][0]['id'])['netlist'] == one


def test_tail_only_clock_requirement_cannot_be_satisfied_by_reset_only_clocking():
    from circuit_workbench.nl_templates import deterministic_plan
    plan = deterministic_plan('Find a clocked comparator with a differential input pair and regenerative latch, with an external clock net controlling the tail transistor.')
    reset = 'M1 (Q INP tail VSS) nmos4\nM2 (QB INN tail VSS) nmos4\nM3 (Q QB VSS VSS) nmos4\nM4 (QB Q VSS VSS) nmos4\nM5 (Q CLK VSS VSS) nmos4\nM6 (QB CLK VSS VSS) nmos4\nM7 (tail VB1 VSS VSS) nmos4'
    assert required_evidence(parse_upload(reset, 'reset-only clock', 'INP INN Q QB CLK VB1 VSS'), plan)[2]


def test_optional_compensation_placement_is_not_a_hard_capacitor_requirement():
    from circuit_workbench.nl_templates import deterministic_plan
    plan = deterministic_plan('Find a two-stage amplifier. A compensation capacitor between the first and final outputs is optional.')
    no_cap = 'M1 (first INP tail VSS) nmos4\nM2 (other INN tail VSS) nmos4\nM3 (OUT first VDD VDD) pmos4'
    assert not required_evidence(parse_upload(no_cap, 'no optional cap', 'INP INN OUT VDD VSS'), plan)[2]


def test_mirror_custom_terminal_roles_are_not_replaced_by_an_atomic_recipe():
    from circuit_workbench.nl_templates import deterministic_plan
    assert deterministic_plan('Find NMOS current mirrors with a reference transistor gate connected to the output net.') is None


def test_explicit_rules_only_mode_never_falls_back_to_a_provider_for_custom_wiring(tmp_path):
    db, neo = setup(tmp_path)
    called=[]
    def generate(*args):called.append(args);return SearchPlan()
    with pytest.raises(ValueError, match='Shared rules'):
        NaturalSearch(db, neo, Retrieval(db), generate).run(
            {'text':'Find a two-stage folded-cascode op amp.','interpretation':'rules_only'},
            threading.Event(),lambda _:None)
    assert called==[]
