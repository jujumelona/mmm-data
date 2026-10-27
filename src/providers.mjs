/** Explicit, opt-in external source registry. Never automatically install or execute external code. */
export const providers=Object.freeze({
 psd2live:{repo:'tsunehimatoi/psd2live',focus:['ninePoseFace','semanticRig'],integration:'algorithm-adapter',runtime:'external',notes:'GPL parts; face rig still produces flawed output for some artwork.'},
 iki:{repo:'zeikar/iki',focus:['layerRoles','autoBlink','autoMouth','autoHead','arms'],integration:'algorithm-adapter',runtime:'external',notes:'MIT; defaults tuned on few characters, not an Inochi exporter.'},
 rev2d:{repo:'RevStudio/Rev2D',focus:['motionValidation','loopSeams','physicsLimits','ikLimits'],integration:'data-adapter',runtime:'external',notes:'MIT; output is not Inochi format.'},
 puppetloom:{repo:'CheshireMew/PuppetLoom',focus:['meshQuality','revisionGates','occlusionQA'],integration:'algorithm-adapter',runtime:'external',notes:'AGPL; no verified high-layer-count transfer.'},
 stretchystudio:{repo:'MangoLion/stretchystudio',focus:['bodyLandmarks','armSkinning'],integration:'optional-study',runtime:'external',notes:'MIT; style-dependent autro-rig regressions.'},
 meshavatarstudio:{repo:'shinshin86/mesh-avatar-studio',focus:['faceLandmarks','poseRenderComparison'],integration:'optional-study',runtime:'external',notes:'MIT; designed for simplified front bust.'},
 anime25drig:{repo:'852wa/Anime2.5DRig',focus:['layerRoleInference','simpleAnchorPlacement'],integration:'optional-study',runtime:'external',notes:'MIT; neck/torso artifacts documented.'}
});
export function getProvider(name){if(!Object.hasOwn(providers,name))throw new Error('unknown provider: '+name);return providers[name];}
export function providerPlan(requested=Object.keys(providers)){
 if(!Array.isArray(requested))throw new TypeError('requested must be array');
 return requested.map(name=>({id:name,...getProvider(name),imported:false,executable:false,nativeInochiExporter:false}));
}
