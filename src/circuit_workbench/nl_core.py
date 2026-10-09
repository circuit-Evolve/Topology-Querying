"""Model-independent interpretation of explicit counts and curated wiring seeds.

Rules are deliberately bounded. Unknown electronics stay hypotheses, not guessed
hard filters. The JSON rulebook is loaded by all model adapters via the service.
"""
import json
from pathlib import Path
import re
from functools import lru_cache
from .nl_schema import CountConstraint, SearchPlan, Hypothesis, GraphPattern, RequiredBlock, Unverified

RULEBOOK = Path(__file__).with_name("search-rulebook.json")
WORDS = {"zero":0,"one":1,"two":2,"three":3,"four":4,"five":5,"six":6,"seven":7,"eight":8,"nine":9,"ten":10}
NUMBER = r"(?:\d+|zero|one|two|three|four|five|six|seven|eight|nine|ten)"
ENTITIES = {
    "mos":r"mos(?:fet)?s?(?:\s+transistors?)?",
    "nmos":r"nmos(?:fet)?s?(?:\s+transistors?)?",
    "pmos":r"pmos(?:fet)?s?(?:\s+transistors?)?",
    "bjt":r"(?:bipolar\s+transistors?|bjts?)",
    "npn":r"npns?(?:\s+transistors?)?", "pnp":r"pnps?(?:\s+transistors?)?",
    "transistor":r"(?:transistors?|trans)","resistor":r"(?:resistors?|res)",
    "capacitor":r"(?:capacitors?|caps)","inductor":r"inductors?", "diode":r"diodes?",
    "device":r"(?:devices?|components?)", "port":r"(?:declared\s+)?ports?", "net":r"nets?",
    "current_source":r"independent\s+current\s+sources?", "voltage_source":r"independent\s+voltage\s+sources?",
}
COMPARISONS = {"more than":"gt","greater than":"gt","over":"gt",">":"gt","at least":"ge","minimum of":"ge",">=":"ge", "fewer than":"lt","less than":"lt","under":"lt","<":"lt","at most":"le","no more than":"le","maximum of":"le","<=":"le","exactly":"eq","equal to":"eq","=":"eq"}


def parse_counts(text):
    lowered = text.lower()
    matches, questions = [], []
    if re.search(rf"\b{NUMBER}\s+(?:current|voltage)\s+sources?\b",lowered):
        questions.append("Specify independent SPICE sources explicitly; transistor current-source roles cannot be counted as independent source devices.")
    comparison = "|".join(re.escape(c) for c in sorted(COMPARISONS,key=len,reverse=True))
    number = lambda s: WORDS[s] if s in WORDS else int(s)
    for entity, noun in ENTITIES.items():
        range_pattern = rf"\b(?:between\s+({NUMBER})\s+and\s+({NUMBER})|({NUMBER})\s*(?:to|–|-)\s*({NUMBER}))\s+({noun})\b"
        ranges = []
        for m in re.finditer(range_pattern, lowered):
            lo,hi = (m.group(1),m.group(2)) if m.group(1) else (m.group(3),m.group(4))
            matches += [(m.start(),entity,"ge",number(lo)),(m.start()+.01,entity,"le",number(hi))]
            ranges.append(m.span())
        for m in re.finditer(rf"(?<![\w.])(?:(?P<op>{comparison})\s*)?(?P<n>{NUMBER})\s+(?:{noun})\b", lowered):
            if any(a<=m.start()<b for a,b in ranges):
                continue
            # 'not more than' reverses semantics; require an explicit supported phrase.
            if re.search(r"\bnot\s*$", lowered[max(0,m.start()-5):m.start()]):
                questions.append("Rephrase negated counts using at most/at least/fewer than/more than.")
                continue
            matches.append((m.start(),entity,COMPARISONS.get(m.group("op"),"eq"),number(m.group("n"))))
        for m in re.finditer(rf"\b(?:no|without\s+any|without|zero)\s+(?:{noun})\b",lowered):
            matches.append((m.start(),entity,"eq",0))
        if re.search(rf"\b(?:x|y|n)\s+(?:{noun})\b",lowered):
            questions.append(f"Provide a numeric {entity} count instead of a placeholder.")
    # Detect overlapping total-count matches inside '10 MOS transistors'. The
    # longer noun consumed the number first; same span belongs to one entity.
    ordered = sorted(matches, key=lambda m:m[0])
    counts, seen = [], set()
    for _,entity,op,value in ordered:
        if (entity,op,value) not in seen:
            counts.append(CountConstraint(entity=entity,operator=op,value=value));seen.add((entity,op,value))
    for entity in {c.entity for c in counts}:
        lower,upper=0,100000
        for c in (c for c in counts if c.entity==entity):
            if c.operator=="eq":lower=max(lower,c.value);upper=min(upper,c.value)
            if c.operator in {"gt","ge"}:lower=max(lower,c.value+(c.operator=="gt"))
            if c.operator in {"lt","le"}:upper=min(upper,c.value-(c.operator=="lt"))
        if lower>upper:
            questions.append(f"The {entity} count requirements contradict each other.")
    if any(min((m[0] for m in matches),default=0)<m.start()<max((v[0] for v in matches),default=0) for m in re.finditer(r"\bor\b",lowered)):
        questions.append("Specify whether the count requirements must all hold; OR alternatives need separate searches in V1.")
    return counts, list(dict.fromkeys(questions))


@lru_cache(maxsize=1)
def load_rulebook():
    book = json.loads(RULEBOOK.read_text())
    if book["version"] != "1.0":
        raise ValueError("Unsupported electrical rulebook version.")
    for primitive in book["primitives"]:
        for pattern in primitive.get("patterns",[]):
            if primitive["id"] in {"mos_diff_pair","regenerative_comparator"}:
                pattern["net_conditions"]=[{"net":"tail","condition":"not_rail"}]
            GraphPattern.model_validate(pattern)
    return book


def alias_matches(alias,text):
    return bool(re.search(r"(?<!\w)"+re.escape(alias)+r"s?(?!\w)",text))


def relevant_rules(text):
    book=load_rulebook()
    normalized = text.lower()
    families=[f for f in book["families"] if any(alias_matches(alias,normalized) for alias in f["aliases"])]
    ids={p for f in families for p in f.get("candidate_primitives",[])}
    primitives=[p for p in book["primitives"] if p["id"] in ids or any(alias_matches(a,normalized) for a in p["aliases"])]
    return {"version":book["version"],"policy":book["policy"],"device_contracts":book["device_contracts"],
            "families":families,"primitives":primitives,"interpretation_examples":book["interpretation_examples"]}


def ground_plan(text, plan):
    plan=SearchPlan.model_validate(plan.model_dump())
    counts,questions=parse_counts(text)
    recognized={c.entity for c in counts}
    for c in plan.count_constraints:
        if c.entity not in recognized:
            questions.append(f"Cannot independently ground the {c.entity} count. Rephrase using e.g. 'at least 2 {c.entity}' with numerals and a supported device name.")
    plan.count_constraints=counts
    plan.clarification_questions=list(dict.fromkeys(plan.clarification_questions+questions))
    references=re.findall(r'\b(?:similar\s+to|like|neighbou?rs\s+of)\s+(?:circuit\s+)?((?:analoggenie:)?\d+|uploaded:[a-f0-9-]+)\b',text.lower())
    if references:
        normalized_refs={('analoggenie:'+r if r.isdigit() else r) for r in references}
        if len(normalized_refs)>1:plan.clarification_questions.append('Choose one reference circuit for this search.')
        else:plan.reference_id=next(iter(normalized_refs))
    else:plan.reference_id=''
    if not re.search(r'\b(?:annotated|annotations?|metadata|labelled|labeled|tagged)\b',text.lower()):
        properties=[]
        for prop in plan.property_constraints:
            if prop.field=='dataset':
                if str(prop.value).casefold() not in text.casefold():
                    plan.clarification_questions.append('Confirm the dataset filter; it was not explicit in your request.')
                else:properties.append(prop)
            else:
                plan.unverified_requirements.append(Unverified(requirement=f'{prop.field}: {prop.value}',reason='This is not an explicit request for stored annotations. Sparse annotation fields cannot be used as assumed circuit facts.',evidence_needed='Reviewed annotations or independent functional evidence.'))
        plan.property_constraints=properties
    if plan.required_pattern and not re.search(r'\b(?:connected|shared|tied|diode|stack|cross[- ]coupled|series|parallel)\b',text.lower()):
        plan.hypotheses=([Hypothesis(interpretation='Model-inferred wiring; not explicitly required by the user.',pattern=plan.required_pattern)]+plan.hypotheses)[:5]
        plan.required_pattern=None
    # Identical user text yields identical semantic input, irrespective of provider paraphrasing.
    plan.semantic_text=text[:2000]
    if RULEBOOK.exists():
        book=load_rulebook()
        normalized=text.lower()
        if re.search(r"\bcomparator\b",normalized):
            primitive=next(p for p in book["primitives"] if p["id"]=="regenerative_comparator")
            preferred=[Hypothesis(interpretation=primitive["description"]+" (curated composite; function still unverified)",pattern=GraphPattern.model_validate(p)) for p in primitive["patterns"]]
            plan.hypotheses=(preferred+plan.hypotheses)[:5]
        for identifier in dict.fromkeys(plan.hypothesis_rules):
            primitive=next(p for p in book["primitives"] if p["id"]==identifier)
            for pattern in primitive.get("patterns",[]):
                hypothesis=Hypothesis(interpretation=primitive["description"]+" (curated rule)",pattern=GraphPattern.model_validate(pattern))
                if hypothesis not in plan.hypotheses and len(plan.hypotheses)<5:
                    plan.hypotheses.append(hypothesis)
        # Only explicit primitive requests use fixed queries. A generic comparator
        # needs a combination/context; no single fixed motif certifies its function.
        direct=[p for p in book["primitives"] if p.get("deterministic_seed") and any(alias_matches(a,normalized) for a in p["aliases"])]
        if any(p["id"]=="mos_mirror" for p in direct) and re.search(r"\b(?:bjt|npn|pnp|bipolar)\b",normalized):
            direct=[p for p in direct if p["id"]!="mos_mirror"]+[next(p for p in book["primitives"] if p["id"]=="bjt_mirror")]
        parents=[f for f in book["families"] if f["id"]!="current_mirror" and any(alias_matches(a,normalized) for a in f["aliases"])]
        for primitive in direct:
            patterns=primitive.get("patterns",[])
            generic_mirror=primitive['id']=='mos_mirror' and not re.search(r'\b(?:nmos|pmos|mos|mosfet|bjt|bipolar|npn|pnp)\b',normalized)
            if generic_mirror:
                patterns=patterns+next(p for p in book['primitives'] if p['id']=='bjt_mirror')['patterns']
            for kind in ("nmos","pmos","npn","pnp"):
                if re.search(r"\b"+kind+r"\b",normalized):
                    patterns=[p for p in patterns if any(d["type"]==kind for d in p["devices"])]
                    break
            contains=any(re.search(r"\b(?:with|containing|contains|includes?|using|has|having)\b[^.;]{0,60}"+re.escape(a),normalized) for a in primitive["aliases"])
            if parents or contains:
                if patterns:
                    block=RequiredBlock(name='Current mirror' if generic_mirror else primitive["name"],alternatives=[GraphPattern.model_validate(p) for p in patterns[:5]])
                    plan.required_blocks=[b for b in plan.required_blocks if b.name!=block.name and not ('mirror' in b.name.lower() and 'mirror' in block.name.lower())]+[block]
                # Leave parent-function hypotheses intact: mirror containment is
                # eligibility evidence, not a replacement for parent function.
            elif len(direct)==1:
                plan.hypotheses=[Hypothesis(interpretation=primitive["description"]+" (curated wiring candidate; not functional proof)",pattern=GraphPattern.model_validate(p)) for p in patterns[:5]]
    return SearchPlan.model_validate(plan.model_dump())
