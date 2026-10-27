#!/usr/bin/env node
import { readFileSync } from 'node:fs';
import { analyzePose } from './rig-quality.mjs';
import { improveInteriorMesh } from './mesh-repair.mjs';
import { classifyLayers } from './semantic-roles.mjs';
import { proposeFaceNinePoses } from './face-proposal.mjs';
import { analyzeMotion } from './motion-quality.mjs';
import { providerPlan } from './providers.mjs';
const [command,file]=process.argv.slice(2);
try{
 const doc=file?JSON.parse(readFileSync(file,'utf8')):null;
 const result=command==='mesh-check'?{results:doc.samples.map(s=>analyzePose(s))}
   :command==='mesh-repair'?(Array.isArray(doc?.samples)
     ?{results:doc.samples.map(s=>({part:s.part??null,pose:s.pose??null,...improveInteriorMesh(s)}))}
     :improveInteriorMesh(doc))
   :command==='roles'?classifyLayers(doc.layers)
   :command==='face-propose'?proposeFaceNinePoses(doc)
   :command==='motion-check'?analyzeMotion(doc)
   :command==='providers'?providerPlan(doc?.requested)
   :null;
 if(result===null)throw new Error('Usage: node src/cli.mjs <mesh-check|mesh-repair|roles|face-propose|motion-check|providers> [input.json]');
 console.log(JSON.stringify(result,null,2));
 if(command==='mesh-check'&&result.results.some(r=>!r.geometryPass))process.exitCode=1;
 if(command==='motion-check'&&!result.qualityPass)process.exitCode=1;
}catch(error){console.error(error.message);process.exitCode=2;}
