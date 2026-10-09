"""Prompt-only design drafts and immutable library schematic artifacts."""
from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3
import threading
from typing import Annotated, Literal
import uuid
from pydantic import Field, model_validator
from circuit_ingest.models import CircuitRecord
from .nl_schema import Contract, SearchPlan
from .nl_core import relevant_rules, parse_counts
from .nl_providers import validated_generate
from .nl_search import meets_plan
from .schematic import LayoutPlan, auto_layout, render_schematic
from .uploads import parse_upload


class StudioRequest(Contract):
    mode: Literal['library','netlist','prompt','artifact']='library'
    source_id: str=Field(default='',max_length=200)
    prompt: str=Field(default='',max_length=6000)
    netlist: str=Field(default='',max_length=1_000_000)
    description: str=Field(default='',max_length=6000)
    ports: str=Field(default='',max_length=20000)
    provider: Literal['codex','claude','ollama']='codex'
    model: str=Field(default='',max_length=150,pattern=r'^[A-Za-z0-9_.:/-]*$')
    polish: bool=False
    style: Literal['connected','labels']='connected'

    @model_validator(mode='after')
    def input_required(self):
        if self.mode in {'library','artifact'} and not self.source_id:raise ValueError('Choose a source circuit/drawing.')
        if self.mode=='prompt' and not self.prompt.strip():raise ValueError('Describe the proposed circuit to generate.')
        if self.mode=='netlist' and (not self.netlist.strip() or not self.description.strip()):raise ValueError('Supply a netlist and basic description.')
        return self


class CircuitProposal(Contract):
    name: str=Field(min_length=1,max_length=150)
    description: str=Field(min_length=1,max_length=3000)
    netlist: str=Field(min_length=1,max_length=32000)
    ports: str=Field(max_length=2000)
    assumptions: list[str]=Field(default_factory=list,max_length=20)
    unverified: list[str]=Field(default_factory=list,max_length=20)
    layout: LayoutPlan|None=None


class StudioStore:
    def __init__(self,path):
        self.path=Path(path);self.path.mkdir(parents=True,exist_ok=True)
        self.database=self.path/'artifacts.sqlite3'
        with self.connect() as db:db.execute('CREATE TABLE IF NOT EXISTS artifacts(id TEXT PRIMARY KEY,created TEXT NOT NULL,name TEXT NOT NULL,data TEXT NOT NULL)')

    def connect(self):
        db=sqlite3.connect(self.database,timeout=10);db.row_factory=sqlite3.Row
        return db

    def save(self,result):
        result={**result,'id':str(uuid.uuid4()),'created':datetime.now(timezone.utc).isoformat()}
        with self.connect() as db:db.execute('INSERT INTO artifacts VALUES(?,?,?,?)',(result['id'],result['created'],result['name'],json.dumps(result)))
        return result

    def get(self,identifier):
        with self.connect() as db:row=db.execute('SELECT data FROM artifacts WHERE id=?',(identifier,)).fetchone()
        if row is None:raise KeyError(identifier)
        return json.loads(row['data'])

    def list(self):
        with self.connect() as db:rows=db.execute('SELECT id,created,name FROM artifacts ORDER BY created DESC LIMIT 50').fetchall()
        return [dict(row) for row in rows]


PROPOSAL_CONTEXT="""Propose a small analog circuit as a draft topology and a clean schematic.
This is NOT an electrically certified design. Return supported flat parenthesized
typed netlist devices with unique instance names, at most 64 devices:
M1 (drain gate source bulk) nmos4/pmos4; Q1 (collector base emitter substrate)
npn/pnp; R1 (p n) resistor r=10k; C1 (p n) capacitor c=1p; L1 (p n) inductor l=1u;
D1 (p n) diode; I1 (p n) isource dc=10u; V1 (p n) vsource dc=1.8.
Use real intentional connections, no disconnected count-padding, directives,
includes, behavioral/hierarchical models or tool execution. Name supply/ground
VDD/VSS and explicit signals INP/INN/OUT/CLK when appropriate. ports lists actual
external net names separated by spaces. An externally supplied clock/reference
may be a port; do not claim its waveform is provided by the drawing. Body/substrate
contacts must be explicit. Values may be illustrative; disclose this, bias/test
assumptions and unverified performance in the JSON. Preserve literal requested
counts exactly. Do not invent claimed simulation results or measured specs.
Optional layout uses netlist device ordinals (1-based device statement order),
each once, non-overlapping integer grid column/row and horizontal flip only.
Prefer supplies/load devices above input/gain devices, bias/tail devices below,
mirrored pairs side by side, gate-facing orientation, and compact placement.
If unsure, set layout to null for deterministic placement. Return JSON only.
"""

LAYOUT_CONTEXT="""Improve only the placement of this immutable analog netlist.
Return LayoutPlan JSON: each listed ordinal exactly once, distinct integer
column/row (prefer columns 0..5, rows 0..6), horizontal flip where gates should
face paired devices. Do not change the netlist, types, terminals or connections.
No executable SVG, tools or arbitrary wire coordinates. Application code owns
symbols and routing. Prefer compact symmetric input/mirror pairs, supplies and
loads above, tail/bias below; minimize long signal connections. Rows are not proof
of gain stages. Return every schema field including flip/rationale.
"""


def proposal_warnings(record):
    warnings=[]
    declared={p.net_id for p in record.ports}
    for device in record.devices:
        terminals={c.terminal:c.net_id for c in device.connections}
        if device.canonical_type in {'nmos','pmos'} and terminals.get('drain')==terminals.get('source'):
            warnings.append(f'{device.source_instance}: drain/source shorted; review whether intentional.')
        for contact in device.connections:
            net=next(n for n in record.nets if n.id==contact.net_id)
            if net.degree_by_terminal==1 and net.id not in declared and contact.terminal in {'gate','base'}:
                warnings.append(f'{device.source_instance}.{contact.terminal}: singly connected undeclared control net {net.name}.')
    return list(dict.fromkeys(warnings))


class Studio:
    def __init__(self,catalog,store,generate=validated_generate):
        self.catalog,self.store,self.generate=catalog,store,generate

    def run(self,request,cancel,progress):
        request=StudioRequest.model_validate(request)
        assumptions,unverified,warnings,proposed_layout=[],[],[],None
        progress('loading circuit source')
        if request.mode=='library':
            row=self.catalog.row(request.source_id);record=CircuitRecord.model_validate_json(row['record'])
            netlist=row['netlist'];meta=json.loads(row['metadata']);name=meta.get('title') or 'Circuit '+record.source_circuit_id
            description=meta.get('description') or 'Schematic regenerated from canonical source netlist.'
            source={'kind':'library','circuit_id':record.circuit_id,'revision':row['revision'],'sha256':record.source.primary_sha256}
        elif request.mode=='artifact':
            artifact=self.store.get(request.source_id);record=CircuitRecord.model_validate(artifact['record'])
            netlist=artifact['netlist'];name=artifact['name'];description=artifact['description'];source={**artifact['source'],'parent_artifact':artifact['id']}
            proposed_layout=LayoutPlan.model_validate(artifact['layout']);assumptions=artifact['assumptions'];unverified=artifact['unverified']
        elif request.mode=='netlist':
            netlist=request.netlist;description=request.description;name='Netlist schematic'
            record=parse_upload(netlist,description,request.ports)
            source={'kind':'pasted','sha256':record.source.primary_sha256}
        else:
            counts,questions=parse_counts(request.prompt)
            if questions:raise ValueError('Clarify the design request: '+' '.join(questions))
            progress('proposing circuit netlist')
            proposal=self.generate(CircuitProposal,PROPOSAL_CONTEXT+'\nElectrical guidance:\n'+json.dumps(relevant_rules(request.prompt))+'\nUser request:\n'+request.prompt,request.provider,request.model,cancel)
            netlist=proposal.netlist;description=proposal.description;name=proposal.name
            record=parse_upload(netlist,description,proposal.ports)
            if len(record.devices)>64:raise ValueError('Prompt proposals are limited to 64 devices.')
            if not meets_plan(record,{},SearchPlan(count_constraints=counts)):raise ValueError('The proposed circuit does not meet the independently checked device count requirements. Nothing was saved.')
            source={'kind':'proposed','sha256':record.source.primary_sha256,'prompt':request.prompt,'provider':request.provider,'model':request.model or 'provider default'}
            assumptions=proposal.assumptions;unverified=proposal.unverified;proposed_layout=proposal.layout
            unverified=list(dict.fromkeys(unverified+['Circuit function, bias, stability, timing and performance have not been simulated.']))
        if cancel.is_set():raise InterruptedError()
        warnings+=proposal_warnings(record)
        if request.polish:
            if len(record.devices)>64:raise ValueError('Model-assisted layout is limited to 64 devices; automatic labelled rendering supports larger library circuits.')
            progress('polishing placement with selected model')
            context={'devices':[{'ordinal':d.ordinal,'instance':d.source_instance,'type':d.canonical_type,'connections':{c.terminal:next(n.name for n in record.nets if n.id==c.net_id) for c in d.connections}} for d in record.devices], 'ports':[p.name for p in record.ports]}
            proposed_layout=self.generate(LayoutPlan,LAYOUT_CONTEXT+'\nCircuit:\n'+json.dumps(context),request.provider,request.model,cancel)
        progress('routing and checking schematic')
        layout=proposed_layout or auto_layout(record)
        try:
            drawing=render_schematic(record,layout,name,request.style)
        except ValueError:
            if proposed_layout is None:raise
            warnings.append('Model placement was invalid; used disclosed deterministic placement without changing the circuit or provider.')
            layout=auto_layout(record);drawing=render_schematic(record,layout,name,request.style)
        if cancel.is_set():raise InterruptedError()
        result={**drawing,'name':name,'description':description,'source':source,'netlist':netlist,'ports':' '.join(p.name for p in record.ports),
                'record':record.model_dump(mode='json'),'assumptions':assumptions,'unverified':unverified,
                'warnings':warnings+drawing['warnings'],'provider':request.provider if request.mode=='prompt' or request.polish else 'deterministic',
                'simulation_status':'not performed','request':request.model_dump(exclude={'netlist'})}
        progress('saving drawing artifact')
        return self.store.save(result)

    def relayout(self,identifier,layout):
        artifact=self.store.get(identifier);record=CircuitRecord.model_validate(artifact['record'])
        drawing=render_schematic(record,layout,artifact['name'],artifact['request'].get('style','connected'))
        return self.store.save({**artifact,**drawing,'source':{**artifact['source'],'parent_artifact':identifier},'warnings':drawing['warnings']})
