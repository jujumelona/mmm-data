import test from 'node:test';
import assert from 'node:assert/strict';
import { improveInteriorMesh } from '../src/mesh-repair.mjs';
import { classifyLayers } from '../src/semantic-roles.mjs';
import { proposeFaceNinePoses } from '../src/face-proposal.mjs';
import { analyzeMotion } from '../src/motion-quality.mjs';
import { providerPlan, getProvider } from '../src/providers.mjs';

test('mesh smoother never moves boundary or flips faces',()=>{
 const sample={neutral:[[0,0],[10,0],[10,10],[0,10],[3,3]],triangles:[[0,1,4],[1,2,4],[2,3,4],[3,0,4]]};
 const r=improveInteriorMesh(sample);
 assert.equal(r.boundaryVertexCount,4); assert.deepEqual(r.mesh.neutral.slice(0,4),sample.neutral.slice(0,4));
 assert.ok(r.mesh.neutral[4][0]>=3 && r.mesh.neutral[4][0]<=5);
});
test('mesh smoother rejects invalid triangles',()=>{
 assert.throws(()=>improveInteriorMesh({neutral:[[0,0]],triangles:[[0,0,0]]}),/invalid triangle/);
});
test('semantic inference is conservative and detects missing pieces',()=>{
 const result=classifyLayers([{name:'iris_L'},{name:'Unknown'}]);
 assert.equal(result.entries[0].side,'L');assert.equal(result.entries[0].role,'iris');
 assert.deepEqual(result.unresolved,['Unknown']);assert.equal(result.ready,false);
});
test('semantic inference allows explicit disambiguation',()=>{
 const result=classifyLayers([{name:'Circuit',role:'accessory',side:'R'}]);assert.equal(result.entries[0].role,'accessory');
});
test('face proposal emits nine complete pose candidates and neutral identity',()=>{
 const r=proposeFaceNinePoses({landmarks:{face:[50,50],leftEye:[40,42],rightEye:[60,42],nose:[50,49],mouth:[50,62],chin:[50,80]}});
 assert.equal(r.poses.length,9);const n=r.poses.find(x=>x.parameter.AngleX===0&&x.parameter.AngleY===0);
 assert.deepEqual(n.features.nose.position,[50,49]);assert.equal(n.features.leftEye.scaleX,1);assert.equal(n.features.rightEye.scaleX,1);assert.equal(r.readyForCreator,false);
});
test('face proposal refuses missing landmarks',()=>{
 assert.throws(()=>proposeFaceNinePoses({landmarks:{face:[1,1]}}),/landmark/);
});
test('motion analyzer detects loop discontinuity and range escapes',()=>{
 const r=analyzeMotion({loop:true,parameterRanges:{AngleX:[-30,30]},frames:[{t:0,parameters:{AngleX:0}},{t:1,parameters:{AngleX:40}}]});
 assert.equal(r.outOfRange.length,1);assert.equal(r.loopDiscontinuity.length,1);assert.equal(r.qualityPass,false);
});
test('motion analyzer accepts closed, in-range loop',()=>{
 const r=analyzeMotion({loop:true,parameterRanges:{AngleX:[-30,30]},frames:[{t:0,parameters:{AngleX:0}},{t:.5,parameters:{AngleX:20}},{t:1,parameters:{AngleX:0}}]});
 assert.equal(r.qualityPass,true);
});
test('provider registry includes all seven and claims no imports',()=>{
 const r=providerPlan();assert.equal(r.length,7);assert.ok(r.every(x=>!x.imported&&!x.nativeInochiExporter));assert.match(getProvider('iki').repo,/iki/);
});
test('provider registry rejects unknown',()=>assert.throws(()=>providerPlan(['none']),/unknown provider/));
import { checkoutPlan, acquireSources } from '../src/source-checkout.mjs';
test('source acquisition dry run checks allowlist without cloning',()=>{
 const plan=checkoutPlan(['iki','rev2d'],'/tmp/authoring-source-validation-example');
 assert.equal(plan.length,2);
 const result=acquireSources(plan,{dryRun:true});assert.ok(result.every(x=>x.status==='planned'));
 assert.throws(()=>checkoutPlan(['untrusted-repo'],'/tmp'),/unknown provider/);
});

import { execFileSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { resolve, dirname } from 'node:path';
const root = resolve(dirname(fileURLToPath(import.meta.url)), '..');
test('documented mesh-repair command accepts the example sample envelope', () => {
 const data = JSON.parse(execFileSync(process.execPath, ['src/cli.mjs','mesh-repair','examples/mesh.json'], {cwd:root,encoding:'utf8'}));
 assert.equal(data.results.length,1);
 assert.equal(data.results[0].moved,0);
 assert.equal(data.results[0].mesh.triangles.length,1);
});
test('real example layer roles do not misclassify hair_back',()=>{
 const data = JSON.parse(execFileSync(process.execPath,['src/cli.mjs','roles','examples/layers.json'], {cwd:root,encoding:'utf8'}));
 assert.equal(data.entries.find(x=>x.name==='hair_back').role,'hair_back');
 assert.equal(data.ready,true);
});
