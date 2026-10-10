"""Composable bounded analog wiring grammar, never corpus answers.

Unfamiliar vocabulary/connections are declined for the selected converter. Rules
establish conservative candidate structure, not simulated electrical behavior.
"""
import itertools
import re
from .nl_core import ground_plan, motif_qualifiers
from .nl_intent import intent_audit, stage_interfaces, OPTIONAL
from .nl_schema import GraphPattern, RequiredBlock, SearchPlan, Hypothesis, Unverified

ACTIVE = ('nmos', 'pmos', 'npn', 'pnp')
MOS = ('nmos', 'pmos')
VOCABULARY = set('''find show retrieve search get list me all some any candidate candidates
circuit circuits an a the with containing contains includes include using use has having
of for from in as to and or but than at least most more fewer less no without exactly
one two three four five six seven eight nine ten zero stage stages input inputs output
outputs differential single ended analog amplifier amplifiers amp amps op opamp ota
operational miller compensated compensation capacitor capacitors cap caps resistor
resistors res inductor inductors transistor transistors trans device devices mos mosfet
mosfets nmos nmosfet pmos pmosfet npn pnp bjt bipolar current mirror mirrors load loading
reference diode connected cascoded cascode branch branches upper lower separate distinct
common source emitter gain gains feeding feeds feed driving drives drive each next first
second third final pair pairs sequential sequence sequentially between through own node nodes net
nets tail reset resets clock clocks clocked external controlling controlled controls control
regenerative cross coupled latch latches comparator comparators positive feedback could
provide that whose must its their connect connects connected gate drain source base collector
emitter supply ground rail rails is be not require required requirements optional optionally
preferably preferred prefer architecture also dc ac phase margin bandwidth power voltage
range frequency db mhz khz hz ghz degrees degree v volt volts mw uw minimum maximum above
below over under atleast upto total internal degeneration degenerated resistive resistively
followers follower including count counts numbered structure topology please would want
need s per'''.split())


def kinds(text, aliases, default=ACTIVE):
    wanted = motif_qualifiers(aliases, text)
    allowed = set()
    for name in wanted:
        allowed.update({'mos': set(MOS), 'bjt': {'npn', 'pnp'}}.get(name, {name}))
    return tuple(k for k in default if not allowed or k in allowed)


def contacts(kind):
    return ('gate', 'drain', 'source') if kind in MOS else ('base', 'collector', 'emitter')


def graph(devices, edges, conditions=(), stages=()):
    return GraphPattern(devices=[{'alias': a, 'type': t} for a, t in devices],
        nets=list(dict.fromkeys(n for _, _, n in edges)),
        edges=[{'device': d, 'terminal': t, 'net': n} for d, t, n in edges],
        net_conditions=[{'net': n, 'condition': c} for n, c in dict.fromkeys(conditions)],
        signal_stages=list(stages))


def pair_parts(kind, capacitive=False, degenerated=False):
    control, out, source = contacts(kind)
    devices = [('left', kind), ('right', kind)]
    edges = [('left', control, 'gate_a' if capacitive else 'in_a'),
             ('right', control, 'gate_b' if capacitive else 'in_b'),
             ('left', out, 'first'), ('right', out, 'other'),
             ('left', source, 'source_a' if degenerated else 'tail'),
             ('right', source, 'source_b' if degenerated else 'tail')]
    conditions = [('in_a', 'external'), ('in_b', 'external'), ('in_a', 'signal'),
                  ('in_b', 'signal'), ('tail', 'not_rail'), ('first', 'not_rail'), ('other', 'not_rail')]
    if capacitive:
        devices += [('input_cap_a', 'capacitor'), ('input_cap_b', 'capacitor')]
        edges += [('input_cap_a', 'p', 'in_a'), ('input_cap_a', 'n', 'gate_a'),
                  ('input_cap_b', 'p', 'in_b'), ('input_cap_b', 'n', 'gate_b')]
    if degenerated:
        devices += [('degeneration_a', 'resistor'), ('degeneration_b', 'resistor')]
        edges += [('degeneration_a', 'p', 'source_a'), ('degeneration_a', 'n', 'tail'),
                  ('degeneration_b', 'p', 'source_b'), ('degeneration_b', 'n', 'tail')]
    return devices, edges, conditions


def stage_patterns(text, count, compensation=False, mirror_load=False):
    inputs = kinds(text, ('input pair', 'differential input pair', 'input stage', 'differential input stage'))
    outputs = kinds(text, ('common-source gain stage', 'common-source output stage', 'output stage', 'gain stage'))
    if re.search(r'common[- ]source', text):
        outputs = tuple(t for t in outputs if t in MOS)
    elif re.search(r'common[- ]emitter', text):
        outputs = tuple(t for t in outputs if t not in MOS)
    variants = []
    for family in itertools.product(inputs, *([outputs] * (count - 1))):
        if len(variants) >= 16:
            return None  # no silently capped polarity coverage
        devices, edges, conditions = pair_parts(family[0])
        stages = [{'devices': ['left', 'right'], 'input_nets': ['in_a', 'in_b'], 'output_nets': ['first']}]
        previous = 'first'
        for i, kind in enumerate(family[1:], 2):
            alias, net = f'gain{i}', 'out' if i == count else f'stage{i}'
            control, output, _ = contacts(kind)
            devices.append((alias, kind))
            edges += [(alias, control, previous), (alias, output, net)]
            stages.append({'devices': [alias], 'input_nets': [previous], 'output_nets': [net]})
            previous = net
        if mirror_load:
            load_types = kinds(text, ('current-mirror load', 'current mirror load', 'mirror load', 'current mirror', 'current-mirror'))
            if len(load_types) != 1:
                return None
            control, output, source = contacts(load_types[0])
            devices += [('load_ref', load_types[0]), ('load_out', load_types[0])]
            edges += [('load_ref', control, 'other'), ('load_ref', output, 'other'),
                      ('load_ref', source, 'load_source'), ('load_out', control, 'other'),
                      ('load_out', output, 'first'), ('load_out', source, 'load_source')]
        if compensation:
            devices.append(('compensation', 'capacitor'))
            edges += [('compensation', 'p', 'first'), ('compensation', 'n', previous)]
        pattern = graph(devices, edges, conditions, stages)
        stage_interfaces(pattern, linear=True)
        variants.append(pattern)
    return variants


def mirror_patterns(text, cascoded):
    variants = []
    for kind in kinds(text, ('current mirror', 'current-mirror', 'mirror')):
        control, output, source = contacts(kind)
        devices = [('reference', kind), ('copy', kind)]
        edges = [('reference', control, 'ref'), ('reference', output, 'ref'),
                 ('reference', source, 'common'), ('copy', control, 'ref'), ('copy', source, 'common'),
                 ('copy', output, 'middle' if cascoded else 'out')]
        if cascoded:
            devices.append(('cascode', kind))
            edges += [('cascode', source, 'middle'), ('cascode', output, 'out')]
        variants.append(graph(devices, edges))
    return variants


def comparator_patterns(text, clocked, output_stage):
    variants = []
    pair_types = kinds(text, ('input pair', 'differential input pair'), MOS if clocked else ACTIVE)
    latch_types = kinds(text, ('loading', 'load', 'latch', 'cross-coupled latch'), MOS)
    if re.search(r'cross[- ]coupled\s+pmos', text):
        latch_types = ('pmos',)
    gains = kinds(text, ('output stage',), ACTIVE) if output_stage else (None,)
    for input_type, latch_type, gain in itertools.product(pair_types, latch_types, gains):
        if not clocked:controls=(None,)
        elif 'tail' in text and 'reset' in text:
            controls=('tail','reset') if re.search(r'tail\b[^.;]{0,100}\bor\b[^.;]{0,60}\breset',text) else ('both',)
        elif 'tail' in text:controls=('tail',)
        elif 'reset' in text:controls=('reset',)
        else:controls=('tail','reset')
        for location, capacitive in itertools.product(controls, (False, True) if clocked else (False,)):
            if len(variants) >= 16:
                return None
            devices, edges, conditions = pair_parts(input_type, capacitive=capacitive)
            devices += [('latch_a', latch_type), ('latch_b', latch_type)]
            edges += [('latch_a', 'gate', 'other'), ('latch_a', 'drain', 'first'),
                      ('latch_b', 'gate', 'first'), ('latch_b', 'drain', 'other')]
            if gain:
                control, out, _ = contacts(gain)
                devices.append(('output', gain))
                edges += [('output', control, 'first'), ('output', out, 'out')]
                conditions += [('out', 'external'), ('out', 'signal')]
            if location:
                conditions += [('clock', 'external'), ('clock', 'clock_named')]
                if location in {'tail','both'}:
                    devices.append(('clock_tail',input_type))
                    edges += [('clock_tail','gate','clock'),('clock_tail','drain','tail')]
                if location in {'reset','both'}:
                    for alias,net in [('reset_a','first'),('reset_b','other')]:
                        devices.append((alias,latch_type))
                        edges += [(alias,'gate','clock'),(alias,'drain',net),(alias,'source','reset_rail')]
                    conditions.append(('reset_rail', 'rail'))
            variants.append(graph(devices, edges, conditions))
    return variants


def deterministic_plan(text):
    """Grounded common request, or None for the selected model pathway."""
    t = text.lower()
    if any(w not in VOCABULARY for w in re.findall(r'[a-zA-Z]+', t)):
        return None
    if re.search(r'\b(?:folded|telescopic|single[- ]ended|fully[- ]differential)\b', t):
        return None
    audit = intent_audit(text)
    if audit['negative_wiring']:
        return None
    family = bool(re.search(r'\b(?:amplifiers?|op[- ]?amps?|opamps?|ota|operational amplifier)\b', t))
    clocked = bool(re.search(r'\bclocked\s+comparator|\bexternal clock\b', t))
    count = audit['signal_stage_count']
    mandatory_text=' '.join(c for c in re.split(r'[,;.!?]',t) if not OPTIONAL.search(c))
    patterns, name, covered_pair = None, '', False
    bare_terminal = re.sub(r'common[- ](?:source|emitter)', '', t)
    if family and count is not None:
        if not 2 <= count <= 3 or re.search(r'\b(?:gate|drain|source|base|collector|emitter|connect\w*|shared|tied|cascode|cross[- ]coupled|supply|rail)\b', bare_terminal):
            return None
        capacitor_between = bool(re.search(r'capacitor\s+between\b', mandatory_text))
        stage_endpoints = bool(re.search(r'between the (?:(?:two|2) )?stage outputs|between (?:the )?first[- ]stage output and (?:the )?(?:final|second[- ]stage) output', mandatory_text))
        if capacitor_between and not stage_endpoints:
            return None
        compensation = bool(stage_endpoints or re.search(r'miller[- ]compensat', mandatory_text))
        if 'between' in mandatory_text and not compensation:
            return None
        patterns = stage_patterns(t, count, compensation, bool(re.search(r'current[- ]mirror load|current mirror load', t)))
        name, covered_pair = f'{count}-stage differential-input signal path', True
    elif 'comparator' in t and (clocked or re.search(r'cross[- ]coupled|regenerative', t)):
        if re.search(r'\b(?:gate|drain|source|base|collector|emitter|connect\w*|between|shared|tied)\b', t) or not re.search(r'\bdifferential (?:input )?pair\b', t):
            return None
        patterns = comparator_patterns(t, clocked, bool(re.search(r'\boutput stage\b', t)))
        name, covered_pair = 'Connected analog input / regenerative decision path', True
    elif re.search(r'source[- ]follower', t):
        clauses = re.split(r'[,;.!?]|\band\b', re.sub(r'source[- ]followers?', '', t))
        for clause in clauses:
            terminals = re.findall(r'\b(?:gate|drain|source|base|collector|emitter)\b', clause)
            if not terminals:
                if re.search(r'between|connect\w*|shared|tied', clause):
                    return None
                continue
            if len(terminals) != 1 or not re.search({
                'gate': r'gate connects? to (?:an? )?external input net',
                'drain': r'drain connects? to (?:an? )?(?:supply|ground) rail',
                'source': r'source connects? to (?:an? )?(?:distinct )?external output net',
            }.get(terminals[0], r'(?!)'), clause):
                return None
        patterns = [graph([('follower', kind)], [('follower', 'gate', 'in'), ('follower', 'drain', 'rail'), ('follower', 'source', 'out')],
            [('in', 'external'), ('in', 'signal'), ('in', 'not_rail'), ('out', 'external'), ('out', 'signal'), ('out', 'not_rail'),
             ('rail', 'ground' if 'ground rail' in t else 'supply' if 'supply rail' in t else 'rail')])
            for kind in kinds(t, ('source follower', 'source-follower'), MOS)]
        name = 'Source-follower terminal path'
    elif re.search(r'current[- ]mirror|current mirror', t) and not family:
        terminal_mentions=re.findall(r'\b(?:gate|drain|source|base|collector|emitter)\b',t)
        conventional_stack=bool(re.search(r'upper\b[^.]{0,60}\bsource\b[^.]{0,60}\blower\b[^.]{0,60}\bdrain',t))
        if terminal_mentions and not (terminal_mentions==['source','drain'] and conventional_stack):
            return None
        patterns = mirror_patterns(t, bool(re.search(r'cascode|cascoded', t)))
        name = 'Diode-reference mirror and output path'
    elif family and re.search(r'\bdifferential\b|\binput pair\b', t):
        degenerated = bool(re.search(r'source[- ]degenerat', mandatory_text))
        if re.search(r'\b(?:gate|drain|base|collector|emitter|between|shared|tied)\b', t):
            return None
        if not degenerated and re.search(r'\bconnect\w*|\bthrough\b', t):
            return None
        patterns = [graph(*pair_parts(k, degenerated=degenerated)) for k in kinds(t, ('input pair', 'differential input pair'))]
        name, covered_pair = 'Analog differential input pair', True
    if not patterns:
        return None
    unverified = [Unverified(requirement='Circuit function and operating-point behavior',
        reason='Shared rules establish candidate terminal structure, not electrical operation.',
        evidence_needed='Source review and appropriate simulation with device models.')]
    for spec in ('gain', 'phase margin', 'bandwidth', 'power', 'supply range'):
        if spec in t and (spec != 'gain' or re.search(r'\bgain\b(?! stages?\b)', t)):
            unverified.append(Unverified(requirement=spec + ': ' + text,
                reason='This requirement cannot be measured from connectivity alone.',
                evidence_needed='Measured annotations or operating-condition/device-model simulation.'))
    structural = bool(audit['wiring'] or count)
    raw = SearchPlan(requested_function='clocked comparator' if clocked else 'comparator' if 'comparator' in t else
        'differential amplifier' if family and not count else f'{count}-stage amplifier' if family else name,
        requested_topology=name, unverified_requirements=unverified)
    if structural:
        raw.required_blocks = [RequiredBlock(name=name, source_quote=text, alternatives=patterns)]
    plan = ground_plan(text, raw)
    if any('complete connected pattern' in q for q in plan.clarification_questions):
        return None
    if not structural:
        plan.required_blocks.insert(0, RequiredBlock(name=name, alternatives=patterns))
    if covered_pair:
        plan.required_blocks = [b for b in plan.required_blocks if b.source_quote or b.name == name or
                                not re.search(r'differential.*pair', b.name, re.I)]
    if family and not count and re.search(r'prefer\w*.*(?:two|2)[- ](?:stage|stages)', t):
        preferred = stage_patterns(t, 2) or []
        plan.hypotheses = [Hypothesis(interpretation='Preferred two-stage connected path; not a hard stage count.', pattern=p)
                           for p in preferred]
    elif family and not count and re.search(r'source[- ]degenerat', t) and not re.search(r'source[- ]degenerat', mandatory_text):
        plan.hypotheses = [Hypothesis(interpretation='Optional source degeneration; not a hard resistor requirement.',
            pattern=graph(*pair_parts(k, degenerated=True))) for k in kinds(t, ('input pair', 'differential input pair'))]
    return SearchPlan.model_validate(plan.model_dump())
