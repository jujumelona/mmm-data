/** Quality-driven interior vertex smoothing. This does NOT re-rig the character.
 * Inspired by PuppetLoom's approach; independent implementation against our mesh contract.
 */
const cross = (a,b,c) => (b[0]-a[0])*(c[1]-a[1])-(b[1]-a[1])*(c[0]-a[0]);
const quality = (a,b,c) => {
  const area = Math.abs(cross(a,b,c));
  const edges = [[a,b],[b,c],[c,a]];
  const sum = edges.reduce((s,[p,q])=>s+(p[0]-q[0])**2+(p[1]-q[1])**2,0);
  return sum ? 2*Math.sqrt(3)*area/sum : 0;
};
export function improveInteriorMesh(sample, {passes=2, strength=0.5}={}) {
  if (!Number.isInteger(passes) || passes<0 || passes>20 || !Number.isFinite(strength) || strength<=0 || strength>1)
    throw new RangeError('invalid repair settings');
  const {neutral,triangles}=sample;
  if (!Array.isArray(neutral) || !Array.isArray(triangles)) throw new TypeError('mesh vertices and triangles required');
  const points = neutral.map(p=>[...p]);
  const edges=new Map(),fans=Array.from({length:points.length},()=>[]),adj=Array.from({length:points.length},()=>new Set());
  for(const tri of triangles){
    if(!Array.isArray(tri)||tri.length!==3||tri.some(i=>!Number.isInteger(i)||i<0||i>=points.length)||new Set(tri).size!==3)
      throw new TypeError('invalid triangle');
    for(let j=0;j<3;j++){
      const a=tri[j],b=tri[(j+1)%3],k=[Math.min(a,b),Math.max(a,b)].join(':');
      edges.set(k,(edges.get(k)||0)+1); adj[a].add(b); adj[b].add(a);
      fans[a].push(tri);
    }
  }
  const fixed = new Set();
  for(const [edge,count] of edges){ if(count===1){const [a,b]=edge.split(':').map(Number);fixed.add(a);fixed.add(b);} }
  let moved=0;
  for(let pass=0;pass<passes;pass++){
    for(let i=0;i<points.length;i++){
      if(fixed.has(i)||!fans[i].length||!adj[i].size)continue;
      const neighbors=[...adj[i]],center=[0,0];
      for(const n of neighbors){center[0]+=points[n][0]/neighbors.length;center[1]+=points[n][1]/neighbors.length;}
      const original=points[i];const before=Math.min(...fans[i].map(t=>quality(...t.map(n=>points[n]))));
      for(const factor of [strength,strength/2,strength/4]){
        const candidate=[original[0]+(center[0]-original[0])*factor,original[1]+(center[1]-original[1])*factor];
        const newPoint=k=>k===i?candidate:points[k];
        if(fans[i].some(tri=>{
          const oldCross=cross(...tri.map(k=>points[k])); const newCross=cross(...tri.map(newPoint));
          return Math.abs(oldCross)<1e-10 || oldCross*newCross<=0;
        })) continue;
        const after=Math.min(...fans[i].map(t=>quality(...t.map(newPoint))));
        if(after>before+1e-8){points[i]=candidate;moved++;break;}
      }
    }
  }
  return {mesh:{...sample,neutral:points},moved,boundaryVertexCount:fixed.size,warning:'Rest-pose mesh topology only; preserve original UV and re-bake all keyforms after editing.'};
}
