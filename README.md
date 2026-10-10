# Topology Querying · Circuit Atlas

A local, single-user research workbench for **analog circuit topology**. Inspect
netlists and schematics, explore their terminal-level graphs, run read-only
Cypher, and find circuits structurally similar to a reference circuit.

The repository ships **3,350 canonical AnalogGenie circuits**, not 10,000.
It does not automatically classify their function or verify electrical specs.
No custom training, hosted LLM, API key or AnalogGenie model checkpoint is needed.

## Start here

| You want to… | Read |
| --- | --- |
| Install and launch on a new machine | [Setup guide](docs/setup.md) |
| Understand the screens, queries and retrieval | [Workbench guide](docs/workbench.md) |
| Redraw a circuit or propose a schematic from words | [Schematic studio](docs/studio.md) |
| Contribute code, pull updates or push a branch | [Co-developer guide](CONTRIBUTING.md) |
| Use the parser, graph exports and legacy CLI tools | [Parser and graph tools](docs/parser-and-graph-tools.md) |

## Quick start

Install **Git**, **Python 3.11–3.13** (3.13 recommended), and **Docker**
first. Open Docker Desktop on Mac; on Linux, make sure `docker info` works
without running the project as root. Internet is needed for the initial setup.

```bash
git clone --recurse-submodules https://github.com/SatyagniCE/Topology-Querying.git
cd Topology-Querying
bash scripts/setup-workbench.sh
bash scripts/run-workbench.sh
```

The launcher opens [Circuit Atlas](http://127.0.0.1:8766/) automatically.
Keep its terminal open; **Ctrl+C** stops the web app.

**On Mac:** after downloading/cloning, double-click **Setup.command** once.
When setup finishes, double-click **Launch.command** for subsequent sessions.
The setup guide covers macOS permission prompts, ZIP downloads and prerequisites.

**Platforms:** the scripts target macOS and Linux; Windows users should use WSL2.
The current end-to-end setup verification was performed on macOS.
There is no native Windows double-click launcher.

### What setup does

1. Checks Python, Docker, corpus files and port availability.
2. Creates a project-only `.venv` and installs the workbench dependencies.
3. Fetches the pinned AnalogGenie source assets if missing.
4. Creates or reuses a local Neo4j Community container with persistent storage.
5. Imports **only missing circuits**, preserving existing graph records.
6. Builds/reuses local text and topology indexes and synchronizes Neo4j.

It does **not** install system software, retrain a model, generate semantic
metadata, clear a database or discard uploaded circuits/annotations.
Initial downloads, graph import and indexing take longer than later launches;
progress is printed in the terminal. Re-running setup resumes completed work.

## Capabilities

| Area | Available in V1 |
| --- | --- |
| Circuit library | Browse circuits, ID/text lookup, dataset/device filters |
| Circuit inspection | Available source schematic, netlist, canonical JSON, provenance and device counts |
| Graphs | NetworkX graph and live Neo4j graph, terminal connections, device inspector, zoom/Fit/expand and JSON exports |
| Structural queries | Read-only Cypher `MATCH`/`WHERE`, aggregation, paths and read subqueries |
| Vector queries | Explicit Neo4j vector `SEARCH` over synchronized text/topology vectors |
| Natural-language search | Validated JSON → compiled structural Cypher; optional temporary-prototype graph retrieval |
| Similarity | Optional reference circuit; reference-only retrieval bypasses the LLM |
| Schematic studio | Library redraw, prompt-only circuit drafts, optional placement polish, saved artifacts and SVG/PNG/JSON/netlist exports |
| Uploads | Validate and save supported flat netlists with a required description; optional ports, annotations and image |
| Annotations | Manual researcher edits, revision history and index/sync refresh |
| Query workflow | JSON parameters, successful-query history, table/graph views and result downloads |

**NetworkX and Neo4j are two views of the same canonical circuit model, not two
different inferred topologies.** Neo4j is needed for Cypher and its live graph;
the local library/NetworkX inspection can remain available if it goes offline.

## Search modes: what they actually mean

| Mode | Input and behavior | Important boundary |
| --- | --- | --- |
| Library lookup | Literal substring over circuit IDs, annotations and source-reference text | No embeddings |
| Reference similarity | Select a circuit; compare its wiring-derived descriptor with other circuits | No descriptions needed; similarity is not functional equivalence |
| Query patterns | Model interprets counts/connections into validated JSON; code compiles read-only Cypher | Explicit requirements are hard; inferred function patterns are hypotheses |
| Generated prototypes · experimental | Model generates 4–5 temporary netlists; eligible real circuits are ranked with the same graph fingerprint/full profiles | Anchors are neither inserted nor simulated; generated structure can be wrong |
| Hybrid evidence | Structure first, with available meaningful text and optional reference ranking | Text never overrides hard constraints; missing descriptions need not block structural search |
| Cypher | Run exactly the query you supply | No hidden English conversion or reranking inside the expert console |

For circuits with little semantic information, start with **query-pattern mode**
or explicit structural Cypher. Named function retrieval remains uncertain.
Counts such as “at least one capacitor” are translated to hard filters;
“two outputs” depends on whether output identity is actually known, not merely
whether two declared ports exist. Inspect the displayed JSON plan and evidence.

The topology descriptor is a deterministic, terminal-aware **768-dimensional
fingerprint**, using device counts, heuristic port roles, wiring motifs and
WL-style local neighborhoods. The UI rescores the top 100 topology candidates
using uncompressed structural features. Text uses local BGE-small, 384 dimensions.
Hybrid uses rank fusion. Native vector Cypher uses the stored fingerprint but
does **not** automatically apply the UI's Python reranker.
See [retrieval details](docs/workbench.md#how-retrieval-actually-works).

### Natural-language converters

Open **Query workbench → Natural language**, enter a request, choose a strategy
and converter, then **Search circuits**. Expand the plan, compiled Cypher or
prototype netlists to inspect what the search used. Click a candidate to see its
original schematic, netlist and graphs. Cancel stops this app's owned conversion;
successful requests are saved in history. A blank prompt with a selected reference
uses the original direct topology search without calling a model.
Refreshing resets query forms, options and visible results to their initial state.
Saved query history, annotations, circuits and Studio artifacts are retained.

- **Codex CLI:** install/sign in separately (`codex login`); current CLI must support
  structured output, `--ignore-user-config` and ephemeral/read-only execution.
- **Ollama:** start it and install a suitable structured-output model separately.
  Choose an installed model in the UI. No model is automatically downloaded.
- **Claude Code:** install/sign in separately (`claude auth login`); requires print
  mode/schema output and tool/MCP/hook isolation flags. Managed policies that can
  force hooks are rejected. This adapter needs live verification on your machine.

Both strategies work through the same provider interface. CLI model is optional
(Codex defaults to **gpt-5.6-sol with high reasoning**; an explicit model field
overrides the model); Ollama model is required. CLI authentication remains owned by
the CLI, never pasted into Circuit Atlas. Codex/Claude send the prompt/schema to
their provider and use normal account allowances; Ollama stays on loopback.
No automatic local-to-cloud fallback occurs. CLI availability is not a guarantee
of valid login or model access: a failed conversion is reported without querying.

All converters share [the machine-readable electrical rulebook](src/circuit_workbench/search-rulebook.json):
14 physical device contracts, 17 low-level primitives and 30 higher-level family
guides, including clocked comparators, StrongARM/double-tail latches, op-amps,
mirrors, references, filters and oscillators. Each guide distinguishes supporting
wiring from false positives and unverified specifications. Common motifs can be
selected by rule ID, so the model need not invent their terminal connections.
The runtime serves the same rulebook at `/api/natural/rulebook`.

The deterministic core independently parses common literal device-count phrases,
preserves strict/inclusive comparisons and rejects contradictions/placeholders.
It distinguishes an overall circuit from required embedded blocks: “op-amp
containing a mirror” keeps op-amp interpretations and checks mirror containment
within that same circuit. Unknown terms/custom patterns remain supported through
the validated model plan; this is not a closed circuit-family menu. Smaller models
are not guaranteed frontier-level accuracy; identical validated plans do use the
same query compiler and ranking regardless of provider.
Model-inferred blocks stay hypotheses unless explicit positive containment can be
grounded in curated wiring rules, or a complete connected pattern is grounded in
a verbatim quote covering all requested connections. Incomplete conversions ask
for clarification instead of searching a weaker request. Numbered gain-stage
requests require separate, ordered gain-device groups and connected signal
interfaces; this is wiring evidence, not a simulation-certified stage count.
A direct reciprocal gate–drain/base–collector regenerative branch is not counted
as an extra feedforward gain stage. This is a conservative wiring proxy, not a
general analysis of feedback or operating gain.

**LLM interpretation:** selecting Codex, Ollama or Claude always sends a nonempty
natural-language request to that selected model. The electrical rulebook guides
its JSON plan; deterministic validation, counts/wiring guards, Cypher compilation
and ranking follow. No Python interpretation replaces a selected model, even for
common requests. Provider failures remain failures; there is no silent no-model
or cloud-provider fallback. Codex CLI launches the executable installed on the
server machine using its existing login; inference is still remote. Ollama uses
an installed local model; Claude uses the installed Claude Code CLI.

**Optional rules-only mode:** **Shared rules only · no model** separately invokes
a bounded deterministic grammar for common differential-pair/degeneration,
mirror/cascode, follower, gain-stage and clocked-comparator requests. It is never
automatically selected for an LLM request. Uncovered wiring reports an unsupported
request rather than calling a model. Reference-only topology similarity remains
model-free when the prompt is blank.

For common requests, canonical source witnesses narrow the candidate IDs before
Neo4j checks the full constraints in bounded alternative batches. This avoids
expensive whole-corpus multi-pattern joins without dropping required alternatives
or raising the 10-second per-transaction timeout. Bias/clock/logic interfaces,
mirror-reference branches counted as gain stages, and regenerative amplifier
outputs have additional conservative guards. Source scans still grow with corpus
size; the repaired live audit covers 3,352 records, not a 10k scaling benchmark.

**Accuracy status:** the repaired ten-prompt **rules-only** browser run completed without timeouts;
all 102 displayed result instances passed count and raw-terminal checks. Previously
observed logic-latch/comparator false positives were excluded, and optional stage
preferences now affect ranking rather than eligibility. This is sampled structural
validation, not certification of circuit family, operating stage count, gain or
stability. Those timings/results are not an LLM demo benchmark. The strict
three-stage prompt returns no supported structural match,
not proof of corpus absence. See the
[repair results and coverage limits](docs/search-fidelity-evaluation.md#deterministic-core-repair--10-october-2026).
Different pattern net aliases mean different physical nets; intentionally shared
connections must reuse one alias. Resistors/capacitors/inductors match either
terminal orientation. Explicit terminal/interface clauses can require external
non-rail signals, supply, ground or either rail. Supply/ground checks use the
documented VDD/VCC/VSS/VEE/GND/0 naming conventions (plus VDD!, VCC!, VSS!, GND!),
not measured voltage; differently named supplies need explicit port bindings.
Explicit external-clock searches use VCLK/CLK/CLOCK/PHI/CK naming hints on an
external control gate; ordinary bias controls are not interchangeable. This
does not validate a waveform, phase or clocked operation, and differently named
clock controls need an explicit port-binding query.
An explicitly source-degenerated pair is not forced into the generic shared-source
pair template. Both retrieval strategies enforce the same mandatory
patterns against canonical records before ranking. Near misses are shown
separately and never counted as full results. Optional blocks do not filter results. Requests
for absence of a named block ask for clarification in V1 instead of reversing
their meaning; the expert Cypher console supports explicit absence queries.
Embedded-block patterns cannot fill the parent-function hypothesis budget or
qualify a plain mirror as a differential-amplifier candidate. Soft graph matching
runs only within the hard-filtered, source-validated pool rather than repeating
the mandatory graph search. These safeguards are bounded, not a general
electrical or natural-language proof.

For reproducible live checks, run `PYTHONPATH=src .venv/bin/python
scripts/verify-natural-search.py --case mirror --strategy prototypes` as one
terminal command. See [sampled result review](docs/search-evaluation.md).
The newer [search-fidelity audit](docs/search-fidelity-evaluation.md) records
multi-clause, two-stage, absent and near-match cases, including discovered failures.
Run `PYTHONPATH=src .venv/bin/python scripts/audit-natural-search.py` to repeat
the real-provider matrix; outputs are saved under ignored `output/search-fidelity`.

### Schematic studio

Click **Draw** in the Library or open the third tab. **Library** uses the stored
netlist without a model. **From words** needs only a circuit description: the
selected converter proposes a netlist internally, then the app checks and draws
it. Optional polish changes placement only. Zoom, pan, expand, edit placement JSON
and export the artifact; **Add draft to library** is an explicit opt-in action.
Every proposed design is labelled **not simulated**. See [the Studio guide](docs/studio.md).

## First five minutes

1. Open Library, search for `1004`, and open that circuit.
2. Inspect its netlist/schematic and toggle NetworkX ↔ Neo4j.
3. Choose **Find similar**, leave text empty, and inspect the returned candidates.
4. Open Query → Cypher and run the examples below.
5. Check the footer status: indexing complete, Neo4j connected, no pending sync.

Inventory:

```cypher
MATCH (c:Circuit)
RETURN count(c) AS circuits
```

Inspect circuit 1004's actual terminal connections:

```cypher
MATCH (c:Circuit {id:'analoggenie:1004'})-[:HAS_DEVICE]->(d:Device)
MATCH (d)-[r:CONNECTED_TO]->(n:Net)
RETURN d,r,n
LIMIT 100
```

More templates: [queries/](queries/) and [docs/queries/](docs/queries/).
The [three-stage diagnostic](docs/queries/three-stage-opamp-candidates.cypher)
is a narrowly defined **candidate pattern**, not a stage-count classifier.

## Limitations

- **No automatic semantic metadata.** Circuit family, named topology, stage count,
  functional roles and performance are not reliably labeled across the corpus.
  Manual annotations are user assertions, not independently verified facts.
- **No simulation or spec guarantees.** Gain, bandwidth, power, stability and supply
  range cannot be established from similarity scores or device counts.
- **Model interpretations can be wrong.** Schema validation checks supported syntax,
  not electronics. Broad structural hypotheses can match incidental subcircuits.
  Prototype mode can retrieve the wrong function despite high structural scores.
- **No trained circuit graph encoder or schematic understanding.** Graph vectors
  are engineered fingerprints; schematic images are displayed, not interpreted.
- **No broad electrical retrieval benchmark.** Regression fixtures and sampled
  rankings exist; they do not establish general retrieval accuracy.
- **Upload parser is deliberately limited.** Supported flat SPICE/typed netlists
  only; no `.include`, hierarchical `.subckt`, PDK resolution or control blocks.
  A valid upload is structurally parseable, not guaranteed electrically valid.
- **Query limits.** Read-only console, 10-second transaction timeout, default
  200 displayed rows; graph views cap at 1,200 nodes / 3,000 edges.
  Natural search has a separate 10,000-ID candidate cap with disclosed truncation,
  one active job and at most 20 retained jobs. Each converter call times out after
  180 seconds; one schema repair is allowed. Failed prototype graphs are disclosed.
- **Local V1 only.** No multi-user authentication/permissions or production
  hosting. Keep the app/database on loopback.
- **Scaling is not yet proven at 10k.** The committed corpus has 3,350 records.
  Source assets and Python/model/Neo4j dependencies consume additional storage.

## Architecture

```text
AnalogGenie source / supported uploads
                  │
                  ▼
      Canonical circuit JSON
         ┌────────┴─────────┐
         ▼                  ▼
   NetworkX graph       Neo4j graph
         │                  │
         └───── Circuit Atlas UI ─────┐
                                      │
                     Local SQLite catalog
                     annotations / uploads / history
                     text + topology vectors
                                      │
                             Neo4j vector sync
```

Parsing/graph construction records explicit device-terminal-to-net connections.
It does not infer a knowledge graph of electrical meaning.
SQLite holds local user state; Neo4j provides graph queries and synchronized
vector indexes. Browser UI assets are bundled; there is no Node build step.

## Repository layout

| Path | Purpose |
| --- | --- |
| `README.md`, `docs/setup.md`, `CONTRIBUTING.md` | Entry point, installation and collaboration |
| `Setup.command`, `Launch.command` | Mac double-click entry points |
| `scripts/setup-workbench.sh`, `scripts/run-workbench.sh` | Main setup/launch commands |
| `src/circuit_workbench/` | Web app, local catalog, upload validation, retrieval and runtime helpers |
| `src/circuit_ingest/` | Canonical parser, Neo4j storage and NetworkX/HTML exports |
| `src/gnn_pruning/` | Earlier general netlist/device-graph tools |
| `data/analoggenie/` | Committed circuit JSON, manifest, schema and audit |
| `AnalogGenie/` | Pinned upstream Git submodule: original sources/assets |
| `queries/`, `docs/queries/` | Cypher examples |
| `tests/` | Unit, environment-gated integration and UI helper tests |
| `visualizations/` | Prebuilt offline HTML graph snapshot |
| `output/` | Ignored local catalog, uploads, model cache and runtime credentials |

## Data, privacy and maintenance

The default web URL is `http://127.0.0.1:8766/`; Neo4j Browser is
`http://127.0.0.1:7474/`. Both database ports bind to loopback for new setups.
Neo4j has a locally generated password; Circuit Atlas reuses it without a login
prompt. Docker packages the database so Java/Neo4j need not be installed separately.

Your annotations, uploads, vectors and query history stay in
`output/workbench/`. Database data stays in Docker volume
`topology-querying-neo4j-data`. Newly generated runtime credentials are stored
privately in `output/runtime/neo4j.env`; existing containers retain their own
credentials. These are **not distributed through Git**.

Do not delete `output/`, remove the Docker volume, or use the replacing legacy
import command as a troubleshooting shortcut. See
[backup/restore and troubleshooting](docs/setup.md#backups-and-local-data).

To diagnose without changing data:

```bash
bash scripts/run-workbench.sh --doctor
```

## Development and tests

After setup:

```bash
.venv/bin/python -m pip install -e '.[workbench,test]'
PYTHONPATH=src .venv/bin/python -m pytest -q
```

Integration tests requiring Neo4j are gated; skips do not mean they passed.
For live-workbench verification with Neo4j/indexing ready:

```bash
PYTHONPATH=src .venv/bin/python scripts/verify-workbench.py
```

The live check writes successful query history but does not edit circuit content.
Optional UI helper tests use `node --test tests/ui/viewer-controls.test.mjs`;
Node is **not** required to run the application.

See [CONTRIBUTING.md](CONTRIBUTING.md) for Git cloning, branch/pull/push workflow,
GitHub authentication and when `git init` is appropriate.

## Upstream and licensing

Original circuit assets come from [AnalogGenie](https://github.com/xz-group/AnalogGenie),
pinned at `efc25358939c6bedd247f28d3df61066964f3a90`.
Our app reads its dataset; it does not run its training code or require Conda.
Respect the upstream license and any separately applicable source-figure rights.

Bundled visualization assets retain their third-party license notices.
This repository currently has no top-level license grant for its own code;
do not assume one from a dependency's license.
