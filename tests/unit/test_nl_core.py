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
    assert result.required_blocks[0].name == "MOS current mirror"
    assert len(result.required_blocks[0].alternatives) == 2


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
