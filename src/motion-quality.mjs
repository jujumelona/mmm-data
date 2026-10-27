/** Motion QA from sampled frames. Works without a runtime; does not claim visual beauty. */
export function analyzeMotion({frames,parameterRanges={},loop=false,loopTolerance=0.01,canvas}={}){
 if(!Array.isArray(frames)||frames.length<2)throw new TypeError('at least two frames required');
 let prevT=-Infinity;const names=new Set();
 for(const f of frames){
  if(!f||!Number.isFinite(f.t)||f.t<=prevT||!f.parameters||typeof f.parameters!=='object')throw new TypeError('frames must be ordered by increasing t and include parameters');
  prevT=f.t;
  for(const [k,v] of Object.entries(f.parameters)){if(!Number.isFinite(v))throw new TypeError('non-finite parameter: '+k);names.add(k);}
 }
 const outOfRange=[],loopDiscontinuity=[],outsideCanvas=[];
 for(const k of names){
  const bounds=parameterRanges[k];
  if(bounds){if(!Array.isArray(bounds)||bounds.length!==2||bounds.some(x=>!Number.isFinite(x))||bounds[0]>=bounds[1])throw new TypeError('invalid parameter range');
    frames.forEach((f,i)=>{if(k in f.parameters&&(f.parameters[k]<bounds[0]||f.parameters[k]>bounds[1]))outOfRange.push({parameter:k,frame:i,value:f.parameters[k]});});
  }
  const start=frames[0].parameters[k],end=frames.at(-1).parameters[k];
  if(loop&&Number.isFinite(start)&&Number.isFinite(end)&&Math.abs(start-end)>loopTolerance)loopDiscontinuity.push({parameter:k,delta:Math.abs(start-end)});
 }
 if(canvas){if(!Array.isArray(canvas)||canvas.length!==2||canvas.some(x=>!Number.isFinite(x)||x<=0))throw new TypeError('invalid canvas');
  frames.forEach((f,i)=>{for(const [name,p] of Object.entries(f.points??{})){if(!Array.isArray(p)||p.length!==2||p.some(x=>!Number.isFinite(x)))throw new TypeError('invalid point');if(p[0]<0||p[1]<0||p[0]>canvas[0]||p[1]>canvas[1])outsideCanvas.push({frame:i,part:name});}});
 }
 return {frames:frames.length,duration:frames.at(-1).t-frames[0].t,outOfRange,loopDiscontinuity,outsideCanvas,qualityPass:!outOfRange.length&&!loopDiscontinuity.length&&!outsideCanvas.length,warning:'Does not calculate physics, IK reachability, pose realism or rendered pixels; requires actual samples.'};
}
