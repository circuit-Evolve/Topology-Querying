# Search fidelity audit · 9 October 2026

> Latest follow-up: the deterministic-core repair below supersedes the earlier
> failing run for the ten researcher prompts. All ten completed without timeouts,
> with source-terminal checks on every displayed candidate. These are structural
> candidates, not simulation-certified electrical results; zero is not proof of
> corpus absence. Historical failures remain documented below.

This is a sampled development audit, **not a general electrical-accuracy
benchmark**. It tests explicit structural requirements and records where named
functions/performance cannot be verified. No circuit IDs are used by product
matching code; known IDs occur only as evaluation fixtures/counterexamples.

## Deterministic-core repair · 10 October 2026

The ten exact researcher prompts were rerun through the visible browser with
**Shared rules only · no model**, on the final repaired code. No converter or
prototype-generation model call was needed. This is a fresh end-to-end run,
not replay of cached conversions or saved result lists.

| # | Request | Eligible / displayed | First results | Server execution |
| --- | --- | --- | --- | --- |
| 1 | Two-stage differential input → common-source gain, direct compensation between stage outputs, T<25 | 90 / 20 | 884, 926, 2032 | 2.70s |
| 2 | PMOS pair, NMOS mirror load and NMOS output stage, direct compensation, T≤12 | 9 / 9 | 884, 2095, 2101 | 1.52s |
| 3 | NMOS differential input with separate source-degeneration resistors to a shared tail, R≥2, T<20 | 1 / 1 | 220 | 1.72s |
| 4 | NMOS diode-reference mirror with cascoded output branch, T<16 | 241 / 20 | 108, 672, 841 | 2.78s |
| 5 | NMOS G=external input, D=supply, S=distinct external output, T≤6 | 8 / 8 | 57, 20, 214 | 1.90s |
| 6 | Differential comparator path, cross-coupled PMOS loading and output stage, 8<T<24, L=0 | 1 / 1 | 1035 | 4.58s |
| 7 | Differential input / regenerative latch, external clock controlling tail OR reset, T<24 | 3 / 3 | 1051, 1062, 1039 | 10.14s |
| 8 | Differential amplifier containing a mirror, T<16; compensation optional; two stages preferred | 314 / 20 | 619, 333, 884 | 7.88s |
| 9 | Differential input → two distinct common-source gain stages, C≥2, T<20 | 0 / 0 | No supported structural matches | 2.89s |
| 10 | Two-stage op-amp candidates, C≥1, gain≥60dB and phase margin≥60° | 104 / 20 | 884, 738, 907 | 7.08s |

Timing is captured server execution, not inferred from time between browser
actions. Clocked-comparator execution spans several bounded transactions; the
existing **10-second per-transaction** timeout was not raised. The corpus contains
3,352 circuits. These measurements do not establish 10k-circuit scaling.

Every displayed result instance (102 across the ten requests, including repeated
circuits) passed mandatory count/witness checks and evaluation-only raw-terminal
oracles. The oracles enumerate terminals separately from the product matcher;
they still consume the same parsed canonical records, so parser errors are a
shared limitation. Source drawings were reviewed for representative results:
884, 220, 108, 57, 1035, all three clocked results, 619, 333, 908, 898, 914, 909
and 999. Many paper-derived records lack original PNGs; their netlists, not
nonexistent source drawings, were checked.

Important source nuances:

- 1051 has a clocked preamplifier and dynamic latch. 1039 capacitively couples
  analog inputs into a gated preamplifier/latch. The canonical matcher and the
  independent input trace include those capacitors, rather than treating internal
  gates as external inputs.
- 1062 has a credible clocked-comparator drawing, but its dataset netlist is a
  simplified/different connectivity representation: the drawing separates
  preamplifier/latch nodes and includes coupling capacitors absent from the `.cir`.
  The displayed witness describes the canonical netlist, not an asserted exact
  image-to-netlist correspondence. Clock waveforms and operation remain unverified.
- 57 contains a source-follower branch with an input-controlled load; it is not
  claimed to be a textbook ideal current-source-loaded follower. Mirror/follower
  retrieval can return blocks embedded in larger circuits.
- 8's two-stage preference is ranking evidence, not a compulsory stage count.
  One-stage circuits satisfying the required pair/mirror remain eligible.
- 9's zero applies to the conservative sequential gain-path interpretation. It
  neither relaxes requirements nor certifies absence of other three-stage designs.
- 10 returns connectivity candidates. Neither the 60dB gain nor 60° phase margin
  is verified; both remain prominently disclosed in the results.

### What the repair changes

Common requests use bounded composable rules → validated SearchPlan JSON →
canonical-source pre-filter → scoped, batched read-only Cypher → source witnesses
and ranking. The pre-filter retains all hard requirements; Neo4j checks them
again. Complete polarity alternatives are not silently capped to one guess.
Known bias/clock/logic interface names cannot masquerade as primary analog inputs;
mirror-reference branches cannot create extra voltage-gain stages; regenerative
output branches are conservatively rejected for linear-amplifier requests.

The selected converter remains available for uncovered vocabulary/wiring, using
the same schema, validation, compiler and ranker. Rules-only mode never silently
calls it. Identical supported requests are model-independent on the fast path;
arbitrary free-form electrical reasoning is **not** guaranteed equally accurate
across weaker and frontier models. Naming guards can reject unusual valid signal
names; exotic positive-feedback, buffered, cascode and indirect signal paths may
require an explicit custom pattern. There is no simulation or new corpus metadata.

Final review reproduced and fixed unintended capacitor endpoints, optional
degeneration becoming mandatory, history replay switching rules-only to Codex,
and concurrent reference-only completions. Tests preserve unsupported wiring
instead of silently changing it. Refresh clears fields/results and cancels only
the remembered job owned by that browser tab. Navigation prevents stale results
from an older form from overwriting the current view. Errors are not empty successes.

Fresh verification: **338 Python tests passed, 22 integration-gated tests skipped**;
**25 Node UI tests passed**; separately enabled **4 live Neo4j tests passed**,
including exact agreement with canonical candidate sets for two-stage, clocked
and follower plans. No expected IDs, exact audit prompts or audit files are
loaded by production matching code. No corpus records/annotations were edited.
Local ignored evidence: `output/researcher-live-20261010/repair-case-*.json`,
`repair-live-ui.json`, `repair-source-checks.json`, and timestamped server captures.

Additional browser checks: a two-stage request with T≤7 and C=0 returned nine
source-verified candidates; a 97-transistor mirror request returned zero; an
uncovered capacitor-between-inputs request in rules-only mode showed an explicit
unsupported-request error with no old cards. Refresh restored initial fields and
empty results. On the restored normal server, the Cypher console returned 20 rows
and reference-only similarity against 1004 returned 20 candidates without a
converter. History provider restoration and overlapping reference submissions
are additionally covered by UI regression tests.

The earlier audit below is retained as a historical baseline, not the current
result matrix.

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

### Follow-up: mixed-polarity requirements · 10 October 2026

The new prompt specifying a PMOS input pair, NMOS mirror load, separate NMOS
output stage, interstage capacitor and at most 12 transistors initially returned
zero. Diagnosis showed the model's complete pattern matched circuit 884, but
the core added an unrelated mandatory NMOS input pair: it selected the first
polarity mentioned anywhere in the request rather than the input pair's own
qualifier. This was a false negative, not corpus absence.

Curated motif selection now uses local noun-phrase qualifiers and clause boundaries.
An unqualified mirror retains its alternatives instead of inheriting another
block's polarity/technology. Eight regressions cover both MOS polarities, reversed
motif ordering, mixed MOS/BJT requests and actual source eligibility. They failed
before the fix and passed afterward. The historical model pattern replay and a
fresh Codex conversion through the UI both returned **10 matches**, with **884
first** in the fresh run. No circuit IDs or prompt-specific branches were added
to runtime code. This bounded qualifier grammar does not claim general language
understanding or electrical certification.

The fix makes explicit **structural** searching substantially stricter; it does
not solve all electrical reasoning. A model may propose the wrong complete
interpretation, an overly narrow pattern may miss a valid variant, a named
function can match an incidental subcircuit, and simulation/spec values are
unavailable. Inspection is still necessary. Near misses stay separately labelled
and cannot turn "no full matches" into an apparently successful exact search.

## Ten-prompt live audit completed · 10 October 2026

Audit scope: the original ten researcher prompts, with live browser tests starting
at number 3 as requested. Numbers 1–2 already had successful browser captures;
their saved plans were replayed against current Neo4j/source records. Successful
earlier conversions were not all reissued just to consume another model call.
Latest Codex default is **gpt-5.6-sol / high**, after the requested 6.1 model proved
unavailable to this CLI login. Prompt 4's successful capture predates this switch.
Ollama/Claude have no live accuracy evidence on this machine.

| # | Request, abbreviated | Observed outcome and source judgement |
| --- | --- | --- |
| 1 | Differential input → separate common-source stage, interstage capacitor, <25 transistors | Existing live capture: 10 displayed, including 884/926/2032. Current saved-plan replay: 90 hard-filter candidates, all literal/source-witness checks passed. Original 884 schematic/netlist supports the requested path. Replay is not a fresh conversion or ranking. |
| 2 | PMOS input pair, NMOS mirror load and output stage, interstage capacitor, ≤12 transistors | Fixed polarity scoping. Existing fresh browser capture: 10, with 884 first. Current replay: 10, literal/source-witness checks passed. |
| 3 | NMOS input pair with separate source-degeneration resistors, R≥2, <20 transistors | Fresh corrected conversion: 220 only. M2/M0 connect through separate R3/R2 to common net06; original drawing agrees. Earlier loose eight-hit scan was not eight verified amplifiers. |
| 4 | Diode-reference NMOS mirror with cascoded output, <16 transistors | 20 displayed; all passed literal mirror/stack terminal checks. 108/672 drawings support cascode mirrors. Some lower hits contain that block in a larger circuit rather than being standalone mirrors. |
| 5 | NMOS source follower: external gate input, supply drain, distinct external source output; ≤6 transistors | Corrected conversion: 20 displayed/20 eligible; all literal interface checks passed. 20 is a straightforward follower; 421/57 have follower-like branches inside more complicated networks. Whole-circuit function is not universally established. |
| 6 | Differential comparator, cross-coupled PMOS load and output stage; >8/<24 transistors, no L | Fresh corrected conversion: 1035 only. Netlist and original caption support a comparator with internal hysteresis/output stage. Unrequested output polarity/rail alias previously caused false zero. |
| 7 | Clocked comparator: differential input, regenerative latch, external clock-controlled tail/reset; <24 transistors | Successful run: 1062/559/560/564/1039/565. All passed the generated literal plan. 1062 is a credible clocked-comparator candidate; 1039 has a gated preamplifier/latch. Logic-latch/divider false positives remain. Final fresh retry timed out during conversion at 180 s; this is a failure, not zero matches. |
| 8 | Differential amplifier containing a mirror, <16 transistors; optional C, prefer two stages | Fresh corrected run: 20 displayed/446 eligible. All 20 passed independent pair/mirror checks. 675/155/889 source drawings support differential amplifiers with mirror loading. Single-stage hits are allowed because two stages were a preference, not a requirement. A preexisting uploaded OTA draft remains a draft. |
| 9 | Differential input → two distinct common-source stages in sequence; C≥2, <20 transistors | Fresh run: zero full matches, five separately labelled partials; 94.74 s. Current Neo4j replay also zero. Plan used only all-NMOS/all-PMOS alternatives. Broader independent mixed-polarity enumeration found wiring paths in 1004/1009, but source review does not establish three operating gain stages: mirror/bias paths can look like cascades, and 1009's apparent final node is a bias interface. Therefore **no corpus-absence claim**. |
| 10 | Two-stage op-amp, C≥1, DC gain≥60 dB, phase margin≥60° | Final fresh browser run completed in 65.36 s without database timeout: 989/1074/910/574/1050. All passed generated literal wiring/count checks, but only 989 is a plausible broad two-stage amplifier candidate. 1074/1050 are comparator networks; 574 is a feedback/switch network; 910's drawing has a three-stage path, so its embedded two-stage match is insufficient. Gain/phase margin were visibly marked unverified. **Functional accuracy failed for this result set.** |

### Verification performed and what it does not prove

Every displayed record from 3–8 and 10 (73 records, including repeated IDs across
requests) was checked against source counts, canonical terminal connections and
the current mandatory-plan witness validator. Independent hand-derived terminal
checks supplement this, but they too are only wiring proxies: prompt 10
demonstrates that those checks can pass while whole-circuit function/stage count
is wrong. Original drawings were inspected for representative positive results
and **all six prompt-7 and all five prompt-10 results**. Previously inspected
drawings/netlists were not claimed as new inspections.

For prompt 9, all 3,352 records were screened: 772 satisfy its counts. Eight MOS
polarity combinations were independently enumerated, with a direct reciprocal
feedback exclusion; 1004/1009 require further functional interpretation rather
than being accepted as confirmed three-stage amplifiers. Reciprocal paths in
574/1074 were excluded. This is not an exhaustive analog-topology classifier.

Fresh final software verification: **306 Python tests passed, 19 skipped**, one
existing Starlette/httpx deprecation warning; **18 Node UI tests passed**;
separate live Neo4j composite integration: **1 passed**. All 15 earlier saved
audit cases also passed their current structural checks in offline replay. None
of these statements imply 100% named-function accuracy or equal model quality.

The database timeout fix restricts optional hypothesis queries to the already
hard-filtered/source-validated candidate IDs, rather than repeating mandatory
joins. A captured failing workload replayed with individual soft queries below
1.5 s; the final prompt-10 live run succeeded. Conversion still has a separate
180 s deadline and can time out. Increasing deadlines is not an accuracy fix.

Local, ignored evidence: `output/researcher-live-20261010/case-*.json`, provider
`run-*.json`/`failure-*.json`, `final-source-recheck.json`, and UI screenshots.
The final replay helper never calls a provider or mutates circuit records.
It is evaluation-only and is not imported by production. Runtime inspection
found no result-ID lists or full audit-prompt routing branches. Existing 1004
examples demonstrate explicit reference-ID syntax, not a search answer whitelist.

### Remaining work, not hidden by the audit

- Whole-circuit function and coherent signal interfaces need stronger evidence:
  independent blocks can match incidental/bias/logic structures in one circuit.
- Two-stage containment does not prove **exactly** two operating gain stages.
- Model-generated alternatives may omit valid polarity/topology variants, causing
  false negatives. Identical plans are provider-independent; different model
  interpretations are not guaranteed to be equally accurate.
- Missing models, values and operating conditions prevent measured gain,
  stability or clock-waveform verification.

This follow-up finishes the requested testing, **not those unresolved accuracy
problems**. No prompt-specific special cases, result-ID exclusions, dataset edits,
new model installations, or silent hard-filter relaxation were used to force a
successful-looking answer.
