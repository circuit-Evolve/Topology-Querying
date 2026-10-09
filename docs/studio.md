# Schematic studio

Open the third navigation tab, **Schematic studio**. Three entry paths share one
canonical parser and owned renderer:

- **Library:** click **Draw** on any library row or **Generate schematic** in its
  inspector. The stored netlist is used; automatic placement needs no model.
- **From words:** describe a proposed circuit. You do **not** need a netlist.
  The selected converter proposes a flat netlist internally; the app parses it,
  independently checks common requested device counts, places symbols and renders.
- **Netlist:** paste a supported flat netlist, a basic description and optional
  external ports. This is useful outside the existing library.

Codex, Ollama and Claude use the same structured-output adapter as search. Optional
model-assisted placement polish only changes positions/orientation, never an
existing circuit's wiring. No model downloads or automatic cloud fallback occur.
See [converter setup](../README.md#natural-language-converters).

## Drawing and editing

The renderer owns symbols, typed terminal positions and orthogonal routing. Every
canonical terminal, including MOS body and BJT substrate, appears in the manifest.
It checks pin/net coverage and rejects cross-net geometric contacts. Rails and
obstructed connections use explicit repeated net labels; identical labels connect
electrically. Large circuits use more labelled connectivity to avoid spaghetti.
Opaque macros are pin-labelled boxes, not invented transistor internals.

Use incremental zoom, Fit, drag-to-pan and Expand. The side panel contains source
provenance, assumptions, diagnostics, netlist and checks. Placement JSON uses
device ordinals, integer grid cells and horizontal flips; every ordinal must occur
once and cells cannot overlap. Valid edits create a new artifact, not a source edit.

Export SVG, PNG, complete artifact JSON or netlist. PNG is bounded to 4096 pixels
on its longest side. SVG uses standard Helvetica/Arial fallback fonts, not embedded
font outlines. Successful drawings persist in local SQLite under
`output/workbench/studio/`; Saved drawings shows the latest 50. Artifacts are not
automatically deleted and are excluded from Git.

**Add draft to library** is explicit, not automatic. It imports the netlist,
description, rendered PNG and draft/provenance notes through the existing upload
flow. Original source images and records stay untouched.

## What the checks mean

A drawing faithfully represents the **parsed** netlist; this is not simulation or
design certification. Count checks do not establish amplifier/comparator function,
bias, gain, stability, delay, noise, dimensions, startup or PDK compatibility.
Prompt proposals are limited to 64 devices. Unsupported syntax or count mismatches
fail without saving a successful artifact. Invalid model placement falls back to
disclosed deterministic placement without changing the circuit or provider.

The implementation adapts ideas from cirfig_gen without forking or executing its
agent workspace. It replaces path-vertex pin inference with canonical typed pins,
adds immutable-source grounding, routing checks, persistence and interactive
exports. See [upstream attribution](cirfig-attribution.md).

## Actual local verification

Live Codex checks on 9 October 2026, with schematic and netlist inspection:

| Request | Observed result |
| --- | --- |
| Two-transistor NMOS mirror, from words | 13.2 seconds; two MOS, 8/8 contacts, diode-connected reference, shared gate/source and separate output drain |
| Five-transistor PMOS-input mirror OTA, from words | 22 seconds; five MOS, 20/20 contacts, distinct input gates, tail-bias port and NMOS mirror load; requires appropriate external bias |
| Library 1004, Codex placement polish | 23 seconds; 17 devices, 60/60 contacts; original netlist/source hash unchanged |

Browser checks exercised zoom/Fit/expand, rejected overlapping JSON placement,
valid correction, artifact reopening, PNG/SVG/JSON/netlist export and explicit
draft import into the normal graph/schematic inspector. One labelled OTA test draft
was retained locally. No original corpus records were changed. Model cancellation
and source immutability also have automated regressions.

Only Codex was live-tested: Ollama has no installed model here and Claude is
absent. Controlled adapter tests are not proof of their electrical reasoning.
Generation is useful for draft topology diagrams, not guaranteed circuit design.

For a repeatable live run with the app started:

```bash
PYTHONPATH=src .venv/bin/python scripts/verify-schematic-studio.py
PYTHONPATH=src .venv/bin/python scripts/verify-schematic-studio.py --source 1004 --polish
```
