import test from 'node:test';
import assert from 'node:assert/strict';
import {jobOutcome, searchPayload, scoreLabels, providerChoice, mountGuard, canSearch,naturalResultHTML,deliverResult,historyProvider,executionLock,retireOwnedJob} from '../../src/circuit_workbench/static/natural-language.mjs';

test('refresh cancels only the job owned by this tab and does not restore search fields',async()=>{
  const values=new Map([['atlas-owned-natural-job','our-job']]),calls=[];
  const storage={getItem:k=>values.get(k),removeItem:k=>values.delete(k)};
  await retireOwnedJob(storage,async(path,options)=>calls.push([path,options.method]));
  assert.deepEqual(calls,[['/api/natural/jobs/our-job','DELETE']]);assert.equal(values.size,0);
  await retireOwnedJob(storage,()=>assert.fail('Must not cancel an unowned job'));
});

test('history replay preserves rules-only interpretation instead of selecting a cloud converter',()=>{
  assert.equal(historyProvider({provider:'codex',interpretation:'rules_only'}),'rules');
  assert.equal(historyProvider({provider:'ollama'}),'ollama');
});

test('reference-only execution is serialized and cannot finish behind a newer search',()=>{
  const lock=executionLock();assert.equal(lock.begin(),true);assert.equal(lock.begin(),false);
  lock.end();assert.equal(lock.begin(),true);
});

test('failed and cancelled jobs never masquerade as empty successful searches',()=>{
  assert.equal(jobOutcome({state:'complete',result:{items:[]}}).result.items.length,0);
  assert.equal(jobOutcome({state:'running',stage:'ranking'}).pending,true);
  assert.equal(jobOutcome({state:'cancelled'}).error,'Search cancelled.');
  assert.equal(jobOutcome({state:'failed',error:'provider failed'}).error,'provider failed');
});
test('both strategies preserve prompt/reference rather than embedding counts as text only',()=>{
  const p=searchPayload({text:'Find a mirror with 4 transistors',strategy:'prototypes',provider:'codex',model:'',reference:'1004',limit:'10'});
  assert.equal(p.strategy,'prototypes');assert.equal(p.reference_id,'analoggenie:1004');assert.equal(p.limit,10);
});
test('scores omit unavailable signals and do not present probabilities',()=>{
  assert.deepEqual(scoreLabels({semantic_score:null,topology_score:.5,structural_score:.8,reference_score:null}),[['0.800','FULL PATTERN'],['0.500','PROTOTYPE COSINE']]);
});
test('an unavailable local provider never silently switches to cloud',()=>{
  const p=providerChoice('ollama',[{id:'codex',available:true},{id:'ollama',available:false}]);
  assert.equal(p.id,'ollama');assert.equal(p.available,false);
});
test('remounting a connected form invalidates older asynchronous updates',()=>{
  const root={isConnected:true},first=mountGuard(root);assert.equal(first(),true);
  const second=mountGuard(root);assert.equal(first(),false);assert.equal(second(),true);
  root.isConnected=false;assert.equal(second(),false);
});
test('direct reference search does not need an available converter',()=>{
  assert.equal(canSearch({text:'',reference:'1004'},false),true);
  assert.equal(canSearch({text:'find comparator',reference:''},false),false);
});
test('near misses never appear as full results in the UI',()=>{
  const html=naturalResultHTML({plan:{},strategy:'patterns',items:[],total:0,structural_matches:0,queries:[],warnings:[],partial_items:[{id:'x',title:'near miss',missing_requirements:['connected capacitor branch']}]});
  assert.match(html,/0 candidates/);assert.match(html,/Near misses/);assert.match(html,/connected capacitor branch/);assert.doesNotMatch(html,/data-result-id="x"/);
});

test('rule-engine results disclose that no converter model was called',()=>{
  const html=naturalResultHTML({interpreter:'deterministic rules',plan:{},strategy:'patterns',items:[],total:0,structural_matches:0,queries:[],warnings:[]});
  assert.match(html,/Shared structural rules/);assert.match(html,/no converter model call/i);
  assert.match(html,/not proof.*dataset/i);
});

test('completion of an old form never delivers stale results to a remounted workbench',()=>{
  const root={isConnected:true},old=mountGuard(root),received=[];
  const current=mountGuard(root);
  deliverResult(old,{id:'old'},result=>received.push(result));
  deliverResult(current,{id:'current'},result=>received.push(result));
  assert.deepEqual(received,[{id:'current'}]);
});

test('rules-only selection is explicit and cannot silently request cloud conversion',()=>{
  const p=searchPayload({text:'Find a two-stage amplifier',provider:'rules',strategy:'patterns',reference:'',limit:20});
  assert.equal(p.interpretation,'rules_only');assert.equal(p.provider,'codex');
});

test('selecting any LLM explicitly requests model interpretation for a common prompt',()=>{
  for(const provider of ['codex','ollama','claude']){
    const p=searchPayload({text:'Find a two-stage amplifier',provider,strategy:'patterns',reference:'',limit:20});
    assert.equal(p.interpretation,'llm');assert.equal(p.provider,provider);
  }
});

test('prototype mode never advertises a model-free generation',()=>{
  const html=naturalResultHTML({interpreter:'deterministic rules',plan:{},strategy:'prototypes',items:[],total:0,structural_matches:0,queries:[],warnings:[],prototypes:[],prototype_diagnostics:[]});
  assert.match(html,/Prototype generation.*selected model/i);
  assert.doesNotMatch(html,/no converter model call/i);
});
