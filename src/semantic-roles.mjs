/** Conservative semantic PSD layer analyzer: names are hints, not an illustration segmenter. */
const rules=[
  ['eye_white',/(?:sclera|eye[_\s-]?white|white[_\s-]?eye|whites)/i],
  ['iris',/iris|홍채/i],['pupil',/pupil|동공/i],['eyelid',/eyelid|eyelash|lash|눈꺼풀|속눈썹/i],
  ['brow',/eyebrow|brow|눈썹/i],['mouth',/mouth|lip|tongue|teeth|입술|입안|혀|이빨/i],
  ['face',/face[_\s-]?base|얼굴[_\s-]?베이스/i],
  ['hair_front',/bang|fringe|front[_\s-]?hair|앞머리/i],
  ['hair_back',/back[_\s-]?hair|rear[_\s-]?hair|hair[_\s-]?back|뒷머리/i],
  ['hair_side',/side[_\s-]?hair|side[_\s-]?lock|옆머리/i],
  ['neck',/neck|목(_|$)/i],['torso',/torso|body[_\s-]?base|몸통/i],
  ['upper_arm',/upper[_\s-]?arm|상완/i],['forearm',/forearm|lower[_\s-]?arm|전완/i],
  ['hand',/hand|palm|손(_|$)/i],['clothing',/sleeve|collar|cuff|cape|cloth|coat|의상|소매/i],
  ['accessory',/dna|capsule|earring|hairpin|vial|accessory|장식/i]
];
export function classifyLayers(layers){
 if(!Array.isArray(layers))throw new TypeError('layers must be an array');
 const seen=new Set();const entries=layers.map((layer,i)=>{
  if(!layer||typeof layer.name!=='string'||!layer.name.trim())throw new TypeError(`invalid layer at ${i}`);
  if(seen.has(layer.name))throw new Error('duplicate layer: '+layer.name);seen.add(layer.name);
  const hit=rules.filter(([_,re])=>re.test(layer.name));
  const role=layer.role??(hit.length===1?hit[0][0]:null);
  if(role!==null && !rules.some(([key])=>key===role))throw new Error('unsupported role: '+role);
  const side=layer.side??(/(?:^|[_\s-])(L|left|좌)(?:[_\s-]|$)/i.test(layer.name)?'L':/(?:^|[_\s-])(R|right|우)(?:[_\s-]|$)/i.test(layer.name)?'R':null);
  if(side!==null&&!['L','R'].includes(side))throw new Error('unsupported side');
  return {name:layer.name,role,side,status:role?'classified':'needs-review',candidates:hit.map(h=>h[0]),bbox:layer.bbox??null};
 });
 const missing=['face','iris','eye_white','mouth','hair_front','hair_back','torso'].filter(role=>!entries.some(x=>x.role===role));
 return {entries,missingRoles:missing,unresolved:entries.filter(x=>!x.role).map(x=>x.name),ready:!missing.length&&!entries.some(x=>!x.role)};
}
