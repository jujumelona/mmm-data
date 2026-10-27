"""Explicit planar scene-graph coordinate evaluation for Inochi2D 0.8.

Only unambiguous, rotation-Z 2D transforms are supported. Refuse root locks,
X/Y rotations, singular scales, unparseable transforms and sheared results.
Never interpret a mesh-local landmark as an editor pivot automatically.
"""
from __future__ import annotations
import math
from .contracts import ContractError, lineage, finite_pair


def _matmul(a,b):
    return [[sum(a[i][k]*b[k][j] for k in range(3)) for j in range(3)] for i in range(3)]


def _inverse(m):
    a,b,tx=m[0];c,d,ty=m[1];det=a*d-b*c
    if abs(det)<1e-12:raise ContractError('singular transform')
    return [[d/det,-b/det,(b*ty-d*tx)/det],
            [-c/det,a/det,(c*tx-a*ty)/det],[0.,0.,1.]]


def _transform_data(t):
    if not isinstance(t,dict):
        raise ContractError('node transform missing/unsupported; cannot calculate world position')
    trans=t.get('trans',t.get('translation'))
    rot=t.get('rot',t.get('rotation'))
    scale=t.get('scale')
    if (not isinstance(trans,list) or len(trans)!=3 or
        not isinstance(rot,list) or len(rot)!=3 or
        not isinstance(scale,list) or len(scale)!=2):
        raise ContractError('explicit trans[3], rot[3] radians, scale[2] required')
    if any(type(x) not in (int,float) or not math.isfinite(x) for x in (*trans,*rot,*scale)):
        raise ContractError('non-finite transform')
    if abs(rot[0])>1e-9 or abs(rot[1])>1e-9:
        raise ContractError('3D X/Y rotation needs SDK matrix, not planar shortcut')
    if abs(scale[0])<1e-9 or abs(scale[1])<1e-9:
        raise ContractError('singular node scale')
    return trans,rot,scale


def local_matrix(t):
    trans,rot,scale=_transform_data(t)
    cs=math.cos(rot[2]);sn=math.sin(rot[2]);sx,sy=scale
    return [[cs*sx,-sn*sy,trans[0]],
            [sn*sx,cs*sy,trans[1]],
            [0.,0.,1.]]


def world_matrix(document,guid):
    result=[[1.,0.,0.],[0.,1.,0.],[0.,0.,1.]]
    for n in lineage(document,guid):
        if n.get('lockToRoot'):
            raise ContractError(f"{n.get('guid')} uses lockToRoot; explicit Creator SDK transform required")
        result=_matmul(result,local_matrix(n['transform']))
    return result


def transform_point(matrix,point):
    x,y=finite_pair(point,'point')
    return [matrix[0][0]*x+matrix[0][1]*y+matrix[0][2],
            matrix[1][0]*x+matrix[1][1]*y+matrix[1][2]]


def mesh_local_to_world(document,guid,local):
    return transform_point(world_matrix(document,guid),local)


def world_to_mesh_local(document,guid,world):
    return transform_point(_inverse(world_matrix(document,guid)),world)


def pivot_handoff(document,validated_anchor):
    """Machine-readable control-point handoff to a rigging agent or Creator.

    A semantic anchor is a joint location, *not* the actual node pivot unless
    its mesh-local point is [0,0]. Moving an editor node requires compensated
    mesh/child/binding edits, which this function deliberately does not do.
    """
    guid=validated_anchor['node_guid'];local=validated_anchor['local']
    world=mesh_local_to_world(document,guid,local)
    origin=mesh_local_to_world(document,guid,[0,0])
    return {'node_guid':guid,'parent_guid':validated_anchor.get('parent_guid'),
            'kind':validated_anchor['kind'],'label':validated_anchor['label'],
            'landmark_mesh_local':local,'landmark_world':world,
            'current_node_pivot_world':origin,
            'pivot_is_at_landmark':math.dist(world,origin)<1e-7,
            'coordinate_space':'inochi_model_world_xy',
            'transform_units':'model_units','rotation_units':'radians',
            'apply_policy':'PLAN_ONLY_REQUIRES_CREATOR_COMPENSATION'}


def reparent_plan_2d(document,node_guid,new_parent_guid):
    """Derive a world-preserving planar reparent *proposal*, no mutation.

    Inochi Creator `reparent_node` itself may have other semantics; a caller
    must still validate the actual live scene graph after a reparent.
    """
    if node_guid==new_parent_guid:
        raise ContractError('cannot parent node to itself')
    if any(n['guid']==node_guid for n in lineage(document,new_parent_guid)):
        raise ContractError('reparenting would create a cycle')
    old=world_matrix(document,node_guid)
    par=world_matrix(document,new_parent_guid)
    m=_matmul(_inverse(par),old)
    a,b,c=m[0];d,e,f=m[1]
    sx=math.hypot(a,d)
    if sx<1e-10:raise ContractError('singular reparent scale')
    theta=math.atan2(d,a)
    sy=(a*e-b*d)/sx
    if abs(sy)<1e-10:raise ContractError('singular reparent Y scale')
    reconstructed=local_matrix({'trans':[c,f,0.], 'rot':[0,0,theta], 'scale':[sx,sy]})
    if any(abs(m[i][j]-reconstructed[i][j])>1e-7 for i in range(2) for j in range(3)):
        raise ContractError('sheared frame; Creator-native transform required')
    return {'node_guid':node_guid,'new_parent_guid':new_parent_guid,
            'proposed_translation':[c,f,0.], 'proposed_rotation_rad':[0.,0.,theta],
            'proposed_scale':[sx,sy], 'preserve_world_in_plan':True,
            'applied_to_model':False,'creator_reparent_verified':False}
