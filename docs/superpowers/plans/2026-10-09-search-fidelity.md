# Search Fidelity Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans inline, test-first.

**Goal:** Preserve complete explicit requirements and audit many realistic searches.
**Architecture:** Quote-grounded mandatory connected patterns and independent device presence; full eligibility precedes either ranking strategy; partial results separate.
**Tech Stack:** Existing Python/Pydantic/Neo4j/JS, existing Codex adapter.
**Spec:** docs/superpowers/specs/2026-10-09-search-fidelity-design.md

## Global Constraints

- Existing natural-language-query checkout, no IDs/family-specific fixes in product code.
- Same providers, no installs/downloads, no source/metadata mutation or remote push.
- Named function, operating stages and performance remain unverified, not false promises.
- Explicit connected requirements cannot be silently relaxed, even if no full results.
- User's prior no-approval execution preference applies; internal plan only.

## Review Focus

- Partial source quotes must not omit connected requirements (Task 1 test).
- Optional/negative nouns must not become compulsory presence (Task 1 test).
- Prototype similarity must not bypass exact eligibility (Task 2 test).
- No full match must remain empty in UI and history (Task 2/3 test).
- Source-netlist verification must reject stale or incomplete Neo4j matches (Task 2 test).

### Task 1: Ground and audit explicit structural intent

**Files:** nl_schema.py, nl_core.py, new nl_intent.py, tests/unit/test_nl_intent.py.
**Interfaces:** intent_audit(text)->wiring clauses/presence; grounded_required_patterns(text,plan) preserves only quote-complete connected alternatives; source_quote and required_pattern_source defaults backward compatible.
- [ ] Write failing tests for whole/composite wiring, presence, partial/fabricated quote, optional/negated and incomplete model plans; run targeted pytest, Expected FAIL.
- [ ] Implement general lexical intent audit and typed-pattern grounding, not circuit recipes. Missing mandatory wiring requests clarification.
- [ ] Run targeted/full pytest, Expected PASS; commit.

### Task 2: Full eligibility, ranking and separate partials

**Files:** nl_search.py, natural-language.mjs, tests/unit/test_nl_search.py, tests/ui/natural-language.test.mjs.
**Interfaces:** NaturalSearch.run items always full structural matches; partial_items separate max5, each missing_requirements; specificity precedes coverage; validate_prototypes(batch,plan) checks complete eligibility.
- [ ] Write failing regressions for 615/complete graph, both strategies, absent results, missing anchors and partial UI; run, Expected FAIL.
- [ ] Preserve requirements in provider instructions. Apply local full witnesses to results/anchors, maintain empty full results and bounded separate partial diagnostics.
- [ ] Run Python/Node full suites, Expected PASS; commit.

### Task 3: Real-provider audit and researcher workflow

**Files:** scripts/audit-natural-search.py, tests/fixtures/search-audit.json, docs/search-fidelity-evaluation.md, README.md.
**Interfaces:** CLI case matrix -> captures request/plan/results/pattern checks under ignored output/search-fidelity; full, partial, absent and unverified cases, both modes; no automatic success based on scores.
- [ ] Construct hand-derived literal expectations from existing canonical records and absent count combinations; validate offline first.
- [ ] Run at least 12 varied real Codex searches across both strategies, inspect every returned mandatory witness and representative original images/netlists; record wrong/questionable results and fix verified causes test-first.
- [ ] Browser-check original prompt, full/partial empty states and circuit inspection; full fresh suites, Expected PASS; commit and one fresh final code review.
