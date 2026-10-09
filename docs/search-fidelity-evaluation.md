# Search fidelity audit · 9 October 2026

This is a sampled development audit, **not a general electrical-accuracy
benchmark**. It tests explicit structural requirements and records where named
functions/performance cannot be verified. No circuit IDs are used by product
matching code; known IDs occur only as evaluation fixtures/counterexamples.

## What was wrong and what changed

The original two-stage Miller request could rank circuit 615 first: it contains
an input pair, but no second gain transistor or compensation capacitor. The
converter's connected request was being treated as optional hypotheses.

The corrected path is: request → typed JSON → independent intent audit →
application-owned structural Cypher → canonical-netlist witness checks → ranking.
Counts and complete quote-grounded connection requirements are mandatory in
**both** modes. Every temporary prototype must meet the same requirements.
Unmatched/invalid structures are rejected, not promoted by similarity scores.

Numbered signal stages require separate, ordered gain-device groups and
connected input/output nets. Different net aliases cannot collapse onto one net.
This removes the false second stage formed from an input pair's mirror load
(circuit 181). It is still a structural proxy, not operating-point simulation.

RC/L terminals are interchangeable; MOS/BJT/diode terminal identities are not.
"Diode-connected transistor" no longer means a required discrete diode.
Explicit differential inputs require distinct control inputs in the first
stage. Composite Cypher uses successive device traversals and DISTINCT horizons:
the real four-alternative EXPLAIN timeout is fixed without increasing timeout.
Fixed tuples in provider schemas are ordinary fixed-length typed arrays, fixing
a live `invalid_json_schema` rejection. Failed calls remain failures, not empty
successful searches. Only recognized connection failures get one same-provider
retry; authentication/schema/unknown failures do not silently switch providers.

Fresh final review found three additional edge cases, reproduced with failing
tests before fixes: a complete quote hiding a wrong typed-terminal connection,
"a resistor and an optional capacitor" erasing the resistor, and a preferred
stage count overriding a mandatory one. The core now checks supported explicit
typed-terminal connections/passive endpoints, scopes mixed optional phrases,
and extracts stage counts only from positive mandatory clauses. An additional
NPN/PNP regression verifies the terminal guard is not an op-amp/MOS-only recipe.
These grammar checks are bounded; they are not a general English/electrical
semantic proof. Unresolved explicit terminal pronouns ask for clarification.

Audit prompts, gold IDs and corpus counterexamples are confined to test fixtures
and this report. Runtime code does not load `search-audit.json` or
`complex-search-plan.json`, and contains none of their expected circuit IDs.

## Case matrix and evidence

Real Codex conversions were run for 14 initial cases, in both strategies where
listed, with repeated reruns of failures. A fifteenth genuine near-miss case was
added after corpus inspection. Captured requests, plans, every displayed source
netlist/witness and diagnostics live in ignored `output/search-fidelity/`.
Earlier failing passes are retained separately under `*-first-pass` and
`*-second-pass`. These files are local evidence, not distributed corpus labels.

| Request class | Mode | Observed top examples / outcome |
| --- | --- | --- |
| Differential input → separate common-source stage → interstage capacitor; <25 transistors | Patterns | 884, 926, 2032; independent wiring oracle passed; excludes 615/181 |
| Same connected request | Prototypes | 2032, 2033, 2043; independent wiring oracle passed; excludes 615/181 |
| NMOS mirror, diode-connected reference, shared gate/source, separate output | Patterns | 726, 698, 102; mirror wiring passed |
| Same mirror request | Prototypes | 672, 836, 841; mirror wiring passed |
| Exactly two NMOS, no C, shared sources, separate external gates/drains | Patterns | 615, 192, 408 after injective-net rerun; literal wiring passed |
| Series-connected R/C, different outer endpoints | Patterns | 651, 218, 403; passive-orientation wiring passed |
| Same R/C request | Prototypes | 651, 223, 469; wiring passed |
| Exactly two total transistors but a pair feeding a distinct gain transistor | Patterns | Clarification, no query; internally contradictory request |
| Exactly one NPN, one PNP, three inductors, no MOS | Patterns | Zero full matches; count combination absent |
| At least 48 MOS and four capacitors | Prototypes | Zero full matches; corpus maximum MOS count is 47 |
| Comparator candidates, >8 transistors, no inductors | Patterns | 1035, 1051, 1045; count/source checks passed, function remains inferred |
| Same comparator request | Prototypes | 1064, 1904, 634; counts passed, function remains inferred |
| Two-stage candidates, C≥1, gain≥60dB, phase margin≥60° | Patterns | 884, 738, 907; cascade wiring passed; performance explicitly unverified |
| One MOS, R gate–drain, C gate–source, distinct G/D/S | Patterns | 697; positive exact wiring example |
| Exactly three devices: one MOS, R gate–drain, C drain–source | Patterns | Zero full matches, five labelled partials; seven circuits satisfy counts, none satisfy wiring |

Final captures are a mixture of fresh conversion reruns and rechecking earlier
successful conversions against the latest canonical witness validator. They are
not 15 independent successful model conversions on the final revision. Model
plans/rankings can vary between runs. The script's hand-derived oracle patterns
are independent of converter plans but reuse the terminal matcher; manual source
review and real Neo4j integration supplement that shared dependency.

## Manual researcher review

- **884:** original Book schematic and `.cir` show a PMOS differential pair,
  NMOS mirror load, a separate NMOS common-source output stage and C between
  first-stage node and output. The source drawing's current-source abstractions
  differ from simplified dataset elements; no numerical performance is claimed.
- **738:** image/netlist show the same cascade with a transistor in the
  compensation path. It belongs in the broad two-stage/C request, not necessarily
  a strict direct-capacitor request. The independent oracle was corrected to
  avoid imposing an unrequested Miller constraint on that broad prompt.
- **907:** original image shows input pair, separate output gain stage and a
  buffered compensation path. Operating gain/phase margin remain unknown.
- **2032:** netlist shows MM3/MM0 differential inputs, net011 driving MM5 gate,
  MM5 drain at VOUT1, and CC0 across net011/VOUT1. MM6 is a biased load, not
  a third cascaded signal stage. 2032/2033/2043 lack source PNGs: reviewed netlists,
  not nonexistent original drawings. Duplicate source names retain unique
  canonical device identities.
- **726:** source image depicts the diode-connected reference and shared-gate
  NMOS output; mirror *containment* is evidence, not whole-circuit classification.
- **651:** source schematic is the simple R/C junction example; numeric values
  pictured are not inferred into absent canonical device values.
- **1035:** source image explicitly captions a comparator with internal
  hysteresis/output stage; cross-coupled PMOS structure agrees with its netlist.
- **1064:** source image captions comparator plus Schmitt trigger. **634** has
  cross-coupled regenerative loading and a differential front end. **1904** has
  no source PNG and only weak comparator evidence from its netlist: it is a
  questionable function candidate, not a verified comparator. Prototype ranking
  still cannot replace family metadata/simulation.

## Repeat it

Final verification: **265 Python tests passed, 19 skipped**, one existing
Starlette/httpx deprecation warning; **18 Node UI tests passed**; the real Neo4j
composite integration passed separately. All 15 captured cases passed the
current structural audit. Original and near-miss prompts were rerun live after
the review fixes; outcomes remained 884/926/2032 and zero full/five partials.
Browser walkthrough verified original search, graph → schematic → netlist,
zero-result state, expanded partial diagnostics, and successful-query history.
Screenshots: `output/search-fidelity/884-inspection.png`,
`two-stage-browser.png`, `near-miss-browser.png` (local, ignored evidence).

Start Circuit Atlas/Neo4j normally. From the repository:

```bash
PYTHONPATH=src .venv/bin/python scripts/audit-natural-search.py
PYTHONPATH=src .venv/bin/python scripts/audit-natural-search.py --offline
PYTHONPATH=src RUN_NL_LIVE_NEO4J=1 .venv/bin/python -m pytest -q tests/integration/test_nl_composites.py
PYTHONPATH=src .venv/bin/python -m pytest -q
node --test tests/ui/*.test.mjs
```

The real-provider run uses existing CLI login/account allowances and takes time;
no software/models are installed. Ollama has no installed model on this machine,
and Claude CLI is absent, so neither has live-provider accuracy evidence here.
All providers still use the same JSON contract/compiler/eligibility/ranking.

## Remaining boundary

The fix makes explicit **structural** searching substantially stricter; it does
not solve all electrical reasoning. A model may propose the wrong complete
interpretation, an overly narrow pattern may miss a valid variant, a named
function can match an incidental subcircuit, and simulation/spec values are
unavailable. Inspection is still necessary. Near misses stay separately labelled
and cannot turn "no full matches" into an apparently successful exact search.
