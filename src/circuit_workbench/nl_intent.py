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
    clauses=[c.strip() for c in re.split(r'[,;.!?]|\band\s+(?=(?:no|without|not|optional|preferably)\b)',text,flags=re.I) if c.strip()]
    wiring=[];presence=set();negative_wiring=[]
    for clause in clauses:
        if OPTIONAL.search(clause):continue
        # Negative device counts are handled by the literal-count parser, not
        # inverted into positive presence or wiring requirements here.
        if NEGATIVE.search(clause):
            if WIRING.search(clause):negative_wiring.append(clause)
            continue
        for entity,noun in NOUNS.items():
            for match in re.finditer(r'(?<!\w)(?:'+noun+r')(?!\w)',clause,re.I):
                # A compound modifier is not a discrete component: e.g.
                # diode-connected transistor, capacitor-coupled stage.
                if not re.match(r'\s*[-–]?\s*(?:connected|coupled|loaded|input|based)\b',clause[match.end():],re.I):presence.add(entity)
        if WIRING.search(clause):wiring.append(clause)
    words={'one':1,'two':2,'three':3,'four':4,'five':5}
    stage_counts={words.get(m.group(1).lower(),int(m.group(1)) if m.group(1).isdigit() else 0) for m in re.finditer(r'\b(\d+|one|two|three|four|five)[- ]+(?:gain\s+)?stages?\b(?!\s+(?:outputs?|inputs?|nodes?)\b)',text,re.I)}
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

def quote_patterns_valid(text,quote,patterns,audit):
    q=normalized(quote)
    if not q or q not in normalized(text) or not (audit['wiring'] or audit['signal_stage_count']):return False
    if not all(normalized(clause) in q for clause in audit['wiring']):return False
    if intent_audit(quote)['negative_wiring']:return False
    # Physical type mentions cannot be fulfilled by prose attached to a smaller
    # pattern (the original failure). All OR alternatives must be complete.
    types=intent_audit(quote)['presence']
    differential=bool(re.search(r'\bdifferential[- ]input\b|\bdifferential input\b',text,re.I))
    for pattern in patterns:
        if not connected(pattern) or (audit['signal_stage_count'] and len(pattern.signal_stages)!=audit['signal_stage_count']):return False
        if not all(any(d.type in GROUPS.get(e,[e]) for d in pattern.devices) for e in types):return False
        if differential and pattern.signal_stages:
            first=pattern.signal_stages[0]
            controls={edge.net for edge in pattern.edges if edge.device in first.devices and edge.terminal in {'gate','base'}}
            if len(first.devices)<2 or len(set(first.input_nets))<2 or not set(first.input_nets)<=controls:return False
    return True

def stage_interfaces(pattern):
    if not pattern.signal_stages:return
    from .nl_schema import NetCondition
    for net in pattern.signal_stages[0].input_nets+pattern.signal_stages[-1].output_nets:
        condition=NetCondition(net=net,condition='external')
        if condition not in pattern.net_conditions:pattern.net_conditions.append(condition)
    for stage in pattern.signal_stages:
        for a in stage.input_nets:
            for b in stage.output_nets:
                if (a,b) not in pattern.distinct_nets and (b,a) not in pattern.distinct_nets:pattern.distinct_nets.append((a,b))

def ground_structures(text,plan):
    audit=intent_audit(text);kept=[];complete=False
    for block in plan.required_blocks:
        if quote_patterns_valid(text,block.source_quote,block.alternatives,audit):
            for pattern in block.alternatives:stage_interfaces(pattern)
            kept.append(block);complete=True
        else:
            from .nl_schema import Hypothesis
            for pattern in block.alternatives:
                if len(plan.hypotheses)<5:plan.hypotheses.append(Hypothesis(interpretation='Ungrounded model block: '+block.name,pattern=pattern))
    plan.required_blocks=kept
    if plan.required_pattern:
        if quote_patterns_valid(text,plan.required_pattern_source,[plan.required_pattern],audit):
            stage_interfaces(plan.required_pattern);complete=True
        else:
            from .nl_schema import Hypothesis
            if len(plan.hypotheses)<5:plan.hypotheses.append(Hypothesis(interpretation='Ungrounded model wiring; not compulsory.',pattern=plan.required_pattern))
            plan.required_pattern=None;plan.required_pattern_source=''
    if (audit['wiring'] or audit['signal_stage_count']) and not complete:
        plan.clarification_questions.append('The converter did not provide a complete connected pattern for all explicit wiring clauses. Rephrase the connections or retry another converter; no weakened search was executed.')
    if audit['negative_wiring']:
        plan.clarification_questions.append('Negated wiring is not supported by the structural plan. Use an explicit absence Cypher query or rephrase positively.')
    if audit['ambiguous_stages'] or (audit['signal_stage_count'] is not None and not 1<=audit['signal_stage_count']<=5):plan.clarification_questions.append('Specify one signal-stage count between 1 and 5 for the bounded structural search.')
    return audit
