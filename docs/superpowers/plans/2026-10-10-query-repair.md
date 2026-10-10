# Query repair implementation plan

> For agentic workers: implement inline with executing-plans and test-driven-development.

Goal: make the existing natural-language workbench return coherent analog structural
candidates for the researcher prompts, without answer IDs or prompt-string routing.
Architecture: retain the SearchPlan/compiler contract. Compile supported common
motifs from bounded composable rules; use the provider for uncovered custom intent.
Apply identical role/gain-path guards in Neo4j and canonical source verification.
Spec: the user's existing approved model-agnostic search requirements and the
short in-chat repair design. No new approval gate, installations or metadata work.

## Global constraints

- Stay on natural-language-query; preserve corpus and user annotations.
- Never turn unknown gain/stability into verified performance or weaken counts.
- Rules may describe classes/terminal structures, never expected circuit IDs.
- Unsupported intent falls back to the model, rather than silently dropping it.
- No authentication changes, provider substitution, merger or remote push.

## Review focus

- Bias/clock/logic names must not count as analog signal interfaces.
- Incidental mirrors/latches must not replace a connected primary signal path.
- Unspecified polarity must include mixed-polarity alternatives.
- Additional/unrecognized terminal clauses must not be ignored by fast rules.
- Navigation, errors and reload must not resurrect stale results or jobs.

### Task 1: role and gain-path guards

Files: nl_schema.py, nl_intent.py, nl_compiler.py, nl_search.py; unit/integration tests.
Interface: GraphPattern conditions plus shared gain-stage guard descriptors;
compiler and canonical witness must enforce the same semantics.
- [x] Write synthetic failures: VB/VCLK/LOGIC as stage inputs; bias output;
  mirror-reference input counted as gain stage; regenerative output as amplifier.
- [x] Run and observe assertion failures, then implement conditions/guards.
- [x] Verify positive mixed MOS/BJT stages remain supported; run full suite.

### Task 2: deterministic common-motif planning

Files: new nl_templates.py; nl_search.py; unit tests.
Interface: deterministic_plan(text: str) -> SearchPlan | None. Returned plans
cover all supported clauses, or None triggers the existing isolated provider.
- [x] Write real-service tests for renamed/count-varied common requests, asserting
  correct physical results without provider calls; unknown wiring uses provider.
- [x] Implement pair/degeneration, mirror/cascode, follower, sequential gain,
  connected regenerative-load/output and clock tail/reset composition.
- [x] Preserve counts via existing ground_plan, optional preferences and unknown
  performance; expose interpreter provenance. Allow bounded complete variants.
- [x] Run unit suite and live compiled queries; commit verified changes.

### Task 3: UI and end-to-end acceptance

Files: natural-language.mjs, app.js, UI tests, evaluation/report documentation.
- [x] Test rule-engine provenance, unknown-spec display, empty interpretation,
  stale job cancellation/remount and reference-only search.
- [x] Implement clear progress/provenance and safe error/zero states; no redesign.
- [x] Exercise all ten requests in the visible browser; independently review source
  records/images and strict/partial results. Include paraphrases and absent cases.
- [x] Run Python/Node/live Neo4j suites, one read-only final review, update report,
  restart normal server, commit locally and leave the browser ready.

## Execution record

Observed failing tests for role/gain guards and all three final-review grammar
counterexamples before their fixes. The review's four important findings were
fixed; none were dismissed. Added owned-job refresh cleanup and serialization of
reference-only searches. Canonical source pre-filtering and bounded Cypher
alternative batches resolve reproduced join-planning timeouts without loosening
constraints. All ten final browser requests completed; every displayed netlist
passed source count/wiring checks. Additional varied, absent and unsupported
requests were exercised. See search-fidelity-evaluation.md for actual timings,
representative image reviews and coverage limitations. Normal app restored;
feature branch retained. No provider calls, new installations or corpus mutations.
