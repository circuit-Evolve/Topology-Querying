"""Captured real-model composite must plan/execute within the existing timeout."""
import json,os
from pathlib import Path
import pytest

@pytest.mark.skipif(os.getenv('RUN_NL_LIVE_NEO4J')!='1',reason='requires running local corpus Neo4j')
def test_multi_alternative_connected_patterns_fit_the_live_query_budget():
    from circuit_workbench.nl_schema import SearchPlan
    from circuit_workbench.nl_core import ground_plan
    from circuit_workbench.nl_compiler import compile_query
    from circuit_workbench.settings import Settings
    from circuit_workbench.catalog import Catalog
    from circuit_workbench.neo4j import Neo4jService
    root=Path(__file__).resolve().parents[2]
    raw=SearchPlan.model_validate(json.loads((root/'tests/fixtures/complex-search-plan.json').read_text()))
    # Captured graph predates stage-assignment fields; test compiler semantics
    # directly, independently of the newer intent-grounding contract.
    plan=raw
    settings=Settings.local();catalog=Catalog(settings.state,settings.corpus,settings.upstream);neo=Neo4jService(settings,catalog)
    try:response=neo.candidate_query(*compile_query(plan))
    finally:neo.driver.close()
    assert response['rows']
    assert 'analoggenie:615' not in {r['circuit_id'] for r in response['rows']}
    assert 'analoggenie:181' not in {r['circuit_id'] for r in response['rows']}
