#!/usr/bin/env node
/** Optional upstream source checkout. Never executes third-party source or installs its dependencies. */
import { spawnSync } from 'node:child_process';
import { existsSync, mkdirSync, mkdtempSync, renameSync, rmSync, writeFileSync } from 'node:fs';
import { resolve, join } from 'node:path';
import { pathToFileURL } from 'node:url';
import { providers, getProvider } from './providers.mjs';

export function checkoutPlan(ids, destRoot){
 if(!Array.isArray(ids)||!ids.length)throw new TypeError('at least one source required');
 const destination=resolve(destRoot);
 return [...new Set(ids)].map(id=>{const p=getProvider(id);return {id,repo:p.repo,url:`https://github.com/${p.repo}.git`,destination:join(destination,id)};});
}
export function acquireSources(plan,{dryRun=false}={}){
 if(!Array.isArray(plan))throw new TypeError('plan required');
 const outcomes=[];
 for(const job of plan){
  if(existsSync(job.destination))throw new Error(`destination exists: ${job.destination}`);
  if(dryRun){outcomes.push({...job,status:'planned'});continue;}
  const parent=resolve(job.destination,'..');mkdirSync(parent,{recursive:true});
  const temp=mkdtempSync(join(parent,'.authoring-source-'));
  try{
   // Clone exact allow-listed public GitHub repos. No shell interpolation and no scripts executed.
   const clone=spawnSync('git',['clone','--depth','1','--filter=blob:none','--',job.url,temp],{encoding:'utf8',timeout:180000});
   if(clone.status!==0)throw new Error(`git clone failed (${job.id}): ${clone.stderr?.slice(-300)}`);
   const rev=spawnSync('git',['-C',temp,'rev-parse','HEAD'],{encoding:'utf8'});
   if(rev.status!==0)throw new Error('cannot capture source revision');
   const sha=rev.stdout.trim();
   // Source provenance sidecar; do not mark the foreign tool as Inochi-compatible.
   writeFileSync(join(temp,'UPSTREAM-SOURCE-STATUS.json'),JSON.stringify({project:job.id,upstream:job.repo,commit:sha,downloadedOnly:true,ported:false,nativeInochiExporter:false},null,2)+'\n');
   renameSync(temp,job.destination);
   outcomes.push({...job,commit:sha,status:'source-only'});
  }catch(error){rmSync(temp,{recursive:true,force:true});throw error;}
 }
 return outcomes;
}
if(process.argv[1] && import.meta.url===pathToFileURL(process.argv[1]).href){
 try{
  const args=process.argv.slice(2);const dryRun=args.includes('--dry-run');const all=args.includes('--all');
  const rootArg=args.indexOf('--dest');if(rootArg<0||!args[rootArg+1])throw new Error('Usage: node src/source-checkout.mjs [--all | provider...] --dest DIR [--dry-run]');
  const root=args[rootArg+1];const ids=all?Object.keys(providers):args.filter(a=>!a.startsWith('--')&&a!==root);
  console.log(JSON.stringify(acquireSources(checkoutPlan(ids,root),{dryRun}),null,2));
 }catch(error){console.error(error.message);process.exitCode=2;}
}
