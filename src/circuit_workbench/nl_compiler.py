"""Compile validated patterns into owned, parameterized read-only Cypher."""
from .nl_schema import SearchPlan, GraphPattern, TERMINALS, RECIPROCAL_TYPES, NET_ROLE_NAMES

OPERATORS = {"eq": "=", "gt": ">", "ge": ">=", "lt": "<", "le": "<="}
GROUPS = {"transistor": ["nmos", "pmos", "npn", "pnp"], "mos": ["nmos", "pmos"], "bjt": ["npn", "pnp"]}


def compile_query(plan: SearchPlan, pattern: GraphPattern | None = None):
    # Revalidate even callers holding model objects (model_construct bypasses validation).
    plan = SearchPlan.model_validate(plan.model_dump())
    pattern = GraphPattern.model_validate(pattern.model_dump()) if pattern else None
    params, predicates = {}, []
    for i, count in enumerate(plan.count_constraints):
        key = f"count{i}"
        params[key] = count.value
        if count.entity in {"net", "port"}:
            expression = f"COUNT {{ (c)-[:HAS_{count.entity.upper()}]->() }}"
        else:
            selector = ""
            if count.entity != "device":
                params[f"kinds{i}"] = GROUPS.get(count.entity, [count.entity])
                selector = f" WHERE counted.canonical_type IN $kinds{i}"
            expression = f"COUNT {{ (c)-[:HAS_DEVICE]->(counted:Device){selector} }}"
        predicates.append(f"{expression} {OPERATORS[count.operator]} ${key}")
    for i, prop in enumerate(plan.property_constraints):
        key = f"property{i}"
        params[key] = prop.value
        predicates.append(f"c.{prop.field} = ${key}")
    if plan.required_pattern:
        clause, values = compile_pattern(plan.required_pattern, "hard")
        predicates.append(f"EXISTS {{ {clause} }}")
        params.update(values)
    if pattern:
        clause, values = compile_pattern(pattern, "")
        predicates.append(f"EXISTS {{ {clause} }}")
        params.update(values)
    for i, block in enumerate(plan.required_blocks):
        alternatives = []
        for j, alternative in enumerate(block.alternatives):
            clause, values = compile_pattern(alternative, f"block{i}alt{j}")
            alternatives.append(f"EXISTS {{ {clause} }}")
            params.update(values)
        predicates.append("(" + " OR ".join(alternatives) + ")")
    query = "MATCH (c:Circuit)"
    if predicates:
        query += "\nWHERE " + "\nAND ".join(predicates)
    query += "\nRETURN c.id AS circuit_id ORDER BY circuit_id LIMIT 10001"
    return query, params


def compile_pattern(pattern, prefix):
    devices = {d.alias: f"{prefix}d{i}" for i, d in enumerate(pattern.devices)}
    nets = {n: f"{prefix}n{i}" for i, n in enumerate(pattern.nets)}
    params={f'{prefix}type{i}':d.type for i,d in enumerate(pattern.devices)}
    for i,e in enumerate(pattern.edges):params[f'{prefix}terminal{i}']=e.terminal
    index={d.alias:i for i,d in enumerate(pattern.devices)}
    edges={d.alias:[(i,e) for i,e in enumerate(pattern.edges) if e.device==d.alias] for d in pattern.devices}
    remaining=list(pattern.devices);bound_devices=set();bound_nets=set();clauses=[];emitted=set()
    while remaining:
        linked=[d for d in remaining if any(e.net in bound_nets for _,e in edges[d.alias])]
        # Registry arity gives a deterministic small-anchor preference without
        # circuit-family recipes. Subsequent nodes traverse already bound nets.
        device=min(linked or remaining,key=lambda d:(len(TERMINALS[d.type]),-len(edges[d.alias]),index[d.alias]))
        remaining.remove(device);variable=devices[device.alias];typekey=f'{prefix}type{index[device.alias]}'
        phase=[];where=[]
        if not linked:phase.append(f'(c)-[:HAS_DEVICE]->({variable}:Device {{canonical_type: ${typekey}}})')
        else:where.append(f'EXISTS {{ (c)-[:HAS_DEVICE]->({variable}) }}')
        ordered=sorted(edges[device.alias],key=lambda pair:pair[1].net not in bound_nets)
        for i,edge in ordered:
            if device.type in RECIPROCAL_TYPES:
                rel=f'{prefix}edge{i}'
                phase.append(f'({variable}:Device {{canonical_type: ${typekey}}})-[{rel}:CONNECTED_TO]->({nets[edge.net]}:Net)')
                params[f'{prefix}passive{index[device.alias]}']=['p','n']
                where.append(f'{rel}.terminal IN ${prefix}passive{index[device.alias]}')
            else:phase.append(f'({variable}:Device {{canonical_type: ${typekey}}})-[:CONNECTED_TO {{terminal: ${prefix}terminal{i}}}]->({nets[edge.net]}:Net)')
            if edge.net not in bound_nets:where.append(f'EXISTS {{ (c)-[:HAS_NET]->({nets[edge.net]}) }}')
            bound_nets.add(edge.net)
        bound_devices.add(device.alias)
        if device.type in RECIPROCAL_TYPES:
            relations=[f'{prefix}edge{i}' for i,_ in ordered]
            where += [f'{a} <> {b}' for i,a in enumerate(relations) for b in relations[i+1:]]
        names=[devices[d.alias] for d in pattern.devices if d.alias in bound_devices]
        where += [f'{a} <> {b}' for i,a in enumerate(names) for b in names[i+1:]]
        named_nets=[nets[n] for n in pattern.nets if n in bound_nets]
        where += [f'{a} <> {b}' for i,a in enumerate(named_nets) for b in named_nets[i+1:]]
        for i,condition in enumerate(pattern.net_conditions):
            if condition.net not in bound_nets:continue
            if condition.condition=='external':where.append(f'{nets[condition.net]}.is_external = true')
            else:
                key=f'{prefix}rails{i}'
                params[key]=list(NET_ROLE_NAMES['rail' if condition.condition=='not_rail' else condition.condition])
                negation='NOT ' if condition.condition=='not_rail' else ''
                where.append(f'{negation}toUpper({nets[condition.net]}.name) IN ${key}')
        scope=['c']+names+[nets[n] for n in pattern.nets if n in bound_nets]
        if device.type in RECIPROCAL_TYPES:scope+=relations
        # DISTINCT is a semantics-preserving horizon inside EXISTS: duplicate
        # bindings cannot change existence, but planning no longer enumerates
        # every possible join ordering of the entire multi-device graph at once.
        clause='MATCH '+',\n'.join(phase)+'\nWITH DISTINCT '+', '.join(scope)
        fresh=[w for w in dict.fromkeys(where) if w not in emitted];emitted.update(fresh)
        if fresh:clause+=' WHERE '+' AND '.join(fresh)
        clauses.append(clause)
    for i,port in enumerate(pattern.ports):
        key=f'{prefix}port{i}';params[key]=port.name
        clauses.append(f'MATCH (c)-[:HAS_PORT]->({prefix}p{i}:Port {{name: ${key}}})-[:MAPS_TO]->({nets[port.net]})')
    return '\n'.join(clauses)+'\nRETURN 1',params
