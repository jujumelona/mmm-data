"""Offline structural pose gates. NOT a substitute for real Creator rendering.

Individual deformation keyforms and *additive approximation* combinations are
inspected for invert/collapse/stretch. Upstream Inochi2D may compose differently;
combo findings are diagnostic and never claimed as an exact SDK render.
"""
from __future__ import annotations
from collections import defaultdict
import itertools
from native.inp08 import walk_nodes,validate_mesh
from native.local_geometry import area,geometry_errors
from .topology import _offset_grid, TopologyError

class QualityError(ValueError): pass


def inspect_geometry(document:dict, *, include_pairs:bool=True) -> dict:
    nodes={}
    for path,node in walk_nodes(document['nodes']):
        mesh=validate_mesh(node,path)
        if mesh:
            guid=str(node.get('guid',node.get('uuid','')))
            if not guid or guid in nodes:
                raise QualityError('missing or duplicate drawable node GUID')
            nodes[guid]=(path,mesh)
    per_node=defaultdict(list)
    cases=[]
    for guid,(path,mesh) in nodes.items():
        neutral=mesh['neutral'];tri=mesh['triangles']
        if any(abs(area(*(neutral[i] for i in t)))<1e-10 for t in tri):
            raise QualityError(f'{path}: invalid neutral triangulation')
    for param in document.get('param',[]):
        if not isinstance(param,dict):raise QualityError('invalid parameter')
        axes=param.get('axis_points')
        for bind in param.get('bindings',[]):
            if bind.get('param_name')!='deform':continue
            guid=str(bind.get('node',''))
            if guid not in nodes:
                raise QualityError('deform binding missing drawable node')
            path,mesh=nodes[guid]
            vectors=_offset_grid(bind,len(mesh['neutral']))
            if not isinstance(axes,list) or len(axes)!=2 or len(vectors)!=len(axes[0]) or any(len(v)!=len(axes[1]) for v in vectors):
                raise QualityError('invalid binding axis lengths')
            for x,column in enumerate(vectors):
                for y,v in enumerate(column):
                    if not bind['isSet'][x][y]:continue
                    bad=geometry_errors(mesh['neutral'],v,mesh['triangles'])
                    cases.append({'node_guid':guid,'parameter_guid':str(param.get('guid','')),
                                  'key_index':[x,y],'invalid_triangles':bad})
                    # Don't infer multi-axis SDK interpolation from independent flags.
                    per_node[guid].append((str(param.get('guid','')),[x,y],v))
    pair_cases=[]
    if include_pairs:
        for guid,group in per_node.items():
            path,mesh=nodes[guid]
            for (pa,ka,va),(pb,kb,vb) in itertools.combinations(group,2):
                if pa==pb:continue
                # Basic neutral + additive pair proxy only; exhaustive authored-key
                # cross product, no arbitrary numeric cap.
                combined=[[a[0]+b[0],a[1]+b[1]] for a,b in zip(va,vb)]
                bad=geometry_errors(mesh['neutral'],combined,mesh['triangles'])
                pair_cases.append({'node_guid':guid,'parameters':[pa,pb],
                                   'keys':[ka,kb],'invalid_triangles':bad})
    return {'engine':'offline-geometry-only','rendered':False,
            'individual_key_count':len(cases),'pair_count':len(pair_cases),
            'individual_failures':[x for x in cases if x['invalid_triangles']],
            'additive_proxy_pair_failures':[x for x in pair_cases if x['invalid_triangles']],
            'individual_geometry_pass':all(not x['invalid_triangles'] for x in cases),
            'additive_proxy_pair_pass':all(not x['invalid_triangles'] for x in pair_cases),
            'warning':'Independent and additive-pair geometry only; no scene-graph, rendered pixel, physical, or perceptual pass claimed.'}
