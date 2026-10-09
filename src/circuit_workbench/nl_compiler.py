"""Compile validated patterns into owned, parameterized read-only Cypher."""
from .nl_schema import SearchPlan, GraphPattern

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
    matches, where, params = [], [], {}
    for i, d in enumerate(pattern.devices):
        key = f"{prefix}type{i}"
        params[key] = d.type
        if i == 0:
            matches.append(f"(c)-[:HAS_DEVICE]->({devices[d.alias]}:Device {{canonical_type: ${key}}})")
        else:
            where.append(f"{devices[d.alias]}.canonical_type = ${key}")
            where.append(f"EXISTS {{ (c)-[:HAS_DEVICE]->({devices[d.alias]}) }}")
    for n in nets.values():
        where.append(f"EXISTS {{ (c)-[:HAS_NET]->({n}) }}")
    for i, e in enumerate(pattern.edges):
        key = f"{prefix}terminal{i}"
        params[key] = e.terminal
        matches.append(f"({devices[e.device]}:Device)-[:CONNECTED_TO {{terminal: ${key}}}]->({nets[e.net]}:Net)")
    for i, p in enumerate(pattern.ports):
        key = f"{prefix}port{i}"
        params[key] = p.name
        matches.append(f"(c)-[:HAS_PORT]->({prefix}p{i}:Port {{name: ${key}}})-[:MAPS_TO]->({nets[p.net]})")
    names = list(devices.values())
    where += [f"{a} <> {b}" for i, a in enumerate(names) for b in names[i+1:]]
    where += [f"{nets[a]} <> {nets[b]}" for a, b in pattern.distinct_nets]
    for i, condition in enumerate(pattern.net_conditions):
        if condition.condition == "external":
            where.append(f"{nets[condition.net]}.is_external = true")
        else:
            key=f"{prefix}rails{i}"
            params[key]=["VDD","VCC","VDD!","VCC!","VSS","VEE","GND","0","GND!","VSS!"]
            where.append(f"NOT toUpper({nets[condition.net]}.name) IN ${key}")
    clause = "MATCH " + ",\n".join(matches)
    if where:
        clause += " WHERE " + " AND ".join(where)
    return clause, params
