/** A 3x3 candidate pose proposal inspired by nine-pose workflows.
 * NOT imported upstream rig code; NOT an Inochi file writer; starting points only.
 */
export function proposeFaceNinePoses({landmarks,scale=1}={}){
 if(!landmarks||!Number.isFinite(scale)||scale<=0)throw new TypeError('landmarks and positive scale required');
 for(const key of ['face','leftEye','rightEye','nose','mouth','chin']){
  const p=landmarks[key];if(!Array.isArray(p)||p.length!==2||!p.every(Number.isFinite))throw new TypeError(`landmark ${key} must be [x,y]`);
 }
 const cx=landmarks.face[0],cy=landmarks.face[1];const hh=Math.max(1,Math.abs(landmarks.chin[1]-(landmarks.leftEye[1]+landmarks.rightEye[1])/2));
 const poses=[];
 for(const y of [-30,0,30])for(const x of [-30,0,30]){
  const t=x/30, u=y/30;const surface=[t*0.12*hh*scale,-u*0.1*hh*scale];
  const features={};
  for(const key of ['leftEye','rightEye','nose','mouth','chin']){
   const p=landmarks[key];const depth=key==='nose'?2:1;
   features[key]={position:[p[0]+surface[0]+t*0.10*hh*scale*depth,p[1]+surface[1]-u*0.06*hh*scale*depth],scaleX:key.endsWith('Eye')?(t===0?1:(key==='leftEye'&&t>0||key==='rightEye'&&t<0?0.8:1.1)):1};
  }
  poses.push({parameter:{AngleX:x,AngleY:y},faceSurfaceOffset:surface,features});
 }
 return {format:'inochi-authoring.face-nine-pose.v1',axisCenter:[cx,cy],headUnitPx:hh,poses,readyForCreator:false,requires:['rig binding per layer','artist review of face volume and occlusion','consistent topology at all 9 keyforms'],warning:'Numeric pose candidate; not a native .inp/.inx, and appearance quality is unverified.'};
}
