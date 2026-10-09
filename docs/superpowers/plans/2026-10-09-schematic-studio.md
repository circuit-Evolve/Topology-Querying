# Schematic Studio Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans inline, test-first.

**Goal:** Add polished library/netlist/prompt schematic generation with modular local and CLI adapters.

**Architecture:** Typed canonical records ground owned SVG symbols and connections; model output is netlist/placement JSON only. Deterministic placement always supports library rendering. A local artifact store persists drafts; explicit upload is opt-in.

**Tech Stack:** Existing FastAPI/Pydantic/SQLite/NetworkX, SVG XML and browser canvas exports; reuse nl_providers/SearchJobs.

**Spec:** docs/superpowers/specs/2026-10-09-schematic-studio-design.md

## Global Constraints

- Existing feature checkout; preserve original catalog/source assets and annotations.
- Maximum 64 devices for prompt proposals; existing library records remain inspectable.
- No model-authored SVG, executable layout code or wiring changes in layout polish.
- All terminals including bulk/substrate represented; exact typed pin/net manifest checks.
- No simulation claims, automatic ingestion, model download or cloud fallback.
- User explicitly approves continuous execution without further gates.

## Review Focus

- Duplicate source instance names must map via ordinal identity, not ambiguous labels (Task 1 test).
- Four-terminal devices must not lose bulk/substrate contacts (Task 1 test).
- Prompt proposals need no supplied netlist but still fail malformed/count-mismatched output (Task 2 test).
- Labelled-net connections must not claim visible continuous wiring or electrical proof (Task 1/3 check).
- Stale async UI operations and explicit import must preserve source provenance (Task 3 browser check).

### Task 1: Canonical, typed-pin SVG renderer

**Files:** Create schematic.py; tests/unit/test_schematic.py; docs attribution.
**Interfaces:** LayoutPlan/Placement validated JSON; auto_layout(record) -> LayoutPlan; render_schematic(record,layout,name,style) -> SVG+pin/net manifest+diagnostics. Every device ordinal once, no collisions; owned geometry, safely escaped labels. All canonical terminal roles handled; net labels explicitly connect repeated names, routed connected view for small drawings.
- [ ] Write tests for MOS/BJT/macro pin coverage, bad layouts, escaping and unchanged source; run test file; Expected absent-module FAIL.
- [ ] Implement deterministic layout and owned SVG geometry/routing with bounded checks and explicit labelled-mode fallback.
- [ ] Run targeted/full pytest; Expected PASS. Render representative fixtures and visually inspect SVG previews.
- [ ] Commit `feat: render canonical netlists as checked schematics`.

### Task 2: Studio proposals, model polish, artifact store and API

**Files:** Create studio.py; modify app.py; tests/unit/test_studio.py.
**Interfaces:** StudioRequest (library/netlist/prompt), CircuitProposal (name/description/netlist/ports/assumptions/placement), Studio.run(request,cancel,progress), StudioStore get/list/save; POST/GET/DELETE studio/jobs and GET artifacts/svg.
- [ ] Write tests for source immutability, no auto ingestion, generated count mismatch, provider errors, layout-only polish and reopening artifacts; run; Expected FAIL.
- [ ] Implement reuse of provider schema generation, canonical parsing and deterministic count validation. Bind placement model to known ordinals; warn/reject invalid proposals. Persist owned artifacts under existing ignored state; show draft provenance.
- [ ] Run targeted/full tests; Expected PASS. Live Codex prompt-only mirror/OTA and layout-polish checks, with schematic visual inspection.
- [ ] Commit `feat: add model-adapted schematic studio workflows`.

### Task 3: Third tab, library entry points and interactive preview

**Files:** Create static/studio.mjs; modify app.js/app.css/index.html; README/docs/studio.md; tests/ui/studio.test.mjs.
**Interfaces:** mountStudio(root,context) consumes artifacts/jobs/providers endpoints; source picker/library link, prompt/netlist mode, provider/model, optional polish, zoom/Fit/expand, layout editor and exports. Add-to-library explicitly calls existing upload endpoint with draft provenance.
- [ ] Write UI state/export/invalid-layout tests; run Node; Expected FAIL.
- [ ] Implement compact form/prominent preview and job progress/cancel, persisted drafts/artifact history, SVG/PNG/JSON/netlist export and validated manual layout edits.
- [ ] Run full Python/Node and browser checks: every library row action, prompt-only generation, schematic/netlist inspection, cancellation/errors, history/reopen, exports and no janky viewport behavior.
- [ ] Document capabilities/limitations and actual generation review; commit `feat: integrate polished schematic studio into Circuit Atlas`.
- [ ] Final fresh combined-branch review; important findings RED→GREEN with full suite before completion; keep feature branch.
