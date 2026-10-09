import test from 'node:test';
import assert from 'node:assert/strict';
import {studioPayload, exportName, previewScale, importPayload, stateFromArtifact} from '../../src/circuit_workbench/static/studio.mjs';

test('prompt-only generation never requires a user netlist',()=>{
  const p=studioPayload({mode:'prompt',prompt:'Draw a mirror',provider:'codex',style:'connected'});
  assert.equal(p.mode,'prompt');assert.equal(p.prompt,'Draw a mirror');assert.equal(p.netlist,'');
});
test('library render reuses its ID and can run without a converter',()=>{
  const p=studioPayload({mode:'library',source_id:'1004',polish:false});
  assert.equal(p.source_id,'analoggenie:1004');assert.equal(p.polish,false);
});
test('export names cannot inject paths and fit never divides by zero',()=>{
  assert.equal(exportName('../mirror<script>'),'mirror-script-');
  assert.equal(previewScale(0,0,0,0),1);
  assert.ok(previewScale(600,400,1200,800)<1);
});
test('explicit import retains generated provenance rather than claiming verified metadata',()=>{
  const p=importPayload({netlist:'M1',description:'Draft',ports:'a b',name:'Mirror',source:{kind:'proposed'},unverified:['Not simulated']});
  assert.equal(p.metadata.family,undefined);assert.match(p.metadata.notes,/proposed/);assert.match(p.metadata.notes,/Not simulated/);
});
test('reopening a proposed artifact restores prompt mode rather than stale library controls',()=>{
  const s=stateFromArtifact({source:{kind:'proposed',prompt:'draw OTA',provider:'codex'},request:{model:'',style:'connected'},netlist:'M1',description:'OTA',ports:'in out'});
  assert.equal(s.mode,'prompt');assert.equal(s.prompt,'draw OTA');assert.equal(s.source_id,'');
});
