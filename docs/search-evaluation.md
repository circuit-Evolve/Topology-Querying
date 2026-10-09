# Sampled natural-language retrieval review

These are actual local checks against the 3,351-record research catalog, not a
general accuracy benchmark. Codex CLI generated the plans/prototypes; Ollama has
no installed model on this Mac and Claude is absent, so their adapter tests are
not evidence of live model accuracy. No circuits were automatically classified,
modified or ingested by this evaluation. No electrical simulations were run.

Raw plans, scores, netlists and source asset references are saved locally under
`output/natural-evaluation/` (ignored by Git). `*-replay.json` means a captured
real-provider plan was rerun through the updated deterministic core/Neo4j, not
a fresh model call. Replaying isolates ranking/rule changes from model variance.

## Findings from netlist and original-image inspection

| Request/mode | Inspected results | Finding |
| --- | --- | --- |
| NMOS mirror, fewer than 12 transistors · query patterns | 726, 698, 102 | Mirror wiring supported. 726 is a focused two-transistor mirror; 698 adds a capacitor; 102 is a larger current-transfer/mirror network. Counts checked from canonical devices. |
| Same mirror request · four generated prototypes | 672, 836, 841 | Images/netlists support cascoded, multilevel and feedback mirror structures. 672 matches a generated cascoded anchor's full structural profile. Score 1.0 does not establish current ratio/compliance. |
| Differential amplifier, capacitor ≥1, transistors <20 · query patterns | 181, 282, 422 | 181/282 have differential-input amplifier cores and capacitors. 422 was a poor result: an LC-loaded/follower-like network, not a confirmed differential input stage. This exposed the need to distinguish actual input-name hints from bias-only shared-source patterns. 181's bridging capacitor and 282's output capacitor differ; compensation performance remains unknown. |
| Same amplifier request · updated input-hint ranking | 181, 282, 283 | All three original images/netlists inspected. 283 has a differential NMOS pair, PMOS biased loads and two output capacitors; the source figure's tail source is represented as an external bias net in the corpus netlist, not an included source device. |
| Same amplifier request · four generated prototypes | 2032, 2033, 2043 | Netlists have distinct input-gate differential pairs, PMOS mirror loads, a second output stage and bridging capacitor; plausible amplifier topology candidates. Original images are absent, so no image-based confirmation or performance guarantee. |
| Comparator, transistors >8, inductors =0 · initial broad rules | 363, 567, 601 | Poor functional results: telescopic amplifier and clocked logic structures. Shared-source/cross-coupled motifs alone were insufficient. This failure triggered stricter combined-pattern guidance and removal of grounded pseudo-pairs. |
| Same comparator request · updated deterministic composite rules | 1046, 1035, 741 | Images/netlists support clocked regenerative, explicitly captioned hysteretic-comparator and preamp/gain/positive-feedback comparison structures. These are supported comparator candidates, not delay/offset/clock-phase certificates. |
| Same comparator request · generated prototypes | 1809, 1810, 1836 | Netlists support differential gain/current-transfer structures, but comparator function remains uncertain. Original images are absent for these results, so a schematic-based confirmation is impossible. Prototype mode is experimental and is not proven better for generic family retrieval. |

The initial mirror ranking also returned 2137/2146 (amplifiers containing mirror
cores) before focused mirrors. We changed ranking so structural coverage/full
prototype evidence precedes secondary text/reference fusion. Numeric citations
and count filler no longer act as circuit-function text. Missing descriptions do
not disable structural retrieval.

## What is and is not demonstrated

- Literal counts are independently checked; Cypher compilation and ranking do not
  depend on the provider. Broad retrieval was checked beyond the console's 200-row
  cap (2,383 eligible IDs in one count test).
- A model can select a curated rule ID instead of inventing pin wiring. The same
  expanded rule runs through the same compiler for every provider.
- Parent intent and containment are separate: an amplifier containing a mirror is
  not automatically classified as a standalone mirror. Required blocks must be in
  the same circuit, and alternative implementations are ORed within a block.
- Pattern coverage is a retrieval heuristic. Generic family requests can still
  produce weak fallback candidates. Source citations may describe related circuits,
  not the precise subfigure. All such results remain labelled candidates.
- Generated prototypes can be useful anchors, but an inappropriate generated
  topology can steer ranking toward the wrong function. Parseability is not design
  correctness. Invalid/duplicate anchors are disclosed; they are never ingested.
- No claim of local-model/frontier-model reasoning parity is established by these
  checks. Identical validated plans are deterministic; interpretations may differ.

## Reproduce

Start Circuit Atlas, then run:

```bash
PYTHONPATH=src .venv/bin/python scripts/verify-natural-search.py --case mirror --strategy prototypes
PYTHONPATH=src .venv/bin/python scripts/verify-natural-search.py --case comparator --strategy patterns
PYTHONPATH=src .venv/bin/python scripts/verify-natural-search.py --case amplifier --strategy patterns
```

For a deterministic replay of a captured plan, add
`--replay-plan output/natural-evaluation/comparator-patterns.json` with the
matching case/strategy. Do not judge result quality from successful execution or
cosine scores alone: inspect the returned netlists and available original images.
