"""Owned typed-pin schematic renderer inspired by cirfig_gen, not an agent fork.

Models choose placement, never wire coordinates. All electrical contacts derive
from the canonical netlist. Routing uses obstacle-aware orthogonal paths; named
net connections are explicit fallbacks, not silently omitted wires.
"""
from collections import Counter, defaultdict
from heapq import heappop, heappush
from html import escape
import math
from typing import Annotated, Literal
from pydantic import Field, StrictInt
from .nl_schema import Contract
from .topology import port_role

STEP=10
TILE_W,TILE_H=240,170


class Placement(Contract):
    ordinal: Annotated[StrictInt,Field(ge=1,le=2000)]
    column: Annotated[StrictInt,Field(ge=0,le=30)]
    row: Annotated[StrictInt,Field(ge=0,le=1999)]
    flip: bool=False


class LayoutPlan(Contract):
    placements: list[Placement]=Field(min_length=1,max_length=2000)
    rationale: str=Field(default="",max_length=3000)


def auto_layout(record):
    """Conservative polarity/source grouping, not inferred signal-stage labels."""
    names={n.id:n.name for n in record.nets}
    groups=defaultdict(list)
    for device in record.devices:
        terminals={c.terminal:c.net_id for c in device.connections}
        source=names.get(terminals.get('source',terminals.get('emitter','')),'')
        role=port_role(source)
        group=0 if device.canonical_type=='pmos' and role=='supply' else 2 if device.canonical_type in {'nmos','npn'} and role=='ground' else 1
        groups[group].append(device)
    placements=[]
    columns=min(6,max(2,math.ceil(math.sqrt(len(record.devices)))))
    ordered=[device for group in sorted(groups) for device in groups[group]]
    for i,device in enumerate(ordered):
        placements.append(Placement(ordinal=device.ordinal,column=i%columns,row=i//columns,flip=False))
    return LayoutPlan(placements=placements,rationale='Grouped by physical polarity/source connection; rows are not certified gain stages.')


def _geometry(device):
    """Symbol SVG in a 120×80 grid, with explicit semantic pin coordinates."""
    kind=device.canonical_type
    line=lambda path:f'<path d="{path}" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"/>'
    if kind in {'nmos','pmos'}:
        # PMOS source is upper; NMOS drain is upper. Never swap based on rotation.
        pins={'gate':(0,40),'bulk':(120,40)}
        pins.update({'drain':(80,0),'source':(80,80)} if kind=='nmos' else {'source':(80,0),'drain':(80,80)})
        body=line('M 0 40 H 34 M 36 18 V 62 M 50 18 V 62 M 50 20 H 80 V 0 M 50 60 H 80 V 80 M 50 40 H 120')
        body+=('<path d="M 60 34 L 50 40 L 60 46 Z" fill="currentColor"/>' if kind=='nmos' else '<path d="M 60 34 L 70 40 L 60 46 Z" fill="currentColor"/>')
        if kind=='pmos':body+='<circle cx="28" cy="40" r="5" fill="white" stroke="currentColor" stroke-width="2"/>'
        return body,pins,False
    if kind in {'npn','pnp'}:
        pins={'base':(0,40),'collector':(80,0),'emitter':(80,80),'substrate':(120,40)}
        body=line('M 0 40 H 42 M 42 18 V 62 M 42 26 L 80 8 V 0 M 42 54 L 80 72 V 80 M 92 40 H 120')
        body+='<circle cx="62" cy="40" r="34" fill="none" stroke="currentColor" stroke-width="1.4"/>'
        body+=('<path d="M 67 62 L 80 72 L 67 72 Z" fill="currentColor"/>' if kind=='npn' else '<path d="M 67 58 L 54 58 L 62 69 Z" fill="currentColor"/>')
        return body,pins,False
    if kind in {'resistor','capacitor','inductor','diode','voltage_source','current_source'}:
        pins={'p':(0,40),'n':(120,40)}
        if kind=='resistor':body=line('M 0 40 H 30 L 35 28 L 45 52 L 55 28 L 65 52 L 75 28 L 85 52 L 90 40 H 120')
        elif kind=='capacitor':body=line('M 0 40 H 52 M 52 18 V 62 M 68 18 V 62 M 68 40 H 120')
        elif kind=='inductor':body=line('M 0 40 H 28 C 28 18 44 18 44 40 C 44 18 60 18 60 40 C 60 18 76 18 76 40 C 76 18 92 18 92 40 H 120')
        elif kind=='diode':body=line('M 0 40 H 38 M 38 20 L 72 40 L 38 60 Z M 76 20 V 60 M 76 40 H 120')
        else:
            body=line('M 0 40 H 35 M 85 40 H 120')+'<circle cx="60" cy="40" r="25" fill="white" stroke="currentColor" stroke-width="2.2"/>'
            body+=line('M 46 40 H 74 M 64 32 L 74 40 L 64 48') if kind=='current_source' else line('M 48 34 V 46 M 42 40 H 54 M 68 40 H 80')
        return body,pins,False
    terminals=[c.terminal for c in device.connections]
    height=max(80,20*math.ceil(len(terminals)/2))
    body=f'<rect x="25" y="0" width="70" height="{height}" rx="3" fill="white" stroke="currentColor" stroke-width="2"/>'
    body+=f'<text x="60" y="{height/2}" text-anchor="middle" font-size="9">{escape(kind)}</text>'
    pins={}
    half=math.ceil(len(terminals)/2)
    for i,terminal in enumerate(terminals):
        left=i<half;y=10+20*(i if left else i-half);x=0 if left else 120
        pins[terminal]=(x,y)
        body+=line(f'M {x} {y} H {25 if left else 95}')
        body+=f'<text x="{29 if left else 91}" y="{y+3}" text-anchor="{"start" if left else "end"}" font-size="6">{escape(terminal)}</text>'
    return body,pins,True


def _path(start,goals,blocked,occupied,net_id,width,height,max_states=12000):
    """A* over a bounded orthogonal grid, avoiding devices and other nets."""
    goal_set=set(goals)
    heuristic=lambda p:min(abs(p[0]-g[0])+abs(p[1]-g[1]) for g in goal_set)
    queue=[(heuristic(start),0,start)];previous={};cost={start:0};visited=0
    while queue and visited<max_states:
        _,distance,current=heappop(queue);visited+=1
        if distance!=cost[current]:continue
        if current in goal_set:
            result=[current]
            while current in previous:current=previous[current];result.append(current)
            return result[::-1]
        for dx,dy in ((STEP,0),(-STEP,0),(0,STEP),(0,-STEP)):
            next_point=(current[0]+dx,current[1]+dy)
            if not 20<=next_point[0]<=width-20 or not 90<=next_point[1]<=height-20:continue
            if next_point in blocked and next_point not in goal_set:continue
            owner=occupied.get(next_point)
            if owner is not None and owner!=net_id:continue
            candidate=distance+STEP
            if candidate<cost.get(next_point,float('inf')):
                cost[next_point]=candidate;previous[next_point]=current
                heappush(queue,(candidate+heuristic(next_point),candidate,next_point))
    return None


def verify_pin_manifest(record,pins):
    expected=Counter((d.ordinal,c.terminal,c.net_id) for d in record.devices for c in d.connections)
    actual=Counter((p['ordinal'],p['terminal'],p['net_id']) for p in pins)
    if expected!=actual:
        raise ValueError('Drawing pin/net manifest does not exactly match the netlist.')
    coordinates={}
    for pin in pins:
        key=(pin['x'],pin['y'])
        if key in coordinates and coordinates[key]!=pin['net_id']:
            raise ValueError('Different nets share a drawn pin coordinate.')
        coordinates[key]=pin['net_id']
    return True


def _segment_points(start,end):
    x,y=start;tx,ty=end
    if x!=tx and y!=ty:raise ValueError('A wire must be orthogonal.')
    dx=0 if x==tx else STEP if tx>x else -STEP
    dy=0 if y==ty else STEP if ty>y else -STEP
    if abs(tx-x)%STEP or abs(ty-y)%STEP:raise ValueError('Wire endpoints must be on the routing grid.')
    points=[(x,y)]
    while (x,y)!=(tx,ty):x+=dx;y+=dy;points.append((x,y))
    return points


def verify_wire_paths(pins,paths):
    occupied={}
    def add(point,net_id):
        if point in occupied and occupied[point]!=net_id:
            raise ValueError('Different nets touch/cross in the physical wire drawing.')
        occupied[point]=net_id
    for pin in pins:
        for point in _segment_points((pin['x'],pin['y']),tuple(pin['stub'])):add(point,pin['net_id'])
    for path in paths:
        for start,end in zip(path['points'],path['points'][1:]):
            for point in _segment_points(tuple(start),tuple(end)):add(point,path['net_id'])
    return occupied


def render_schematic(record,layout,name,style='connected'):
    layout=LayoutPlan.model_validate(layout.model_dump())
    expected={d.ordinal for d in record.devices}
    ordinals=[p.ordinal for p in layout.placements]
    if len(set(ordinals))!=len(ordinals) or set(ordinals)!=expected:
        raise ValueError('A layout must include every device ordinal exactly once.')
    cells=[(p.column,p.row) for p in layout.placements]
    if len(set(cells))!=len(cells):raise ValueError('Device placements overlap; choose distinct grid cells.')
    if style not in {'connected','labels'}:raise ValueError('Choose connected or labels rendering.')
    placements={p.ordinal:p for p in layout.placements}
    nets={n.id:n for n in record.nets}
    if len({n.name for n in record.nets})!=len(record.nets):raise ValueError('Net names must be unambiguous for labelled connectivity.')
    width=160+(max(p.column for p in layout.placements)+1)*TILE_W
    height=140+(max(p.row for p in layout.placements)+1)*TILE_H
    pins,symbols,blocked,warnings=[],[],set(),[]
    groups=defaultdict(list)
    for device in record.devices:
        placement=placements[device.ordinal];x=80+placement.column*TILE_W;y=130+placement.row*TILE_H
        body,local_pins,opaque=_geometry(device)
        if opaque:warnings.append(f'D{device.ordinal}: opaque {device.canonical_type} drawn with its declared contacts; no transistor internals inferred.')
        if set(local_pins)!={c.terminal for c in device.connections}:
            raise ValueError(f'Device D{device.ordinal} has terminals incompatible with its drawable symbol.')
        transform=f'translate({x+120 if placement.flip else x},{y})'+(' scale(-1,1)' if placement.flip else '')
        instance=device.source_instance if len(device.source_instance)<=8 else device.source_instance[:7]+'…'
        label=f'{instance} · D{device.ordinal:03d}'
        symbols.append(f'<g transform="{transform}" color="#262b25">{body}</g><text x="{x+145}" y="{y+15}" font-size="12" font-weight="600">{escape(label)}</text><text x="{x+145}" y="{y+31}" font-size="9" fill="#6c7466">{escape(device.canonical_type)}</text>')
        parameters=' '.join(f'{k}={v}' for k,v in device.parameters.items() if k.lower() in {'r','c','l','w','dc'})
        if parameters:symbols.append(f'<text x="{x+145}" y="{y+61}" font-size="8" fill="#75806d"><title>{escape(parameters)}</title>{escape(parameters[:22])}</text>')
        # Reserve body, device label and parameter areas before routing.
        for bx in range(x+10,x+111,STEP):
            for by in range(y+10,y+80,STEP):blocked.add((bx,by))
        for bx in range(x+140,x+201,STEP):
            for by in range(y-10,y+40,STEP):blocked.add((bx,by))
            if parameters:
                for by in range(y+50,y+80,STEP):blocked.add((bx,by))
        for connection in device.connections:
            px,py=local_pins[connection.terminal]
            if placement.flip:px=120-px
            pin=(x+px,y+py)
            direction=(-1,0) if px==0 else (1,0) if px==120 else (0,-1) if py==0 else (0,1)
            stub=(pin[0]+direction[0]*20,pin[1]+direction[1]*20)
            net=nets[connection.net_id]
            item={'ordinal':device.ordinal,'instance':device.source_instance,'terminal':connection.terminal,'net_id':net.id,'net_name':net.name,'x':pin[0],'y':pin[1],'stub':list(stub),'direction':list(direction)}
            pins.append(item);groups[net.id].append(item)
    verify_pin_manifest(record,pins)
    route_style=style if len(record.devices)<=40 else 'labels'
    if style=='connected' and route_style=='labels':warnings.append('Large circuit: labelled-connectivity mode avoids an unreadable wire maze; identical net names are electrical connections.')
    occupied=verify_wire_paths(pins,[])
    fixed_pin_points=set(occupied)
    wire_paths,labelled,junctions=[],set(),[]
    for net_id,members in sorted(groups.items(),key=lambda pair:(len(pair[1]),pair[0])):
        net=nets[net_id];role=port_role(net.name)
        if route_style=='labels' or role in {'supply','ground'} or len(members)==1 or any(p['terminal'] in {'bulk','substrate'} for p in members):
            labelled.add(net_id);continue
        starts=[tuple(p['stub']) for p in members]
        tree={starts[0]};paths=[];failed=False
        for start in starts[1:]:
            route=_path(start,tree,blocked,occupied,net_id,width,height)
            if route is None:failed=True;break
            paths.append(route);tree.update(route)
            for point in route:occupied[point]=net_id
        if failed:
            labelled.add(net_id);occupied={p:n for p,n in occupied.items() if n!=net_id or p in fixed_pin_points}
            warnings.append(f'{net.name}: routing used explicit repeated net labels to avoid obstacles/other nets.')
        else:
            for path in paths:wire_paths.append({'net_id':net_id,'points':[list(p) for p in path]})
            adjacency=defaultdict(set)
            for pin in members:
                stub_path=_segment_points((pin['x'],pin['y']),tuple(pin['stub']))
                for a,b in zip(stub_path,stub_path[1:]):adjacency[a].add(b);adjacency[b].add(a)
            for path in paths:
                for a,b in zip(path,path[1:]):adjacency[a].add(b);adjacency[b].add(a)
            junctions += [(net_id,p) for p,neighbors in adjacency.items() if len(neighbors)>=3]
    verify_wire_paths(pins,wire_paths)
    wires=[]
    for pin in pins:
        net=nets[pin['net_id']];dx,dy=pin['direction'];sx,sy=pin['stub']
        wires.append(f'<path d="M {pin["x"]} {pin["y"]} L {sx} {sy}" data-net="{escape(net.id,quote=True)}" fill="none" stroke="#3d4938" stroke-width="1.8"/>')
        if pin['net_id'] in labelled or (net.is_external and groups[net.id][0] is pin):
            anchor='end' if dx<0 else 'start' if dx>0 else 'middle'
            lx=sx+dx*4;ly=sy+(4 if dx else -5 if dy<0 else 13)
            if pin['net_id'] not in labelled:
                anchor='start';lx=sx+12;ly=sy+4
                wires.append(f'<circle cx="{sx}" cy="{sy}" r="3" fill="#fcfcf8" stroke="#3d4938" stroke-width="1.5"/>')
            label=net.name if len(net.name)<=18 else net.name[:13]+'…N'+str(next(i for i,n in enumerate(record.nets,1) if n.id==net.id))
            wires.append(f'<text x="{lx}" y="{ly}" text-anchor="{anchor}" font-size="10" fill="#4e6344"><title>{escape(net.name)} · {escape(pin["terminal"])}</title>{escape(label)}</text>')
        # Body/substrate labels are always explicit even when physical wiring is drawn.
        if pin['terminal'] in {'bulk','substrate'}:
            wires.append(f'<text x="{pin["x"]-4}" y="{pin["y"]-7}" text-anchor="end" font-size="8" fill="#777">{escape(pin["terminal"])}</text>')
    for path in wire_paths:
        points=' '.join(f'{x},{y}' for x,y in path['points'])
        wires.append(f'<polyline points="{points}" data-net="{escape(path["net_id"],quote=True)}" fill="none" stroke="#3d4938" stroke-width="1.8" stroke-linejoin="round"/>')
    for net_id,(x,y) in junctions:wires.append(f'<circle cx="{x}" cy="{y}" r="3" fill="#3d4938" data-net="{escape(net_id,quote=True)}"/>')
    port_text='Ports: '+', '.join(p.name for p in record.ports)
    if len(port_text)>110:port_text=port_text[:107]+'…'
    subtitle='Typed netlist schematic · '+('labelled connectivity' if route_style=='labels' else 'orthogonal routing with labelled rail/fallback nets')
    svg=f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}pt" height="{height}pt" viewBox="0 0 {width} {height}" role="img" aria-label="{escape(name,quote=True)}"><rect width="100%" height="100%" fill="#fcfcf8"/><g font-family="Helvetica,Arial,sans-serif" fill="#262b25"><text x="30" y="35" font-size="20" font-weight="600">{escape(name)}</text><text x="30" y="57" font-size="10" fill="#75806d">{escape(subtitle)}</text><text x="30" y="76" font-size="10" fill="#75806d">{escape(port_text)}</text>{"".join(wires)}{"".join(symbols)}</g></svg>'
    return {'svg':svg,'width':width,'height':height,'pins':pins,'wire_paths':wire_paths,'layout':layout.model_dump(),'style':route_style,'labelled_nets':[nets[n].name for n in sorted(labelled)],
            'checks':{'pin_net_coverage':True,'expected_terminals':record.statistics.connection_count,'represented_terminals':len(pins),'distinct_device_ordinals':len(expected),'cross_net_wire_contacts':0},
            'warnings':warnings,'notice':'Connectivity follows the canonical netlist. Repeated net labels connect electrically; no operating-point, timing or performance simulation was performed.'}
