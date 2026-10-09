/* Natural-language workbench: declarative jobs, explicit strategies and evidence. */
const esc = value => String(value ?? '').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const json = value => esc(JSON.stringify(value,null,2));
const $ = (root,selector) => root.querySelector(selector);

export function jobOutcome(job){
  if(job.state==='complete')return {result:job.result};
  if(job.state==='failed')return {error:job.error||'Search failed.'};
  if(job.state==='cancelled')return {error:'Search cancelled.'};
  return {pending:true,stage:job.stage};
}
export function searchPayload(state){
  const ref=String(state.reference||'').trim();
  return {text:state.text.trim(),strategy:state.strategy||'patterns',provider:state.provider||'codex',model:state.model||'',reference_id:/^\d+$/.test(ref)?'analoggenie:'+ref:ref,limit:Number(state.limit||20)};
}
export function scoreLabels(c){
  return [['pattern_coverage','PATTERN COVERAGE'],['structural_score','FULL PATTERN'],['topology_score','PROTOTYPE COSINE'],['reference_score','REFERENCE SCORE'],['semantic_score','TEXT COSINE']].filter(([key])=>c[key]!=null).map(([key,label])=>[Number(c[key]).toFixed(3),label]);
}
export function providerChoice(requested, providers){
  return providers.find(p=>p.id===requested)||{id:requested,available:false,note:'Choose an available provider explicitly.'};
}
let activeJob=null;
const mounts=new WeakMap();
export function mountGuard(root){const token=Symbol();mounts.set(root,token);return ()=>root.isConnected&&mounts.get(root)===token;}
export function canSearch(state,providerReady){return Boolean(providerReady||(!state.text.trim()&&state.reference.trim()));}

export async function mountNatural(root,{state,persist,api,onResult,onReferenceOnly}){
  const isCurrent=mountGuard(root);let providerReady=false;
  root.innerHTML=`<div class="similarity-form natural-form"><label for="natural-prompt">What circuit are you looking for?</label><textarea id="natural-prompt" placeholder="e.g. Find current mirrors with fewer than 12 transistors and a diode-connected reference branch.">${esc(state.text)}</textarea><div class="natural-strategies" role="group" aria-label="Retrieval strategy"><button class="strategy ${state.strategy!=='prototypes'?'selected':''}" data-strategy="patterns"><strong>Query patterns</strong><span>Language → JSON → structural Cypher</span></button><button class="strategy ${state.strategy==='prototypes'?'selected':''}" data-strategy="prototypes"><strong>Generated prototypes <span class="pill">EXPERIMENTAL</span></strong><span>4–5 temporary graphs → topology similarity</span></button></div><div class="natural-settings"><label>Converter<select id="natural-provider"><option>Loading providers…</option></select></label><label>Model <span class="muted">· optional for CLI</span><input id="natural-model" list="natural-models" placeholder="Provider default" value="${esc(state.model||'')}"><datalist id="natural-models"></datalist></label><label>Results<select id="natural-limit">${[10,20,50].map(n=>`<option ${Number(state.limit||20)===n?'selected':''}>${n}</option>`).join('')}</select></label></div><p class="help" id="provider-note"></p><details class="query-options" ${state.reference?'open':''}><summary>Reference circuit · optional topology signal</summary><div class="reference-picker"><input id="reference-circuit" autocomplete="off" placeholder="Circuit ID, e.g. 1004" value="${esc(state.reference||'')}"><div id="reference-suggestions" class="suggestions hidden"></div></div><p class="help">Most searches need no reference. Leave the prompt blank to compare directly without an LLM.</p></details><div class="info-strip" id="strategy-note"></div><div id="query-error"></div><div class="query-actions"><span class="help" id="natural-progress">Hard requirements filter before ranking.<br>Function and performance still need verification.</span><div class="natural-actions"><button class="button hidden" id="cancel-natural">Cancel</button><button class="button primary" id="run-natural">Search circuits →</button></div></div></div>`;
  const save=()=>{
    state.text=$(root,'#natural-prompt').value;state.reference=$(root,'#reference-circuit').value;
    state.provider=$(root,'#natural-provider').value;state.model=$(root,'#natural-model').value;
    state.limit=Number($(root,'#natural-limit').value);persist();$(root,'#run-natural').disabled=!canSearch(state,providerReady);
  };
  const strategyNote=()=>{$(root,'#strategy-note').textContent=state.strategy==='prototypes'?'Experimental: the model invents retrieval anchors, not proven designs. Only real dataset circuits are returned. Invalid or duplicate anchors are disclosed.':'The model interprets your requirements. Validated JSON is compiled to read-only Cypher; inferred function patterns remain hypotheses, not confirmed labels.';};
  strategyNote();
  root.querySelectorAll('[data-strategy]').forEach(button=>button.onclick=()=>{state.strategy=button.dataset.strategy;root.querySelectorAll('[data-strategy]').forEach(b=>b.classList.toggle('selected',b===button));strategyNote();persist();});
  for(const id of ['natural-prompt','reference-circuit','natural-model','natural-limit'])$(root,'#'+id).addEventListener('input',save);
  let timer;
  $(root,'#reference-circuit').addEventListener('input',event=>{clearTimeout(timer);timer=setTimeout(async()=>{const input=event.target,search=input.value.trim();const box=$(root,'#reference-suggestions');if(!search){box.classList.add('hidden');return;}try{const data=await api('/api/circuits?'+new URLSearchParams({search,limit:6}));if(!isCurrent()||input.value.trim()!==search)return;box.innerHTML=data.items.map(c=>`<button data-reference="${esc(c.id)}">${esc(c.title)} <span class="muted mono">${esc(c.id)}</span></button>`).join('');box.classList.toggle('hidden',!data.items.length);box.querySelectorAll('[data-reference]').forEach(b=>b.onclick=()=>{input.value=b.dataset.reference;box.classList.add('hidden');save();});}catch{}},180);});
  $(root,'#reference-circuit').onblur=()=>setTimeout(()=>$(root,'#reference-suggestions')?.classList.add('hidden'),180);
  const run=$(root,'#run-natural'),cancel=$(root,'#cancel-natural');
  run.disabled=true;
  cancel.onclick=async()=>{if(activeJob){cancel.disabled=true;await api('/api/natural/jobs/'+activeJob,{method:'DELETE'});$(root,'#natural-progress').textContent='Cancelling owned conversion…';}};
  async function execute(){
    save();$(root,'#query-error').innerHTML='';
    if(!state.text.trim()){
      if(state.reference.trim()){await onReferenceOnly(searchPayload(state));return;}
      $(root,'#query-error').innerHTML='<div class="error">Enter a circuit request or choose a reference.</div>';return;
    }
    if(run.disabled)return;
    run.disabled=true;cancel.disabled=false;cancel.classList.remove('hidden');
    const controls=[...root.querySelectorAll('input,textarea,select,[data-strategy]')];controls.forEach(c=>c.disabled=true);
    try{
      const started=await api('/api/natural/jobs',{method:'POST',body:JSON.stringify(searchPayload(state))});activeJob=started.id;
      let job=started;
      while(true){
        const outcome=jobOutcome(job);
        if(!outcome.pending){if(outcome.error)throw new Error(outcome.error);onResult(outcome.result,isCurrent());break;}
        if(isCurrent())$(root,'#natural-progress').innerHTML=`<span class="spinner"></span> ${esc(outcome.stage)}…`;
        await new Promise(resolve=>setTimeout(resolve,600));
        job=await api('/api/natural/jobs/'+started.id);
      }
    }catch(error){if(isCurrent())$(root,'#query-error').innerHTML=`<div class="error">${esc(error.message)}</div>`;}
    finally{activeJob=null;controls.forEach(c=>c.disabled=false);if(isCurrent()){run.disabled=!canSearch(state,providerReady);cancel.classList.add('hidden');$(root,'#natural-progress').textContent='Ready · inspect each candidate’s schematic and netlist.';}}
  }
  run.onclick=execute;$(root,'#natural-prompt').onkeydown=e=>{if(e.key==='Enter'&&(e.metaKey||e.ctrlKey)){e.preventDefault();execute();}};
  try{
    const data=await api('/api/natural/providers');if(!isCurrent())return;
    const select=$(root,'#natural-provider');const current=state.provider||'codex';
    select.innerHTML=data.providers.map(p=>`<option value="${p.id}" ${!p.available?'disabled':''}>${esc(p.name)}${p.available?'':' · unavailable'}</option>`).join('');
    select.value=current;
    const update=()=>{const p=providerChoice(select.value,data.providers);providerReady=p.available;state.provider=p.id;$(root,'#provider-note').textContent=(!p.available?'Selected provider is unavailable; choose another explicitly. ':'')+(p.remote?'Cloud conversion: your prompt/schema goes to this provider; normal account usage applies. ':'')+p.note;$(root,'#natural-models').innerHTML=(p.models||[]).map(m=>`<option value="${esc(m)}"></option>`).join('');if(p.id==='ollama'&&p.available&&!p.models.includes($(root,'#natural-model').value))$(root,'#natural-model').value=p.models[0]||'';save();};
    select.onchange=()=>{$(root,'#natural-model').value='';update();};update();
  }catch(error){if(isCurrent()){$(root,'#provider-note').textContent=error.message;run.disabled=!canSearch(state,false);}}
}

function fullResultHTML(data){
  const plan=data.plan||{};
  if(data.clarification_questions?.length)return `<section class="panel facts"><h3>Clarification needed</h3>${data.clarification_questions.map(q=>`<p>${esc(q)}</p>`).join('')}<p class="help">Edit your prompt and search again. No graph query was executed.</p></section>`;
  const requirements=(plan.count_constraints||[]).map(c=>`${c.entity} ${{eq:'=',gt:'>',ge:'≥',lt:'<',le:'≤'}[c.operator]} ${c.value}`);
  const unverified=plan.unverified_requirements||[];
  return `<div class="result-heading"><h2>${data.items.length} candidates</h2><span class="muted">${esc(data.strategy==='prototypes'?'Prototype':'Query-pattern')} retrieval · ${Number(data.total).toLocaleString()} eligible</span></div><div class="panel natural-summary"><h3>${esc([plan.requested_function,plan.requested_topology].filter(Boolean).join(' · ')||'Structural search')}</h3><p>${esc(requirements.join(' · ')||'No numeric hard filters')} · ${data.structural_matches||0} structural hypothesis matches</p>${unverified.length?`<div class="unverified"><strong>Not verified:</strong> ${unverified.map(u=>esc(u.requirement)+' — '+esc(u.reason)).join('<br>')}</div>`:''}${(data.warnings||[]).map(w=>`<p class="result-note">${esc(w)}</p>`).join('')}</div><div class="panel">${data.items.length?data.items.map((c,i)=>`<article class="search-card" data-result-id="${esc(c.id)}" tabindex="0" aria-label="Inspect ${esc(c.title)}"><div class="rank">${String(i+1).padStart(2,'0')}</div><div><h3>${esc(c.title)} <span class="muted mono natural-id">${esc(c.id)}</span></h3><span class="pill">${esc(c.tier)}</span><p>${esc(c.evidence.slice(0,4).join(' · '))}</p><details class="match-evidence"><summary>Why this candidate?</summary>${c.matches.map(m=>`<p>${esc(m.interpretation)}</p><pre>${esc(m.witness.connections.join('\n'))}</pre>`).join('')}<p>${esc(c.evidence.join(' · '))}</p><p class="help">${Object.entries(c.statistics.device_type_counts).map(([k,v])=>esc(k)+': '+v).join(' · ')} · ${c.statistics.external_port_count} declared ports</p></details></div><div class="scores">${scoreLabels(c).map(([value,label])=>`<div>${value}<span>${label}</span></div>`).join('')}</div></article>`).join(''):'<div class="empty-state"><h3>No circuits meet these requirements</h3><p>Change the request; no hard filter was silently relaxed.</p></div>'}</div><p class="result-note">${esc(data.warning)}</p><details class="query-options"><summary>Interpretation · JSON plan</summary><pre class="schema-block">${json(plan)}</pre></details><details class="query-options"><summary>Compiled read-only Cypher · ${data.queries.length} queries</summary>${data.queries.map(q=>`<h4>${esc(q.purpose)}</h4><pre class="schema-block">${esc(q.cypher)}</pre><pre class="schema-block">${json(q.parameters)}</pre>`).join('')}</details>${data.strategy==='prototypes'?`<details class="query-options"><summary>Temporary prototype netlists · ${data.prototypes.length} accepted</summary><p class="help">Never added to the database; not simulated. Best-prototype scores are retrieval signals, not correctness probabilities.</p>${data.prototypes.map(p=>`<h4>${esc(p.name)}</h4><p>${esc(p.rationale)}</p><pre class="schema-block">${esc(p.netlist)}</pre><p class="help">Ports: ${esc(p.ports)}</p>`).join('')}${data.prototype_diagnostics.map(p=>`<p class="error">${esc(p.name)}: ${esc(p.error)}</p>`).join('')}</details>`:''}`;
}

export function naturalResultHTML(data){
  const full=fullResultHTML(data),partials=data.partial_items||[];
  if(data.clarification_questions?.length||!partials.length)return full;
  return full+`<details class="query-options"><summary>Near misses · ${partials.length} · NOT full matches</summary><p class="help">These preserve numeric/physical filters but lack mandatory wiring or supporting structural evidence. They are excluded from the main results.</p>${partials.map(c=>`<p><a href="#circuit/${encodeURIComponent(c.id)}/graph">${esc(c.title)}</a></p><p class="result-note">Missing: ${c.missing_requirements.map(esc).join(' · ')}</p>`).join('')}</details>`;
}
