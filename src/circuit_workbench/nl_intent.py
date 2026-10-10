"""Generic, model-independent guards for explicit device/wiring requests.

This audits grammar and typed graphs, not named circuit functions or performance.
"""
import re
from .nl_compiler import GROUPS

NOUNS={'nmos':r'nmos(?:fet)?s?', 'pmos':r'pmos(?:fet)?s?',
       'npn':r'npns?', 'pnp':r'pnps?', 'mos':r'mos(?:fet)?s?',
       'bjt':r'(?:bjts?|bipolar transistors?)', 'transistor':r'transistors?',
       'resistor':r'resistors?', 'capacitor':r'capacitors?', 'inductor':r'inductors?',
       'diode':r'diodes?', 'voltage_source':r'independent voltage sources?',
       'current_source':r'independent current sources?'}
WIRING=re.compile(r'\b(?:connect(?:ed|ing|s)?|shar(?:e|ed|ing)|ti(?:e|ed)|feed(?:ing|s)?|driv(?:e|es|ing)|between|series|parallel|gate|drain|collector|emitter|bulk|cross[- ]coupled|diode[- ]connected)\b',re.I)
OPTIONAL=re.compile(r'\b(?:optional(?:ly)?|prefer(?:ably|red)?|nice to have|not required)\b',re.I)
NEGATIVE=re.compile(r"\b(?:without|no|not|exclude|excluding|avoid|don['’]t)\b",re.I)

def normalized(text):
    return ' '.join(text.casefold().split())

def intent_audit(text):
    clauses=[c.strip() for c in re.split(r'[,;.!?]|\band\s+(?=(?:an?\s+|the\s+)?(?:no|without|not|optional(?:ly)?|preferably)\b)',text,flags=re.I) if c.strip()]
    wiring=[];presence=set();negative_wiring=[];positive=[]
    for clause in clauses:
        if OPTIONAL.search(clause):continue
        # Negative device counts are handled by the literal-count parser, not
        # inverted into positive presence or wiring requirements here.
        if NEGATIVE.search(clause):
            if WIRING.search(clause):negative_wiring.append(clause)
            continue
        positive.append(clause)
        for entity,noun in NOUNS.items():
            for match in re.finditer(r'(?<!\w)(?:'+noun+r')(?!\w)',clause,re.I):
                # A compound modifier is not a discrete component: e.g.
                # diode-connected transistor, capacitor-coupled stage.
                if not re.match(r'\s*[-–]?\s*(?:connected|coupled|loaded|input|based)\b',clause[match.end():],re.I):presence.add(entity)
        if WIRING.search(clause) or re.search(r'\bexternal clock (?:net|node)\b',clause,re.I):wiring.append(clause)
    words={'one':1,'two':2,'three':3,'four':4,'five':5}
    stage_counts={words.get(m.group(1).lower(),int(m.group(1)) if m.group(1).isdigit() else 0) for m in re.finditer(r'\b(\d+|one|two|three|four|five)[- ]+(?:gain\s+)?stages?\b(?!\s+(?:outputs?|inputs?|nodes?)\b)','; '.join(positive),re.I)}
    return {'wiring':wiring,'presence':sorted(presence),'negative_wiring':negative_wiring,'signal_stage_count':next(iter(stage_counts)) if len(stage_counts)==1 else None,'ambiguous_stages':len(stage_counts)>1}

def connected(pattern):
    adjacency={('d',d.alias):set() for d in pattern.devices}
    for edge in pattern.edges:
        d,n=('d',edge.device),('n',edge.net)
        adjacency.setdefault(n,set()).add(d);adjacency[d].add(n)
    seen=set();todo=[next(iter(adjacency))]
    while todo:
        node=todo.pop()
        if node in seen:continue
        seen.add(node);todo+=list(adjacency[node]-seen)
    return len(seen)==len(adjacency)


def explicit_terminals_valid(pattern,clauses):
    """Check literal typed-terminal clauses, not named circuit recipes.

    Resolve high-confidence device/terminal references and simple `that gate`
    continuations. A quote cannot substitute for these physical connections.
    Unresolved explicit pronouns fail closed rather than guessing their owner.
    """
    terminal=r'gate|drain|source|bulk|base|collector|emitter'
    device=r'nmos(?:fet)?|pmos(?:fet)?|npn|pnp|mos(?:fet)?(?:\s+transistor)?|bjt|transistor'
    reference=re.compile(r'\b(?:(?P<entity>'+device+r")\s*(?:['’]s)?\s+(?P<terminal>"+terminal+r')|(?P<pronoun>that|its)\s+(?P<referred>'+terminal+r')|and\s+(?:the\s+)?(?P<bare>'+terminal+r'))\b',re.I)
    previous={}
    for clause in clauses:
        refs=[]
        for match in reference.finditer(clause):
            term=(match['terminal'] or match['referred'] or match['bare']).lower()
            if match['entity']:
                entity=match['entity'].lower().replace('fet','').split()[0]
            elif match['bare']:
                if not refs:continue
                entity=refs[-1][0]
            else:
                entity=previous.get(term)
                if entity is None:return False
            previous[term]=entity;refs.append((entity,term))
        if len(refs)<2:continue
        choices=[{e.net for e in pattern.edges if e.terminal==term and any(d.alias==e.device and d.type in GROUPS.get(entity,[entity]) for d in pattern.devices)} for entity,term in refs]
        if any(not nets for nets in choices):return False
        if re.search(r'\bbetween\b',clause,re.I):
            actors=[kind for kind in ('resistor','capacitor','inductor') if re.search(NOUNS[kind],clause,re.I)]
            if not actors:return False
            for kind in actors:
                matched=False
                for d in pattern.devices:
                    if d.type!=kind:continue
                    ends={e.terminal:e.net for e in pattern.edges if e.device==d.alias}
                    a,b=ends.get('p'),ends.get('n')
                    if a!=b and ((a in choices[0] and b in choices[1]) or (b in choices[0] and a in choices[1])):matched=True
                if not matched:return False
        elif re.search(r'\b(?:connected|tied|shared)\b',clause,re.I):
            if not set.intersection(*choices):return False
    return True

def quote_patterns_valid(text,quote,patterns,audit):
    q=normalized(quote)
    if not q or q not in normalized(text) or not (audit['wiring'] or audit['signal_stage_count']):return False
    if not all(normalized(clause) in q for clause in audit['wiring']):return False
    if intent_audit(quote)['negative_wiring']:return False
    # Physical type mentions cannot be fulfilled by prose attached to a smaller
    # pattern (the original failure). All OR alternatives must be complete.
    # Count/presence-only components are enforced independently on the whole
    # circuit. Only types mentioned in wiring clauses must occur in this
    # connected pattern; otherwise we invent an unrequested passive placement.
    # Counts/presence can share a sentence with a connected path. Their own
    # coordinated segment has no placement semantics unless it contains wiring
    # words (e.g. "and a capacitor BETWEEN the two outputs").
    segments=[]
    for clause in audit['wiring']:
        pieces=re.split(r'\b(?:and|with|having)\s+(?=(?:at least|at most|more than|fewer than|less than|exactly|a|an|\d+|one|two|three|four|five)\b)',clause,flags=re.I)
        segments.extend(p for p in pieces if WIRING.search(p))
    types=intent_audit('; '.join(segments))['presence']
    differential=bool(re.search(r'\bdifferential[- ]input\b|\bdifferential input\b',text,re.I))
    for pattern in patterns:
        if not connected(pattern) or (audit['signal_stage_count'] and len(pattern.signal_stages)!=audit['signal_stage_count']):return False
        if not all(any(d.type in GROUPS.get(e,[e]) for d in pattern.devices) for e in types):return False
        if not explicit_terminals_valid(pattern,audit['wiring']):return False
        if not explicit_net_roles_valid(pattern,audit['wiring']):return False
        if differential and pattern.signal_stages:
            first=pattern.signal_stages[0]
            controls={edge.net for edge in pattern.edges if edge.device in first.devices and edge.terminal in {'gate','base'}}
            if len(first.devices)<2 or len(set(first.input_nets))<2 or not set(first.input_nets)<=controls:return False
    return True


def explicit_net_roles_valid(pattern,clauses):
    """Do not replace explicit terminal/rail/interface clauses with disclaimers.

    Bounded literal phrasing only; naming conventions are not voltage proof.
    Conditions must be on the very net bound to the requested terminal.
    """
    roles=re.compile(r'\b(gate|drain|source|bulk|base|collector|emitter)\s+(?:connects?\s+to|is\s+connected\s+to|is\s+tied\s+to)\s+(?:an?\s+)?(?:distinct\s+)?(external\s+(?:input\s+|output\s+)?(?:net|node)|supply\s+rail|ground\s+rail|rail)\b',re.I)
    conditions={n:{c.condition for c in pattern.net_conditions if c.net==n} for n in pattern.nets}
    kinds={d.alias:d.type for d in pattern.devices}
    subjects={};subject=0;entity='transistor'
    for clause in clauses:
        if re.search(r'\bexternal clock (?:net|node)\b',clause,re.I):
            if not any(e.terminal in {'gate','base'} and {'external','clock_named'}<=conditions[e.net] for e in pattern.edges):return False
        previous_end=0
        for match in roles.finditer(clause):
            prefix=clause[previous_end:match.start()]
            previous_end=match.end()
            mentions=list(re.finditer(r'\b(nmos(?:fet)?|pmos(?:fet)?|npn|pnp|mosfet|mos|bjt|transistor)\b',prefix,re.I))
            if mentions:
                named=mentions[-1].group(1).lower().replace('fet','')
                if named!=entity or re.search(r'\b(?:another|different|second|separate)\b',prefix):subject+=1
                entity=named
            terminal,role=match.groups();role=role.lower()
            expected={'external'} if role.startswith('external') else {role.split()[0]}
            if re.search(r'\b(?:input|output)\b',role):expected.add('not_rail')
            choices={e.device for e in pattern.edges if e.terminal==terminal.lower() and expected<=conditions[e.net] and kinds[e.device] in GROUPS.get(entity,[entity])}
            # Bare/pronominal terminal continuations retain the subject: one
            # transistor's gate/drain/source cannot be distributed over others.
            subjects[subject]=subjects.get(subject,set(kinds)) & choices
    return all(subjects.values())

def stage_interfaces(pattern, linear=False):
    if not pattern.signal_stages:return
    from .nl_schema import NetCondition
    for net in pattern.signal_stages[0].input_nets+pattern.signal_stages[-1].output_nets:
        for kind in ('external', 'signal') if linear else ('external',):
            condition=NetCondition(net=net,condition=kind)
            if condition not in pattern.net_conditions:pattern.net_conditions.append(condition)
    if linear:
        first = set(pattern.signal_stages[0].devices)
        signal_nodes = {e.net for e in pattern.edges if e.device in first and e.terminal in {'drain','collector'}}
        signal_nodes.update(n for stage in pattern.signal_stages for n in stage.output_nets)
        for net in signal_nodes:
            condition=NetCondition(net=net,condition='not_rail')
            if condition not in pattern.net_conditions:pattern.net_conditions.append(condition)
        for net in pattern.signal_stages[-1].output_nets:
            condition=NetCondition(net=net,condition='linear_output')
            if condition not in pattern.net_conditions:pattern.net_conditions.append(condition)
    for stage in pattern.signal_stages:
        for a in stage.input_nets:
            for b in stage.output_nets:
                if (a,b) not in pattern.distinct_nets and (b,a) not in pattern.distinct_nets:pattern.distinct_nets.append((a,b))

def ground_structures(text,plan):
    audit=intent_audit(text);kept=[];complete=False
    linear=bool(re.search(r'\b(?:amplifier|op[- ]?amp|ota)\b',text,re.I))
    for block in plan.required_blocks:
        if quote_patterns_valid(text,block.source_quote,block.alternatives,audit):
            for pattern in block.alternatives:stage_interfaces(pattern,linear)
            kept.append(block);complete=True
        else:
            from .nl_schema import Hypothesis
            for pattern in block.alternatives:
                if len(plan.hypotheses)<5:plan.hypotheses.append(Hypothesis(interpretation='Ungrounded model block: '+block.name,pattern=pattern))
    plan.required_blocks=kept
    if plan.required_pattern:
        if quote_patterns_valid(text,plan.required_pattern_source,[plan.required_pattern],audit):
            stage_interfaces(plan.required_pattern,linear);complete=True
        else:
            from .nl_schema import Hypothesis
            if len(plan.hypotheses)<5:plan.hypotheses.append(Hypothesis(interpretation='Ungrounded model wiring; not compulsory.',pattern=plan.required_pattern))
            plan.required_pattern=None;plan.required_pattern_source=''
    if (audit['wiring'] or audit['signal_stage_count']) and not complete:
        plan.clarification_questions.append('The converter did not provide a complete connected pattern for all explicit wiring clauses. Rephrase the connections or retry another converter; no weakened search was executed.')
    # Audit the model's own alternatives; never generate a replacement graph.
    # Offering N-only and P-only chains silently imposes equality across stages
    # when the request never specified it, excluding ordinary N/P cascades.
    if linear and not re.search(r'\b(?:nmos|pmos|npn|pnp)\b|same[- ]polarity|same polarity',text,re.I):
        for block in kept:
            signatures=[]
            for pattern in block.alternatives:
                kinds={d.alias:d.type for d in pattern.devices}
                stage_kinds=[{kinds[a] for a in stage.devices} for stage in pattern.signal_stages]
                if len(stage_kinds)>=2 and all(len(k)==1 for k in stage_kinds):
                    signatures.append(tuple(next(iter(k)) for k in stage_kinds))
            for family in ({'nmos','pmos'},{'npn','pnp'}):
                within=[s for s in signatures if set(s)<=family]
                if len({k for s in within for k in s})==2 and all(len(set(s))==1 for s in within):
                    plan.clarification_questions.append('Polarity coverage is incomplete for the complete connected pattern: the alternatives lock every signal stage to the same polarity although the request does not. Include independent mixed-polarity stage alternatives; do not drop counts or wiring.')
                    break
    if audit['negative_wiring']:
        plan.clarification_questions.append('Negated wiring is not supported by the structural plan. Use an explicit absence Cypher query or rephrase positively.')
    if audit['ambiguous_stages'] or (audit['signal_stage_count'] is not None and not 1<=audit['signal_stage_count']<=5):plan.clarification_questions.append('Specify one signal-stage count between 1 and 5 for the bounded structural search.')
    return audit
