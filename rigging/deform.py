"""2-D thin-plate-spline mesh keyform proposal from explicit, versioned anchors.

TPS interpolates independently provided landmark movements with an affine base,
so different facial landmarks can move differently (not only a uniform shift).
Proposal-only. No image synthesis and no implication of aesthetic quality.
"""
from __future__ import annotations
import copy
import hashlib
import json
import math

from .contracts import ContractError, validate_manifest, locate, finite_pair

class RigProposalError(ContractError):
    pass


def tps_offsets(vertices, source, target, *, regularization=0.0):
    try: import numpy as np
    except ImportError as exc: raise RigProposalError('NumPy required for TPS; pip install numpy') from exc
    n=len(source)
    if n<3 or n!=len(target):
        raise RigProposalError('TPS requires >=3 matched, noncollinear landmarks')
    if not isinstance(vertices,list) or not vertices:
        raise RigProposalError('nonempty mesh vertices required')
    s=np.asarray(source, dtype='float64'); t=np.asarray(target,dtype='float64'); v=np.asarray(vertices,dtype='float64')
    if s.shape!=(n,2) or t.shape!=(n,2) or v.ndim!=2 or v.shape[1]!=2 or not np.all(np.isfinite(s)) or not np.all(np.isfinite(t)) or not np.all(np.isfinite(v)):
        raise RigProposalError('bad finite 2-D coordinates')
    if not isinstance(regularization,(int,float)) or not math.isfinite(regularization) or regularization < 0:
        raise RigProposalError('regularization must be finite, nonnegative')
    scaled=max(1.0,float(np.max(np.ptp(s,axis=0))))
    sn=(s-s.mean(axis=0))/scaled; vn=(v-s.mean(axis=0))/scaled
    p=np.c_[np.ones(n),sn]
    if np.linalg.matrix_rank(p,tol=1e-9)!=3:
        raise RigProposalError('landmarks are collinear or degenerate')
    def kernel(r2):
        # r² ln(r), with K(0)=0; divide by 2 to use r² ln r².
        out=np.zeros_like(r2)
        mask=r2>1e-18
        out[mask]=0.5*r2[mask]*np.log(r2[mask])
        return out
    d=sn[:,None,:]-sn[None,:,:]
    k=kernel(np.sum(d*d,axis=-1))
    lam=float(regularization)
    mat=np.zeros((n+3,n+3),dtype='float64')
    mat[:n,:n]=k+lam*np.eye(n)
    mat[:n,n:]=p; mat[n:,:n]=p.T
    rhs=np.zeros((n+3,2));rhs[:n,:]=(t-s)/scaled
    try: weights=np.linalg.solve(mat,rhs)
    except np.linalg.LinAlgError as exc: raise RigProposalError('singular landmark transform') from exc
    kd=kernel(np.sum((vn[:,None,:]-sn[None,:,:])**2,axis=-1))
    displacement=(kd@weights[:n,:]+np.c_[np.ones(len(vn)),vn]@weights[n:,:])*scaled
    if not np.all(np.isfinite(displacement)): raise RigProposalError('non-finite fitted displacement')
    # Large movement is not automatically wrong but must pass geometric QA.
    return displacement.tolist()


def propose_keyform(document:dict, model_bytes:bytes, manifest:dict, config:dict):
    from native.inp08 import apply_keyform, FormatError, validate_mesh
    result=validate_manifest(document,model_bytes,manifest)
    guid=config.get('node_guid');param_name=config.get('parameter'); idx=config.get('key_index')
    if not isinstance(guid,str) or not isinstance(param_name,str): raise RigProposalError('node_guid/parameter required')
    if not isinstance(idx,list) or len(idx)!=2 or any(type(i) is not int for i in idx):raise RigProposalError('key_index [x,y] required')
    _,node,_=locate(document,guid)
    mesh=validate_mesh(node,node.get('name','mesh'))
    if mesh is None:raise RigProposalError('no mesh on target')
    anchors=[a for a in result['anchors'] if a['node_guid']==guid]
    targets=config.get('targets_local')
    if not isinstance(targets,dict):raise RigProposalError('explicit targets_local {anchor_label: [x,y]} needed')
    if set(targets)!=set(a['label'] for a in anchors):
        raise RigProposalError('each anchor must have exactly one target; no omitted or unknown points')
    source=[a['local'] for a in anchors]
    target=[finite_pair(targets[a['label']],a['label']) for a in anchors]
    offsets=tps_offsets(mesh['neutral'],source,target,regularization=config.get('regularization',0.0))
    patch={'parameter':param_name,'node_guid':guid,'key_index':idx,'vertex_offsets':offsets}
    # Existing user-authored keyforms are never overwritten here.
    temp=copy.deepcopy(document)
    try: report=apply_keyform(temp,patch)
    except (ValueError,KeyError,TypeError) as exc:raise RigProposalError(f'geometry/keyform safety gate failed: {exc}') from exc
    return {'format':'inochi-authoring.keyform-plan.v1','source_sha256':hashlib.sha256(model_bytes).hexdigest(),
            'patches':[patch],'status':'CANDIDATE_ONLY','algorithm':'TPS-v1-explicit-anchored',
            'anchor_manifest_source_sha256':manifest['source_sha256'],
            'source_anchor_count':len(anchors),
            'geometry_validation':report,
            'warning':'New keyform candidate, NOT verified by Creator rendering or against reference artwork.'}
