#!/usr/bin/env python3
"""Run real-provider checks; save evidence for subsequent human schematic review.

This does not judge circuit function. Use the returned images/netlists to do that.
"""
import argparse
import json
from pathlib import Path
import time
import urllib.request

CASES = {
    "mirror": "Find NMOS current mirror circuits with a diode-connected reference transistor, shared gate and source, and a distinct output drain. Fewer than 12 transistors.",
    "amplifier": "Find differential amplifier candidates with at least one capacitor and fewer than 20 transistors.",
    "comparator": "Find comparator candidates with more than 8 transistors and no inductors.",
}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case", choices=CASES, default="mirror")
    parser.add_argument("--strategy", choices=("patterns", "prototypes"), default="patterns")
    parser.add_argument("--provider", choices=("codex", "ollama", "claude"), default="codex")
    parser.add_argument("--model", default="")
    parser.add_argument("--base", default="http://127.0.0.1:8766")
    parser.add_argument("--replay-plan", type=Path, help="Replay a previously captured validated provider result against the current deterministic core; no new model call.")
    args = parser.parse_args()
    def api(path, payload=None):
        request = urllib.request.Request(args.base+path, data=json.dumps(payload).encode() if payload else None, headers={"Content-Type": "application/json"})
        return json.load(urllib.request.urlopen(request, timeout=15))
    request = {"text": CASES[args.case], "strategy": args.strategy, "provider": args.provider, "model": args.model, "limit": 5}
    start = time.monotonic()
    if args.replay_plan:
        import threading
        from circuit_workbench.settings import Settings
        from circuit_workbench.catalog import Catalog
        from circuit_workbench.retrieval import Retrieval
        from circuit_workbench.neo4j import Neo4jService
        from circuit_workbench.nl_search import NaturalSearch
        from circuit_workbench.nl_schema import SearchPlan, PrototypeBatch
        captured = json.loads(args.replay_plan.read_text())["result"]
        def generate(contract,*unused):
            if contract is SearchPlan:
                return contract.model_validate(captured["plan"])
            keys={"name","description","netlist","ports","rationale"}
            return PrototypeBatch.model_validate({"prototypes":[{k:v for k,v in p.items() if k in keys} for p in captured["prototypes"]]})
        settings=Settings.local();catalog=Catalog(settings.state,settings.corpus,settings.upstream)
        retrieval=Retrieval(catalog);retrieval.build();neo=Neo4jService(settings,catalog)
        try:
            result=NaturalSearch(catalog,neo,retrieval,generate).run(request,threading.Event(),lambda s:None)
        finally:
            neo.driver.close()
    else:
        job = api("/api/natural/jobs", request)
        while job["state"] in {"queued", "running"}:
            time.sleep(.7)
            job = api("/api/natural/jobs/"+job["id"])
        if job["state"] != "complete":
            raise SystemExit(job.get("error") or job["state"])
        result = job["result"]
    inspected = []
    for candidate in result["items"]:
        detail = api("/api/circuits/"+candidate["id"])
        inspected.append({"id": candidate["id"], "netlist": detail["netlist"], "assets": detail["assets"],
                          "source": detail["source"], "reference_text": detail["reference_text"]})
    output = Path(__file__).resolve().parents[1] / "output/natural-evaluation"
    output.mkdir(parents=True, exist_ok=True)
    path = output / f"{args.case}-{args.strategy}{'-replay' if args.replay_plan else ''}.json"
    path.write_text(json.dumps({"replay_source":str(args.replay_plan) if args.replay_plan else None,"elapsed_seconds": round(time.monotonic()-start, 1), "result": result, "inspection_sources": inspected}, indent=2))
    print(path)
    print("eligible", result["total"], "matched", result["structural_matches"], "prototypes", len(result["prototypes"]))
    print("warnings", result["warnings"])
    for candidate, detail in zip(result["items"], inspected):
        print(candidate["id"], candidate["tier"], "coverage", candidate.get("pattern_coverage"), "full", candidate["structural_score"], "assets", detail["assets"])


if __name__ == "__main__":
    main()
