# General natural language circuit search

## Purpose and scope

Build the natural-language search pipeline first on `natural-language-query`.
An analog engineer supplies an ordinary request describing circuit function,
topology, devices, connections and other requirements. A reference circuit is
optional and normally absent. The application returns existing dataset circuits
with evidence for the requirements it can check, rather than invented circuits
or unsupported claims of electrical correctness.

Replace the current text-similarity interface with Natural language search.
Preserve the Cypher console and optional reference picker/reference-only
similarity behavior. Schematic rendering is a separate subsequent milestone.
Do not enrich/classify the whole corpus, train a model, install graph plugins,
or download a local model automatically in this milestone.

## Search interpretation

The pipeline is prompt → provider-generated JSON plan → validation → compiled,
parameterized read-only Cypher → eligible candidates → evidence/ranking → top K.
The provider is a query interpreter, not a database executor.

The JSON schema is generic. It describes the physical entities/relations that
the repository supports; it does not restrict users to a list of circuit families
or hard-code a comparator request. Circuit-function/topology names remain open
text, with structural interpretations expressed through generic graph patterns.

Each plan separates:

- Hard requirements: supported device/category counts, declared ports, dataset,
  supported stored properties and explicitly requested connections.
- Structural hypotheses: alternative partial wiring patterns relevant to the
  requested function/topology. They are candidate-finding interpretations, not
  assertions that the wiring proves a circuit family.
- Semantic context: residual function/preferences to compare with available
  descriptions, annotations and source text.
- Unverified requirements: information absent from available records or not
  established by connectivity, such as measured gain, power, stability or stage
  count. Do not invent database properties for these.
- Clarifications: unresolved numbers, contradictions or materially ambiguous
  requirements. Ask instead of guessing.

Examples span functions and structures: op-amps/OTAs, comparators, current
mirrors/references, BJT-based references, filters, oscillators, cascodes and user-
described arrangements. Recognizing a term does not guarantee the dataset has
matching circuits or enough evidence to confirm it.

## Intermediate representation

Use versioned Pydantic models with extra fields forbidden. Provider output must
conform to their JSON Schema and pass independent application validation.

Plan fields:

- `schema_version`: fixed supported version.
- `requested_function` and `requested_topology`: optional free text.
- `count_constraints`: typed entity/device/category, comparison and integer value.
- `property_constraints`: allowed stored field, typed comparison and value.
- `required_pattern`: optional generic connection pattern explicitly requested.
- `required_blocks`: ANDed embedded building blocks, each with ORed structural alternatives within the same parent circuit.
- `hypotheses`: zero to five distinct partial graph patterns plus interpretation.
- `hypothesis_rules`: curated primitive IDs expanded to typed patterns by application code, reducing model wiring burden.
- `semantic_text`: a concise residual search description.
- `reference_id`: optional explicit prompt reference; reconcile with the picker.
- `unverified_requirements`: original requirement, reason and evidence needed.
- `clarification_questions`: zero or more concise questions.

Graph patterns contain bounded device and net variables, typed terminal-to-net
edges, optional port-to-net bindings, and explicit equality/inequality conditions.
Validate device types against supported canonical types, terminals against their
device contracts, aliases/references against declarations and property operations
against an allowlist. Bound each pattern to 16 devices, 24 nets and 64 terminal
edges. Separate device variables denote distinct devices unless the same alias
is deliberately reused. All matched entities belong to the same Circuit.

No raw executable Cypher, shell commands, embeddings, SVG or complete generated
netlists are accepted as a query-plan field. Descriptive explanations are treated
as text, never instructions. The model cannot fabricate numeric vectors.

## Cypher compilation and retrieval

Compile the validated plan in application code. Parameterize values and allow
only application-owned structural query forms. Keep the existing EXPLAIN/read-
only checks, transaction timeout and bans on writes/procedures/external imports.

Count filters distinguish transistor counts from all-device counts. MOS and BJT
types count as transistors; passive counts use their actual canonical types.
Preserve strict versus inclusive comparisons: more than 12 means at least 13,
not at least 12. An unspecified `x`/`y` remains a clarification, not a number.

Hard requirements select eligible circuits before ranking. Explicit requested
wiring can be a hard pattern; inferred function interpretations are hypotheses
and must not silently become additional compulsory constraints.

Compile up to five hypotheses into alternative structural MATCH queries over
eligible circuits. Union and deduplicate their results while recording matched
devices/nets/terminals and which interpretation matched. Sparse descriptions
must not prevent this structural retrieval path from working.

Use a dedicated internal scalar candidate-query path, not the console's graph
serializer or its 200-row display/50-shortcut caps. Support an eligible set up to
10,000 circuit IDs with explicit counts/truncation beyond that bound. Never
silently limit a broad eligible set to the first 200 circuits before ranking.
Bounded queries time out rather than becoming unbounded agent/database work.

If no hypothesis matches, distinguish that from zero circuits meeting the hard
filters. Permit an explicitly identified weaker/count-only candidate tier, not
silent relaxation of a hard requirement or a fabricated functional match.

## Ranking and evidence

Rank the eligible set using independent evidence channels:

1. Available explicit user annotations/source descriptions, qualified by provenance.
2. Matched structural hypotheses and connection evidence.
3. Optional existing text-embedding relevance when useful text is present.
4. Optional reference topology similarity only when a reference is supplied.

Preserve the existing reference fingerprint/full-pattern reranking path. Reference-
only search works without running an LLM. A rare prompt reference such as 1004
is interpreted correctly; conflicting prompt and picker references require
clarification rather than silently choosing one.

Use rank fusion where applicable, deterministic tie-breaking and deduplication.
Do not repeatedly reward a circuit simply because duplicate hypotheses returned
it. Expose each active ranking signal; cosine/fusion scores are not probabilities
of meeting electrical specifications. Text-only relevance cannot override a hard
count or connection requirement.

Every result reports exact count checks, matched graph connections, available
annotation/text evidence and requirements that remain unverified. Label inferred
function results as candidates. Netlist parsing and graph consistency are not
simulation or proof that an op-amp/comparator meets the requested performance.
Do not persist inferred family/role/spec labels into circuit metadata.

## Hypothetical circuit alternatives

The initial multi-interpretation feature generates partial structural query plans,
not complete dummy circuits. A MATCH query is a selector, not a circuit graph
that can be passed to the current topology fingerprint.

Implement a toggleable experimental prototype mode alongside query-pattern mode.
The selected provider generates four or five temporary typed netlists with ports,
descriptions and rationale. Validate them with the existing parser, bound each to
64 devices, reject duplicates, and encode accepted graphs with terminal-wl-v3.
Use best-prototype cosine followed by full-profile reranking over eligible real
circuits. Hard requirements still apply before ranking. Never ingest prototypes
into the dataset or present them as simulated/working circuits. Expose their
netlists and validation diagnostics. Partial query-pattern matching is not
equivalent to full-circuit cosine similarity; compare both empirically.

## Provider adapters

All providers receive the same routed, versioned machine-readable electrical
rulebook. It covers physical devices, lower-level motifs, higher-level families,
parent-versus-contained-block intent, false positives and evidence limits. Common
count phrases are parsed independently and override model errors; contradictions,
placeholders and ungrounded counts trigger clarification. Do not claim weaker
models are universally as accurate: unfamiliar function interpretation and
generated prototypes still depend on model reasoning.

Support one schema/interface for Ollama, Codex CLI and Claude Code CLI. Detect
availability and surface authentication/model errors clearly. Do not silently
switch from a local provider to a cloud provider or download model weights.

Ollama uses schema-constrained local HTTP responses. Codex uses non-interactive
schema-constrained output. Claude Code uses non-interactive schema output. All
responses undergo the same validation, with at most one bounded repair attempt.
Invalid plans are not executed. Timeouts/cancellation terminate only the owned
request/process, not unrelated sessions.

Run CLI interpretation in a dedicated restricted workspace with no database
credentials in its environment, no circuit-state write access, and no inherited
project hooks/MCP integrations. Use compatible CLI permission/structured-output
capabilities; incompatible configurations are unavailable rather than bypassed.
Only the prompt, schema and necessary schema context go to a cloud converter.
Selecting a cloud provider explicitly acknowledges remote processing and normal
account usage. Do not copy credentials into the app or source repository.

Use the user's existing provider authentication where supported. On the current
Mac, Codex CLI is signed in, Ollama has no listed model and Claude Code is not
on PATH. Do not present all three as ready. The implementation must still be
provider-independent and expose unavailable options with setup guidance.

## User interface and API

Retain two main tabs: Cypher and Natural language search. Natural language search
has a general prompt, provider/model selection as applicable, result count and
the existing optional reference picker. Most requests require no reference.

Show a compact search interpretation/requirements summary, candidate results and
collapsible JSON plan/generated Cypher/parameters. Distinguish interpreting,
querying and ranking states. Errors retain the draft. Surface clarification,
unsupported requirements, provider failure, index/Neo4j unavailability, zero
matches and weaker candidate tiers separately.

Add server-side provider status and cancellable search-job endpoints.
Validate submitted plans again on execution. Do not allow a browser client to
submit arbitrary planner-generated Cypher through the new endpoint. Keep direct
expert Cypher use in its existing guarded endpoint.

Keep the existing local catalog and original circuit data authoritative. Store
successful search history with plan/provider versions and parameters, excluding
credentials and provider debug output. Preserve current graph/detail navigation,
query history, uploads, user edits and reference-only similarity behavior.

## Acceptance and evaluation

- General no-reference prompts run through the full pipeline and return real IDs.
- Tests exercise counts, connection patterns and descriptive requests across
  multiple functions, not just comparators or circuit 1004.
- More-than/at-least/exact/fewer-than/range semantics are tested independently.
- Family inference is not treated as a verified label; unsupported performance
  requirements are never translated into nonexistent hard database fields.
- Unknown types/terminals/properties, missing values, conflicts, malicious text,
  invalid JSON, oversized patterns and write attempts fail safely.
- Hard filters apply before ranking, and broad candidate pools are not silently
  capped by the console serializer.
- Duplicate hypotheses/results, missing metadata/vectors and no-match cases have
  deterministic and clearly qualified behavior.
- The optional picker and rare textual reference work without becoming mandatory.
- Provider tests cover availability, invalid schema output, one repair attempt,
  timeouts, cancellation and absence of database credentials in converter calls.
- Real-provider end-to-end checks are explicitly distinguished from mocked tests.
- Browser checks cover prompt → interpretation → results → circuit inspection,
  drafts/history, error recovery and current viewport layout.

Evaluate on a small reviewed set of varied engineer-style requests before claiming
general functional retrieval accuracy. Syntax/schema validation proves neither
the interpretation nor the returned circuit's electrical behavior.

Manually inspect top results' original schematic images and netlists for both
strategies; record supported, questionable and incorrect matches with reasons.
Report live-provider checks separately from adapter tests or unavailable models.

## Provider references

- [Ollama structured outputs](https://docs.ollama.com/capabilities/structured-outputs)
- [Codex non-interactive structured output](https://developers.openai.com/codex/noninteractive)
- [Claude Code programmatic execution](https://code.claude.com/docs/en/headless)

The renderer and its standalone/editor integration remain required follow-on work,
but are intentionally outside this first search-pipeline milestone.
