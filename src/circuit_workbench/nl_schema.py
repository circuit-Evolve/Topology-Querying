"""Bounded, declarative search contracts; no model-authored executable queries."""
from typing import Annotated, Literal
from pydantic import BaseModel, ConfigDict, Field, StrictInt, model_validator
from circuit_ingest.registry import DEVICE_SPECS

TERMINALS = {s.canonical_type: s.terminals for s in DEVICE_SPECS.values()}
TERMINALS.update(voltage_source=("p", "n"), current_source=("p", "n"))
RECIPROCAL_TYPES = frozenset({'resistor','capacitor','inductor'})
NET_ROLE_NAMES = {
    'supply': ('VDD','VCC','VDD!','VCC!'),
    'ground': ('VSS','VEE','GND','0','GND!','VSS!'),
}
NET_ROLE_NAMES['rail'] = NET_ROLE_NAMES['supply'] + NET_ROLE_NAMES['ground']
CLOCK_NAME_PATTERN = r'^(VCLK|CLK|CLOCK|PHI|CK).*'
# Explicit source naming evidence, not an inferred voltage/waveform. Unknown
# names remain allowed; known bias, clock and digital interfaces do not become
# analog inputs merely because they are external ports.
NON_SIGNAL_NAME_PATTERN = r'^(VB.*|IB.*|BIAS.*|VREF.*|IREF.*|VCLK.*|CLK.*|CLOCK.*|PHI.*|CK.*|LOGIC.*)$'
DeviceType = Literal["nmos", "pmos", "npn", "pnp", "resistor", "capacitor", "inductor", "diode", "voltage_source", "current_source", "xor", "pfd", "inverter", "transmission_gate"]
Entity = Literal["device", "transistor", "mos", "bjt", "port", "net", "nmos", "pmos", "npn", "pnp", "resistor", "capacitor", "inductor", "diode", "voltage_source", "current_source", "xor", "pfd", "inverter", "transmission_gate"]
Alias = Annotated[str, Field(pattern=r"^[A-Za-z][A-Za-z0-9_]{0,31}$")]
Text = Annotated[str, Field(max_length=2000)]


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid")


class PatternDevice(Contract):
    alias: Alias
    type: DeviceType


class Edge(Contract):
    device: Alias
    terminal: Annotated[str, Field(max_length=24)]
    net: Alias


class PortBinding(Contract):
    net: Alias
    name: Annotated[str, Field(min_length=1, max_length=100)]


class NetCondition(Contract):
    net: Alias
    condition: Literal["not_rail", "external", "supply", "ground", "rail", "clock_named", "signal", "linear_output"]


class SignalStage(Contract):
    devices: list[Alias] = Field(min_length=1,max_length=16)
    input_nets: list[Alias] = Field(min_length=1,max_length=4)
    output_nets: list[Alias] = Field(min_length=1,max_length=4)


class GraphPattern(Contract):
    devices: list[PatternDevice] = Field(min_length=1, max_length=16)
    nets: list[Alias] = Field(min_length=1, max_length=24)
    edges: list[Edge] = Field(min_length=1, max_length=64)
    ports: list[PortBinding] = Field(default_factory=list, max_length=24)
    distinct_nets: list[tuple[Alias, Alias]] = Field(default_factory=list, max_length=64)
    net_conditions: list[NetCondition] = Field(default_factory=list, max_length=24)
    signal_stages: list[SignalStage] = Field(default_factory=list,max_length=5)

    @model_validator(mode="after")
    def consistent(self):
        kinds = {d.alias: d.type for d in self.devices}
        if len(kinds) != len(self.devices) or len(set(self.nets)) != len(self.nets):
            raise ValueError("Pattern aliases must be unique.")
        seen = set()
        for e in self.edges:
            if e.device not in kinds or e.net not in self.nets:
                raise ValueError("An edge references an undeclared device or net.")
            if e.terminal not in TERMINALS[kinds[e.device]]:
                raise ValueError("Terminal is incompatible with its device type.")
            if (e.device, e.terminal) in seen:
                raise ValueError("Each device terminal can bind to one net only.")
            seen.add((e.device, e.terminal))
        if set(kinds) != {e.device for e in self.edges} or set(self.nets) != {e.net for e in self.edges}:
            raise ValueError("Every declared device and net needs a terminal edge.")
        if any(p.net not in self.nets for p in self.ports):
            raise ValueError("Port references an undeclared net.")
        if any(a not in self.nets or b not in self.nets or a == b for a, b in self.distinct_nets):
            raise ValueError("Invalid distinct-net condition.")
        if any(c.net not in self.nets for c in self.net_conditions):
            raise ValueError("Net condition references an undeclared net.")
        used=set();previous=None;prior_outputs=set()
        for stage in self.signal_stages:
            if len(set(stage.devices))!=len(stage.devices) or used.intersection(stage.devices):raise ValueError('Signal stages must use disjoint device groups.')
            if any(d not in kinds or kinds[d] not in {'nmos','pmos','npn','pnp'} for d in stage.devices):raise ValueError('Active signal stages reference declared gain transistors only.')
            if not set(stage.input_nets+stage.output_nets)<=set(self.nets) or set(stage.input_nets)&set(stage.output_nets):raise ValueError('Signal-stage input/output nets must be declared and distinct.')
            inputs={e.net for e in self.edges if e.device in stage.devices and e.terminal in {'gate','base','source','emitter'}}
            outputs={e.net for e in self.edges if e.device in stage.devices and e.terminal in {'drain','collector','source','emitter'}}
            if not set(stage.input_nets)<=inputs or not set(stage.output_nets)<=outputs:raise ValueError('Stage signals must bind real transistor input/output terminals.')
            if previous is not None and not previous.intersection(stage.input_nets):raise ValueError('Ordered signal stages must connect output to next input.')
            if prior_outputs.intersection(stage.output_nets):raise ValueError('Later cascade outputs cannot be earlier gain-device output nodes (e.g. an active load).')
            primary_roles={e.terminal for e in self.edges if e.device in stage.devices and e.net in stage.output_nets and e.terminal in {'drain','collector','source','emitter'}}
            prior_outputs.update(e.net for e in self.edges if e.device in stage.devices and e.terminal in primary_roles)
            used.update(stage.devices);previous=set(stage.output_nets)
        return self


def stage_feedback_constraints(pattern):
    """Direct reciprocal active branches are regeneration, not extra cascade stages.

    This conservative feedforward proxy does not classify all feedback circuits.
    Each tuple describes a forbidden reverse control/output contact pair.
    """
    kinds={d.alias:d.type for d in pattern.devices}
    contacts={d.alias:{e.terminal:e.net for e in pattern.edges if e.device==d.alias} for d in pattern.devices}
    checks=[]
    for before,after in zip(pattern.signal_stages,pattern.signal_stages[1:]):
        for alias in after.devices:
            kind=kinds[alias]
            control,output=('gate','drain') if kind in {'nmos','pmos'} else ('base','collector')
            a,b=contacts[alias].get(control),contacts[alias].get(output)
            if a in before.output_nets and a in after.input_nets and b in after.output_nets:
                check=(kind,control,output,a,b)
                if check not in checks:checks.append(check)
    return checks


def stage_gain_constraints(pattern):
    """Reject current-replication inputs in the conservative linear-stage proxy.

    A gain device whose control is a same-type diode-reference node is a mirror
    branch, not evidence of another voltage-gain stage. This is deliberately
    conservative; unusual hybrid/translinear circuits need custom search.
    """
    if not any(c.condition == 'linear_output' for c in pattern.net_conditions):
        return []
    kinds = {d.alias: d.type for d in pattern.devices}
    checks = []
    for stage in pattern.signal_stages[1:]:
        for alias in stage.devices:
            kind = kinds[alias]
            control, output = ('gate', 'drain') if kind in {'nmos', 'pmos'} else ('base', 'collector')
            inputs = {e.net for e in pattern.edges if e.device == alias and e.terminal == control}
            checks.extend((kind, control, output, net) for net in inputs & set(stage.input_nets))
    return checks


class CountConstraint(Contract):
    entity: Entity
    operator: Literal["eq", "gt", "ge", "lt", "le"]
    value: Annotated[StrictInt, Field(ge=0, le=100000)]


class PropertyConstraint(Contract):
    field: Literal["dataset", "family", "topology", "input_mode", "output_mode", "stage_count"]
    value: Annotated[str, Field(max_length=200)] | StrictInt

    @model_validator(mode="after")
    def typed(self):
        if self.field == "stage_count":
            if type(self.value) is not int or not 1 <= self.value <= 20:
                raise ValueError("stage_count must be an annotated integer from 1 to 20.")
        elif not isinstance(self.value, str):
            raise ValueError("This stored property needs a text value.")
        return self


class Hypothesis(Contract):
    interpretation: Text
    pattern: GraphPattern


class RequiredBlock(Contract):
    name: Annotated[str, Field(min_length=1, max_length=150)]
    source_quote: Annotated[str, Field(max_length=6000)] = ""
    alternatives: list[GraphPattern] = Field(min_length=1, max_length=16)


class Unverified(Contract):
    requirement: Text
    reason: Text
    evidence_needed: Text


class SearchPlan(Contract):
    schema_version: Literal["1"] = "1"
    requested_function: Text = ""
    requested_topology: Text = ""
    count_constraints: list[CountConstraint] = Field(default_factory=list, max_length=20)
    property_constraints: list[PropertyConstraint] = Field(default_factory=list, max_length=10)
    required_pattern: GraphPattern | None = None
    required_pattern_source: Annotated[str, Field(max_length=6000)] = ""
    required_blocks: list[RequiredBlock] = Field(default_factory=list, max_length=5)
    hypotheses: list[Hypothesis] = Field(default_factory=list, max_length=16)
    hypothesis_rules: list[Literal["mos_mirror", "mos_diff_pair", "bjt_mirror", "cascode_stack", "cross_coupled", "cmos_inverter", "rc_branch"]] = Field(default_factory=list, max_length=5)
    semantic_text: Text = ""
    reference_id: Annotated[str, Field(max_length=200)] = ""
    unverified_requirements: list[Unverified] = Field(default_factory=list, max_length=20)
    clarification_questions: list[Text] = Field(default_factory=list, max_length=10)


class Prototype(Contract):
    name: Annotated[str, Field(min_length=1, max_length=150)]
    description: Annotated[str, Field(min_length=1, max_length=2000)]
    netlist: Annotated[str, Field(min_length=1, max_length=16000)]
    ports: Annotated[str, Field(max_length=2000)]
    rationale: Text


class PrototypeBatch(Contract):
    prototypes: list[Prototype] = Field(min_length=4, max_length=5)


class NaturalRequest(Contract):
    text: Annotated[str, Field(min_length=1, max_length=6000)]
    strategy: Literal["patterns", "prototypes"] = "patterns"
    interpretation: Literal['auto', 'rules_only'] = 'auto'
    provider: Literal["codex", "ollama", "claude"] = "codex"
    model: Annotated[str, Field(max_length=150, pattern=r"^[A-Za-z0-9_.:/-]*$")] = ""
    reference_id: Annotated[str, Field(max_length=200)] = ""
    limit: Annotated[StrictInt, Field(ge=1, le=100)] = 20
