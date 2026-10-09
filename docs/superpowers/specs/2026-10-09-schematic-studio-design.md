# Schematic studio design

User-authorized follow-on to natural-language search. Implement inline without additional approval pauses. Keep the existing feature branch and all source records intact.

## Intent and entry points

Add a third main navigation tab, Schematic studio. An action on every library row and circuit inspector opens it with that circuit selected. Existing circuits use their stored canonical netlist; the user need not upload one. A second path starts from a plain-language request, uses the selected provider to propose a new netlist internally, parses it, and draws the resulting topology. A third optional paste-netlist path supports standalone use.

Proposed circuits are drafts, not electrically certified designs. Source images stay original images; generated SVGs are separate artifacts. No generated circuit is automatically ingested. An explicit Add to library action reuses the current validated upload flow and preserves generated/draft provenance.

## Adaptation, not a fork

Use cirfig_gen as design/source reference (pinned upstream commit 05cf185ed177ddab7a95ce37ad4366c668b3e7c3). Recreate the renderer inside this project rather than cloning/forking an executable agent workspace. Preserve MIT attribution for adapted concepts/assets. Improvements: canonical typed pin contracts, explicit bulk/substrate contacts, automatic netlist grounding, owned routing, bounded layouts, interactive edits, diagnostics, provider isolation, persistence and SVG/PNG/JSON/netlist exports. Do not execute upstream agent instructions.

## Contracts and rendering

The LLM may propose a supported flat analog netlist and/or a placement JSON. It cannot submit executable SVG or arbitrary wire endpoints. Layout placements refer to canonical device ordinals and grid locations; every device must occur exactly once, positions must be finite, bounded and non-overlapping, and flips preserve terminal roles. Existing circuits' device types, terminals and nets cannot be modified by the layout model.

The renderer owns symbol geometry and typed pins. Derive every terminal connection from the canonical record. Never infer pins from all SVG path vertices (upstream limitation). Represent every terminal including body/substrate. Nets may be routed orthogonally where clear, or represented by explicit identical net labels when physical routing would be unreadable; disclose labelled-connectivity mode. Canonical net IDs accompany net labels and pin/wire manifest entries; geometric and semantic checks verify exact pin/net coverage and prevent cross-net joining.

Render unsupported opaque macros as labelled multi-pin boxes, not fabricated transistor internals. Allow all existing parseable library circuits with a scalable labelled view; bound prompt-generated circuits to 64 devices and submitted netlists to the existing parser limits. Validate generated counts deterministically; malformed/duplicate/disconnected or shorted proposed circuits receive failures/warnings as appropriate. No generic diagram check proves gain, clock timing, stability or startup.

## Providers and persistence

Reuse the tool-free Ollama/Codex/Claude provider adapter and cancellable job lifecycle. Test with existing Codex authentication; no automatic model/software installation or cloud fallback. Provide deterministic automatic placement so drawing library circuits works without an LLM. Model-assisted polish is optional and strictly layout-only. Prompt generation requires an available selected LLM.

Persist successful drawings in the local state directory with original/generated provenance, immutable source hash, netlist, record, placement JSON, SVG, diagnostics and provider information (no credentials/debug logs). Reopen generated artifacts from studio history. Export single-file SVG, PNG via browser canvas, JSON manifest/layout and netlist. An editable JSON layout and incremental zoom/Fit/expand controls permit manual adjustment.

## UI and verification

Use existing charcoal/olive/copper styling. Compact form plus prominent bounded preview, expandable assumptions/netlist/layout/checks, clear progress and cancellation. Preserve drafts; stale asynchronous jobs must not mutate another page. Show source/generated status and no-simulation warning alongside checks.

TDD covers pin roles/coverage, XML escaping, layout validation, immutable sources, count mismatch, job cancellation and API isolation. Test prompt-only generation and existing-library drawings with real Codex, manually inspect rendered images/netlists, and exercise library action → studio → export/import/navigation. Verify representative MOS, BJT, R/C/L and macro circuits; final fresh code review covers the combined feature branch.
