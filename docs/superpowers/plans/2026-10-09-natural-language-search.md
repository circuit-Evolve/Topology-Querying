# Natural-language circuit search Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement task-by-task inline. Steps use checkbox syntax.

**Goal:** Search real analog circuits from general language using two selectable strategies, then inspect actual returned circuits.

**Architecture:** An LLM produces validated JSON, never executable Cypher. Application-owned compilation selects eligible circuits before structural/text ranking. Experimental prototypes are parsed temporary circuits, not dataset entries. Cancellable jobs isolate provider work from the UI.

**Tech Stack:** Existing Python/FastAPI/Pydantic/Neo4j/NumPy and vanilla JS; Ollama HTTP, Codex and Claude CLIs.

**Spec:** docs/superpowers/specs/2026-10-09-natural-language-search-design.md

## Global Constraints

- Work on existing natural-language-query branch; preserve corpus and user edits.
- Patterns: maximum 16 devices, 24 nets, 64 terminal edges; 0–5 hypotheses.
- Prototypes: request 4–5, maximum 64 devices each; no ingestion, no simulation claims.
- Hard filters precede ranking; internal queries retrieve up to 10,000 IDs with explicit truncation.
- Provider JSON validated independently; one repair; no automatic model download/cloud fallback.
- Renderer is follow-on work, not part of this milestone.
- User-added scope: shared machine-readable electrical rulebook, deterministic count grounding and parent/required-block semantics; schema and tests included in Task 2. Next approved milestone is Schematic studio with modular adapters.

## Review Focus

- Malicious aliases/types must never inject Cypher (Task 1 rejection test).
- Partial graph hypotheses must not silently become compulsory (Task 2 fallback test).
- CLI cancellation must stop owned processes without killing unrelated work (Task 2 adapter test).
- Prototype failure/duplication must not quietly turn into successful full retrieval (Task 2 validation test).
- Navigating away during a job must preserve drafts and not render into another page (Task 3 browser check).

### Task 1: Validated search plans and structural compiler

**Files:** Create nl_schema.py, nl_compiler.py under src/circuit_workbench; tests/unit/test_nl_search.py.

**Interfaces:** Produces SearchPlan.model_validate, GraphPattern, PrototypeBatch and compile_query(plan, pattern=None) -> (query, parameters). Compile generic terminal patterns with same-circuit ownership, distinct device aliases, net inequalities and exact named port bindings. Supports device/category/port counts and whitelisted stored metadata equality filters.

- [ ] Write tests rejecting injection/unknown terminals/oversize, preserving strict counts and parameterized values, and prototype count bounds.
- [ ] Run `PYTHONPATH=src .venv/bin/python -m pytest tests/unit/test_nl_search.py -q`; Expected FAIL because modules absent.
- [ ] Implement strict Pydantic contracts and owned parameterized compiler; derive terminal contracts from canonical device registry.
- [ ] Run same command; Expected PASS, then full pytest suite.
- [ ] Commit `feat: validate and compile natural-language search plans`.

### Task 2: Providers, ranking and cancellable API

**Files:** Create nl_providers.py, nl_search.py, nl_jobs.py; modify neo4j.py/app.py; extend test_nl_search.py and add test_nl_providers.py.

**Interfaces:** Consumes SearchPlan/compile_query. Produces provider_status(), generate(schema,prompt,provider,model,cancel), NaturalSearch.run(request,cancel,progress), SearchJobs.start/get/cancel; API GET providers, POST jobs, GET/DELETE jobs/{id}. Neo4jService.candidate_query retrieves scalar rows without graph serializer caps. Jobs expire and expose errors without credentials.

- [ ] Write failure tests: broad candidates, hard-filter-before-ranking, no-pattern fallback, duplicate/invalid prototypes, missing vectors, one repair, environment scrubbing, timeouts/cancel and job limit.
- [ ] Run unit tests; Expected FAIL for missing functionality.
- [ ] Implement providers with schema output, tools/hooks disabled where supported, isolated cwd, scrubbed DB env, bounded output/time and cancellation. No auto model installation.
- [ ] Implement query-pattern evidence plus optional text/reference fusion and prototype best-vector/full-profile reranking; retain unknown performance requirements and candidate labels.
- [ ] Implement cancellable bounded jobs and same-origin API. History stores request/validated plan, no debug secrets.
- [ ] Run unit + full suite; Expected PASS. Live check scalar Neo4j compiled queries and Codex JSON generation, distinguish unavailable Ollama/Claude.
- [ ] Commit `feat: add two natural-language retrieval strategies`.

### Task 3: UI, end-to-end evaluation and documentation

**Files:** Create static/natural-language.mjs; modify app.js/app.css; README; add tests/ui/natural-language.test.mjs and docs/search-evaluation.md.

**Interfaces:** Consumes jobs/providers API. Mount form with prompt, strategy, provider/model, optional reference and limit; preserve reference-only direct search. Results retain existing circuit links; show counts, hypotheses, score channels, unverified requirements and collapsible JSON/Cypher/prototypes.

- [ ] Write UI state/cancellation tests; run Node tests; Expected FAIL before module.
- [ ] Implement compact dark UI with progress/cancel, error recovery, draft/history persistence and explicit cloud/experimental notices.
- [ ] Run Python/Node suites; Expected PASS. Use browser prompt→results→schematic/netlist inspection and navigation/error recovery.
- [ ] Run varied real queries in both strategies, inspect top schematic images/netlists manually, record supported/questionable/wrong findings; fix substantive issues test-first.
- [ ] Document setup/capabilities/limitations and actual evaluation; commit `feat: expose and evaluate natural-language circuit search`.
- [ ] One fresh final code review, address important findings RED→GREEN, full suite; leave feature branch intact.
