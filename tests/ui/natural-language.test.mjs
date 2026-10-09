import test from 'node:test';
import assert from 'node:assert/strict';
import {jobOutcome, searchPayload, scoreLabels, providerChoice, mountGuard, canSearch,naturalResultHTML} from '../../src/circuit_workbench/static/natural-language.mjs';

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
