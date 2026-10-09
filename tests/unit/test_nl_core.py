"""Same physical requirements regardless of the model's interpretation."""
import pytest


@pytest.mark.parametrize("prompt,want",[
    ("comparator with more than 8 transistors and no inductors",[("transistor","gt",8),("inductor","eq",0)]),
    ("amplifier with at least one capacitor and fewer than 20 transistors",[("capacitor","ge",1),("transistor","lt",20)]),
    ("between 10 and 20 MOS transistors and exactly two resistors",[("mos","ge",10),("mos","le",20),("resistor","eq",2)]),
    ("at most 5 NMOS and 4 PMOS",[("nmos","le",5),("pmos","eq",4)]),
    ("2 output ports",[]),
])
def test_parse_counts_has_literal_independent_expectations(prompt,want):
    from circuit_workbench.nl_core import parse_counts
    counts,_=parse_counts(prompt)
    assert [(c.entity,c.operator,c.value) for c in counts] == want


def test_model_cannot_weaken_or_drop_explicit_counts():
    from circuit_workbench.nl_core import ground_plan
    from circuit_workbench.nl_schema import SearchPlan
    incorrect=SearchPlan.model_validate({"count_constraints":[{"entity":"transistor","operator":"ge","value":8}]})
    result=ground_plan("comparator with more than 8 transistors and no inductors",incorrect)
    assert [(c.entity,c.operator,c.value) for c in result.count_constraints] == [("transistor","gt",8),("inductor","eq",0)]


def test_placeholders_and_contradictions_require_clarification():
    from circuit_workbench.nl_core import ground_plan
    from circuit_workbench.nl_schema import SearchPlan
    assert ground_plan("with more than x transistors",SearchPlan()).clarification_questions
    assert ground_plan("at least 10 resistors and fewer than 3 resistors",SearchPlan()).clarification_questions


def test_common_mirror_pattern_is_identical_for_different_provider_plans():
    from circuit_workbench.nl_core import ground_plan
    from circuit_workbench.nl_schema import SearchPlan
    a=ground_plan("Find an NMOS current mirror with 2 transistors",SearchPlan(semantic_text="random model text"))
    b=ground_plan("Find an NMOS current mirror with 2 transistors",SearchPlan(requested_function="different model wording"))
    assert a.hypotheses == b.hypotheses
    assert len(a.hypotheses) == 1
    assert a.semantic_text == b.semantic_text


def test_mirror_inside_opamp_is_required_block_not_parent_function():
    from circuit_workbench.nl_core import ground_plan
    from circuit_workbench.nl_schema import SearchPlan
    result=ground_plan("Find an op amp containing a current mirror with fewer than 20 transistors",SearchPlan(requested_function="op amp"))
    assert result.requested_function == "op amp"
    assert result.required_blocks[0].name == "Current mirror"
    assert len(result.required_blocks[0].alternatives) == 4


@pytest.mark.parametrize('text',[
    'Find an op amp without a current mirror',
    'Find an op amp with no current mirror',
])
def test_negated_block_is_not_inverted_into_compulsory_containment(text):
    from circuit_workbench.nl_core import ground_plan
    from circuit_workbench.nl_schema import SearchPlan
    result=ground_plan(text,SearchPlan())
    assert not result.required_blocks
    assert result.clarification_questions  # V1 has no absence-of-block contract.


@pytest.mark.parametrize('text',[
    'Find an op amp. A current mirror is optional.',
    'Find an op amp with an optional current mirror.',
])
def test_optional_block_does_not_filter_eligible_circuits(text):
    from circuit_workbench.nl_core import ground_plan
    from circuit_workbench.nl_schema import SearchPlan
    result=ground_plan(text,SearchPlan())
    assert not result.required_blocks and not result.clarification_questions


def test_model_cannot_promote_an_unrequested_block_to_hard_eligibility():
    from circuit_workbench.nl_core import ground_plan,load_rulebook
    from circuit_workbench.nl_schema import SearchPlan,RequiredBlock,GraphPattern
    pattern=next(p for p in load_rulebook()['primitives'] if p['id']=='mos_diff_pair')['patterns'][0]
    model=SearchPlan(required_blocks=[RequiredBlock(name='inferred differential pair',alternatives=[GraphPattern.model_validate(pattern)])])
    result=ground_plan('Find op amp candidates with fewer than 20 transistors',model)
    assert not result.required_blocks
    assert any(h.pattern==model.required_blocks[0].alternatives[0] for h in result.hypotheses)


def test_full_rulebook_patterns_match_actual_typed_contracts():
    from circuit_workbench.nl_core import load_rulebook, relevant_rules
    book=load_rulebook()
    assert len(book["families"]) >= 20
    assert len(book["primitives"]) >= 12
    routed=relevant_rules("a clocked StrongARM comparator with a current mirror")
    assert any(f["id"]=="clocked_comparator" for f in routed["families"])
    assert any(p["id"]=="mos_mirror" for p in routed["primitives"])


def test_model_can_select_a_rule_without_inventing_terminal_wiring():
    from circuit_workbench.nl_core import ground_plan
    from circuit_workbench.nl_schema import SearchPlan
    p=ground_plan("Find amplifier candidates",SearchPlan.model_validate({"hypothesis_rules":["mos_diff_pair"]}))
    assert len(p.hypotheses)==2
    assert p.hypotheses[0].pattern.devices[0].type=="nmos"


def test_transistor_current_source_role_is_not_independent_source_count():
    from circuit_workbench.nl_core import parse_counts
    counts,questions=parse_counts("Find an amplifier with two current sources")
    assert not counts and questions
    counts,questions=parse_counts("with two independent current sources")
    assert counts[0].entity=="current_source" and not questions


def test_comparator_guidance_prefers_combined_input_and_regeneration_over_lone_pair():
    from circuit_workbench.nl_core import ground_plan
    from circuit_workbench.nl_schema import SearchPlan
    p=ground_plan("Find comparator candidates with more than 8 transistors",SearchPlan(hypothesis_rules=["mos_diff_pair"]))
    assert len(p.hypotheses[0].pattern.devices)==4
    assert len(p.hypotheses)<=5


def test_curated_differential_pair_does_not_mean_any_two_devices_on_ground():
    from circuit_workbench.nl_core import ground_plan
    from circuit_workbench.nl_search import pattern_witness
    from circuit_workbench.nl_schema import SearchPlan
    from circuit_workbench.uploads import parse_upload
    p=ground_plan('Find a differential pair',SearchPlan())
    r=parse_upload('M1 (a in1 VSS VSS) nmos4\nM2 (b in2 VSS VSS) nmos4','two grounded transistors')
    assert pattern_witness(r,p.hypotheses[0].pattern) is None


def test_aliases_are_whole_terms_not_tia_inside_differential():
    from circuit_workbench.nl_core import relevant_rules
    rules=relevant_rules('differential amplifier with current mirrors')
    assert not any(f['id']=='tia' for f in rules['families'])
    assert any(f['id']=='current_mirror' for f in rules['families'])


def test_or_in_unverified_preferences_is_not_a_count_disjunction():
    from circuit_workbench.nl_core import parse_counts
    counts,questions=parse_counts('OTA with exactly 5 transistors. Do not claim gain or stability.')
    assert len(counts)==1 and not questions
    assert parse_counts('either 5 transistors or 2 capacitors')[1]


def test_model_cannot_assume_missing_family_annotations_are_hard_requirements():
    from circuit_workbench.nl_core import ground_plan
    from circuit_workbench.nl_schema import SearchPlan
    p=ground_plan('Find an op amp with fewer than 20 transistors',SearchPlan(property_constraints=[{'field':'family','value':'opamp'}]))
    assert not p.property_constraints
    assert p.unverified_requirements
    p=ground_plan('Find circuits explicitly annotated as opamp',SearchPlan(property_constraints=[{'field':'family','value':'opamp'}]))
    assert p.property_constraints


def test_inferred_family_wiring_is_soft_not_a_model_invented_hard_filter():
    from circuit_workbench.nl_core import ground_plan
    from circuit_workbench.nl_schema import SearchPlan
    from tests.unit.test_nl_search import pair
    p=ground_plan('Find comparator candidates with more than 8 transistors',SearchPlan(required_pattern=pair()))
    assert p.required_pattern is None
    assert p.hypotheses


def test_explicit_reference_is_grounded_and_example_copied_reference_is_removed():
    from circuit_workbench.nl_core import ground_plan
    from circuit_workbench.nl_schema import SearchPlan
    p=ground_plan('similar to circuit 1004 with fewer than 20 transistors',SearchPlan(reference_id='analoggenie:1009'))
    assert p.reference_id=='analoggenie:1004'
    p=ground_plan('find a comparator with more than 8 transistors',SearchPlan(reference_id='analoggenie:1004'))
    assert not p.reference_id
