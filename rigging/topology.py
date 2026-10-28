"""Lossless-with-respect-to-linear-interpolation mesh subdivision for INP 0.8.

All existing authored and unauthored deformation keyform vectors are rebased.
This increases editing resolution without pretending to improve original art quality.
Unknown mesh fields, ambiguous binding targets or unsupported per-vertex data fail closed.
"""
from __future__ import annotations
import copy
import math
from native.inp08 import validate_mesh
from native.local_geometry import area
from .contracts import ContractError, locate, mesh_fingerprint

class TopologyError(ValueError):
    pass


def _offset_grid(binding: dict, count: int) -> list:
    values = binding.get('values')
    flags = binding.get('isSet')
    if not isinstance(values, list) or not isinstance(flags, list) or len(values) != len(flags):
        raise TopologyError('invalid binding values/isSet X dimensions')
    for x, column in enumerate(values):
        if not isinstance(column, list) or not isinstance(flags[x], list) or len(column) != len(flags[x]):
            raise TopologyError('invalid binding Y dimensions')
        for y, vectors in enumerate(column):
            if type(flags[x][y]) is not bool or not isinstance(vectors,list) or len(vectors) != count:
                raise TopologyError(f'invalid deformation keyform grid [{x},{y}]')
            if any(not isinstance(v,(list,tuple)) or len(v)!=2 or any(type(n) not in (int,float) or not math.isfinite(n) for n in v) for v in vectors):
                raise TopologyError(f'invalid vertex offsets [{x},{y}]')
    return values


def subdivide_once(document: dict, node_guid: str, *, expected_mesh_sha256: str) -> dict:
    """1-to-4 shared-edge triangle subdivision with exact displacement/UV rebasing.

    In-place on a *disposable clone*. Call through an atomic transaction and never
    mutate user source directly. Mask/texture references, node GUID and binding
    keypoint flags remain untouched. Linear barycentric interpolation is preserved.
    """
    try:
        path,node,_ = locate(document,node_guid)
    except ContractError as exc:
        raise TopologyError(str(exc)) from exc
    mesh = node.get('mesh')
    if not isinstance(mesh,dict):
        raise TopologyError('selected node is not a mesh')
    if mesh_fingerprint(mesh) != expected_mesh_sha256:
        raise TopologyError('stale mesh SHA-256')
    if set(mesh)-{'verts','uvs','indices','origin'}:
        raise TopologyError('unknown mesh fields may contain vertex-indexed data; refuse retopology')
    old = validate_mesh(node,path)
    if old is None:
        raise TopologyError('invalid target mesh')
    verts,uvs,indices = mesh['verts'],mesh['uvs'],mesh['indices']
    n=len(verts)
    triangles=old['triangles']
    for tri in triangles:
        if abs(area(*(verts[i] for i in tri))) < 1e-10:
            raise TopologyError('degenerate neutral triangle; refuse refinement')
    offsets=[]
    params=document.get('param',[])
    if not isinstance(params,list): raise TopologyError('invalid parameter structure')
    seen=set()
    for param in params:
        if not isinstance(param,dict):raise TopologyError('invalid parameter')
        bindings=param.get('bindings',[])
        if not isinstance(bindings,list):raise TopologyError('invalid binding list')
        for binding in bindings:
            if not isinstance(binding,dict):raise TopologyError('invalid binding')
            if str(binding.get('node','')) != node_guid:continue
            prop=binding.get('param_name')
            if prop=='deform':
                key=(str(param.get('guid','')),prop)
                if key in seen:raise TopologyError('ambiguous multiple deform bindings for same parameter')
                seen.add(key)
                _offset_grid(binding,n)
                axes=param.get('axis_points')
                if not isinstance(axes,list) or len(axes)!=2 or len(axes[0])!=len(binding['values']) or any(len(column)!=len(axes[1]) for column in binding['values']):
                    raise TopologyError('binding dimensions disagree with parameter axis')
                offsets.append(binding)
            elif prop not in ('opacity','zSort','transform.t.x','transform.t.y','transform.t.z',
                              'transform.r.x','transform.r.y','transform.r.z','transform.s.x','transform.s.y'):
                raise TopologyError(f'unknown potentially vertex-indexed binding property {prop!r}')
    new_verts=[list(v) for v in verts]
    new_uvs=[list(v) for v in uvs]
    new_indices=[]
    midpoint={}
    def mid(a,b):
        key=(min(a,b),max(a,b))
        if key not in midpoint:
            midpoint[key]=len(new_verts)
            new_verts.append([(verts[a][k]+verts[b][k])/2 for k in range(2)])
            new_uvs.append([(uvs[a][k]+uvs[b][k])/2 for k in range(2)])
        return midpoint[key]
    for a,b,c in triangles:
        ab=mid(a,b);bc=mid(b,c);ca=mid(c,a)
        for t in [(a,ab,ca),(ab,b,bc),(ca,bc,c),(ab,bc,ca)]:
            new_indices.extend(t)
    # Every keyframe inherits the same shared edge topology; original vertex
    # offsets and original isSet grid are preserved exactly.
    for binding in offsets:
        for column in binding['values']:
            for vec in column:
                for (a,b), new_index in midpoint.items():
                    if len(vec)!=new_index:
                        raise TopologyError('midpoint storage index inconsistent')
                    vec.append([(vec[a][k]+vec[b][k])/2 for k in range(2)])
    mesh['verts'],mesh['uvs'],mesh['indices'] = new_verts,new_uvs,new_indices
    return {'node_guid':node_guid, 'mesh_sha256_before':expected_mesh_sha256,
            'mesh_sha256_after':mesh_fingerprint(mesh),
            'vertices_before':n,'vertices_after':len(new_verts),
            'triangles_before':len(triangles),'triangles_after':len(new_indices)//3,
            'shared_midpoint_count':len(midpoint),'rebased_deform_bindings':len(offsets),
            'quality_claim':'Editing resolution increased. Visual quality not inferred.'}
