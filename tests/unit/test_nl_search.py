"""Contracts must reject unsafe interpretations, not merely JSON syntax errors."""
import pytest


def test_plan_compiler_keeps_count_operators_and_parameterizes_text():
    from circuit_workbench.nl_schema import SearchPlan
    from circuit_workbench.nl_compiler import compile_query
    plan = SearchPlan.model_validate({"count_constraints": [
        {"entity": "transistor", "operator": "gt", "value": 12},
        {"entity": "resistor", "operator": "le", "value": 3}],
        "property_constraints": [{"field": "dataset", "value": "x' DELETE c"}]})
    query, params = compile_query(plan)
    assert "> $count0" in query and "<= $count1" in query
    assert params["count0"] == 12 and params["count1"] == 3
    assert "DELETE" not in query
    assert params["property0"] == "x' DELETE c"
    assert "LIMIT 10001" in query


def pair():
    return {"devices": [{"alias": "a", "type": "nmos"}, {"alias": "b", "type": "nmos"}],
            "nets": ["tail", "in1", "in2"],
            "edges": [{"device": "a", "terminal": "source", "net": "tail"},
                      {"device": "b", "terminal": "source", "net": "tail"},
                      {"device": "a", "terminal": "gate", "net": "in1"},
                      {"device": "b", "terminal": "gate", "net": "in2"}],
            "distinct_nets": [["in1", "in2"]]}


def test_pattern_compiler_owns_entities_and_distinguishes_devices_and_nets():
    from circuit_workbench.nl_schema import SearchPlan
    from circuit_workbench.nl_compiler import compile_query
    p = SearchPlan.model_validate({"required_pattern": pair()})
    query, params = compile_query(p)
    assert "HAS_DEVICE" in query and "HAS_NET" in query
    assert "hardd0 <> hardd1" in query and "hardn1 <> hardn2" in query
    assert "CONNECTED_TO" in query
    assert params["hardtype0"] == "nmos" and "source" in params.values()


@pytest.mark.parametrize("change", [
    lambda x: x["devices"][0].update(alias="a) DELETE c"),
    lambda x: x["devices"][0].update(type="magic"),
    lambda x: x["edges"][0].update(terminal="collector"),
    lambda x: x["edges"][0].update(net="missing"),
    lambda x: x.update(nets=[f"n{i}" for i in range(25)]),
    lambda x: x["edges"].append(dict(x["edges"][0], net="in1")),
])
def test_rejects_invalid_graph_patterns(change):
    from circuit_workbench.nl_schema import SearchPlan
    p = pair()
    change(p)
    with pytest.raises(ValueError):
        SearchPlan.model_validate({"required_pattern": p})


def test_no_raw_cypher_or_invented_performance_property():
    from circuit_workbench.nl_schema import SearchPlan
    for bad in ({"cypher": "DELETE c"}, {"property_constraints": [{"field": "gain", "value": 70}]},
                {"count_constraints": [{"entity": "transistor", "operator": "gt", "value": True}]}):
        with pytest.raises(ValueError):
            SearchPlan.model_validate(bad)


def test_prototype_batch_requires_four_or_five_real_netlists():
    from circuit_workbench.nl_schema import PrototypeBatch
    item = {"name": "mirror", "description": "Hypothetical mirror", "netlist": "M1 (a a 0 0) nmos4", "ports": "a 0", "rationale": "candidate"}
    assert len(PrototypeBatch.model_validate({"prototypes": [item]*4}).prototypes) == 4
    with pytest.raises(ValueError):
        PrototypeBatch.model_validate({"prototypes": [item]*3})


def test_prototypes_reject_renamed_duplicate_graphs_and_do_not_ingest(tmp_path):
    from circuit_workbench.nl_schema import PrototypeBatch
    from circuit_workbench.nl_search import validate_prototypes
    def item(name, netlist):
        return {"name": name, "description": "Temporary mirror", "netlist": netlist, "ports": "a b 0", "rationale": "mirror"}
    batch = PrototypeBatch.model_validate({"prototypes": [
        item("one", "M1 (a a 0 0) nmos4\nM2 (b a 0 0) nmos4"),
        item("duplicate", "Foo (a a 0 0) nmos4\nBar (b a 0 0) nmos4"),
        item("bad", "DELETE c"),
        item("other", "M1 (a a 0 0) nmos4\nM2 (b a 0 0) nmos4\nR1 (b 0) resistor") ]})
    accepted, diagnostics = validate_prototypes(batch)
    assert len(accepted) == 2
    assert any("duplicate" in d["error"].lower() for d in diagnostics)
    assert len(diagnostics) == 2


def test_counts_checked_locally_again_before_ranking(tmp_path):
    from circuit_workbench.nl_schema import SearchPlan
    from circuit_workbench.nl_search import meets_plan
    from circuit_workbench.uploads import parse_upload
    rec = parse_upload("M1 (a b 0 0) nmos4\nR1 (a 0) resistor", "Amplifier")
    plan = SearchPlan.model_validate({"count_constraints": [{"entity": "transistor", "operator": "gt", "value": 1}]})
    assert not meets_plan(rec, {}, plan)
    plan.count_constraints[0].operator = "ge"
    assert meets_plan(rec, {}, plan)


def test_search_filters_stale_graph_counts_and_returns_weaker_tier_without_vectors(tmp_path):
    import threading
    from tests.unit.test_workbench import catalog
    from circuit_workbench.retrieval import Retrieval
    from circuit_workbench.nl_schema import SearchPlan
    from circuit_workbench.nl_search import NaturalSearch
    db = catalog(tmp_path)
    plan = SearchPlan.model_validate({"count_constraints": [{"entity": "transistor", "operator": "lt", "value": 17}],
                                    "hypotheses": [{"interpretation": "differential pair candidate", "pattern": pair()}]})
    class Neo:
        def candidate_query(self, query, params):
            return {"rows": [] if "terminal0" in params else [{"circuit_id": "analoggenie:"+i} for i in ("1004", "1009", "2030")], "truncated": False}
    search = NaturalSearch(db, Neo(), Retrieval(db), generate=lambda *a: plan)
    result = search.run({"text": "amplifier with fewer than 17 transistors"}, threading.Event(), lambda s: None)
    assert result["items"]
    assert all(sum(c["statistics"]["device_type_counts"].get(k, 0) for k in ("nmos", "pmos", "npn", "pnp")) < 17 for c in result["items"])
    assert all(c["tier"] == "hard-filter/text candidate" for c in result["items"])
    assert any("No structural hypothesis" in w for w in result["warnings"])


def test_pattern_witness_rejects_diode_pair_misread_as_separate_inputs():
    from circuit_workbench.nl_schema import GraphPattern
    from circuit_workbench.nl_search import pattern_witness
    from circuit_workbench.uploads import parse_upload
    r = parse_upload("M1 (a a 0 0) nmos4\nM2 (b a 0 0) nmos4", "mirror")
    assert pattern_witness(r, GraphPattern.model_validate(pair())) is None


def test_scalar_candidate_path_is_not_capped_at_console_200_rows():
    from circuit_workbench.neo4j import Neo4jService
    from types import SimpleNamespace
    class Result:
        def consume(self):
            return SimpleNamespace(query_type="r")
        def __iter__(self):
            return iter({"circuit_id": f"analoggenie:{i}"} for i in range(350))
    class Tx:
        def __enter__(self): return self
        def __exit__(self, *a): pass
        def run(self, *a): return Result()
        def rollback(self): pass
    class Session:
        def __enter__(self): return self
        def __exit__(self, *a): pass
        def begin_transaction(self, **kw): return Tx()
    class Driver:
        def session(self, **kw): return Session()
    service = object.__new__(Neo4jService)
    service.driver, service.settings = Driver(), SimpleNamespace(neo4j_database="neo4j")
    result = service.candidate_query("MATCH (c:Circuit) RETURN c.id AS circuit_id")
    assert len(result["rows"]) == 350 and not result["truncated"]


def test_numeric_citations_and_device_count_filler_are_not_functional_text():
    from circuit_workbench.nl_search import meaningful_context
    assert not meaningful_context({"reference_text": "3-7, 389", "metadata": '{}'})
    assert meaningful_context({"reference_text": "A high swing cascode current mirror", "metadata": '{}'})
    assert meaningful_context({"reference_text": "", "metadata": '{"family":"comparator"}'})


def test_pattern_coverage_does_not_reward_duplicate_hypotheses():
    from circuit_workbench.nl_search import coverage_score
    witness={"devices":{"a":"M1","b":"M2"}}
    assert coverage_score([{"witness":witness}]*4,None,10) == .2
    assert coverage_score([{"witness":witness}],None,2) == 1.0


def test_missing_citation_does_not_let_incidental_core_outrank_focused_topology():
    from circuit_workbench.nl_search import ranked_candidates
    focused={"row":{"id":"focused"},"matches":[{}],"required_witness":None,"pattern_coverage":1.,"structural_score":.95,"score":.016}
    incidental={"row":{"id":"incidental"},"matches":[{}],"required_witness":None,"pattern_coverage":.2,"structural_score":.5,"score":.032}
    assert ranked_candidates([incidental,focused],"patterns")[0]["row"]["id"] == "focused"
    assert ranked_candidates([incidental,focused],"prototypes")[0]["row"]["id"] == "focused"


def test_required_block_alternatives_are_or_within_same_parent_circuit():
    from circuit_workbench.nl_schema import SearchPlan
    from circuit_workbench.nl_compiler import compile_query
    p=SearchPlan.model_validate({"required_blocks":[{"name":"input pair","alternatives":[pair(),pair()]}]})
    query,params=compile_query(p)
    assert " OR " in query
    assert "(c)-[:HAS_DEVICE]" in query
    assert params["block0alt0type0"] == "nmos"


def test_compiler_does_not_independently_enumerate_all_net_variables():
    from circuit_workbench.nl_compiler import compile_query
    from circuit_workbench.nl_schema import SearchPlan, GraphPattern
    query,_=compile_query(SearchPlan(),GraphPattern.model_validate(pair()))
    # Net ownership is checked after terminal traversal; enumerating all circuit
    # nets before binding creates an explosive Cartesian candidate space.
    assert "EXISTS { (c)-[:HAS_NET]->(n0) }" in query
