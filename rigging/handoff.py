"""Read-only, lossless-on-demand manual authoring context for Inochi2D INP1.

The summaries are index/identity manifests, not speculative rig data. Actual
vertex offsets are retrieved by an explicit keyform + bounded vertex slice.
No mesh, bindings, artwork or source bytes are modified by this module.
"""
from __future__ import annotations

import hashlib
import json
import math
from typing import Any

from native.inp08 import validate_mesh, FormatError
from .contracts import ContractError, lineage, locate, mesh_fingerprint, validate_manifest
from .spaces import pivot_handoff


class HandoffError(ValueError):
    pass


def _uid(obj: dict) -> str:
    return str(obj.get('guid', obj.get('uuid', '')))


def _finite_number(value: Any) -> bool:
    return type(value) in (int, float) and math.isfinite(value)


def _axes(param: dict) -> list[list[float]]:
    axes = param.get('axis_points')
    if not isinstance(axes, list) or len(axes) != 2 or any(
        not isinstance(axis, list) or not axis or any(not _finite_number(x) for x in axis)
        for axis in axes
    ):
        raise HandoffError(f"parameter {_uid(param)} has incomplete or non-finite axis_points")
    if any(any(axis[i] >= axis[i + 1] for i in range(len(axis) - 1)) for axis in axes):
        raise HandoffError(f"parameter {_uid(param)} has non-increasing axis_points")
    return axes


def _bindings_for(document: dict, node_guid: str):
    if not isinstance(document.get('param', []), list):
        raise HandoffError('parameter list malformed')
    param_guids: set[str] = set()
    for param in document.get('param', []):
        if not isinstance(param, dict):
            raise HandoffError('parameter entry malformed')
        guid = _uid(param)
        if not guid:
            raise HandoffError('parameter GUID missing')
        if guid in param_guids:
            raise HandoffError(f'duplicate parameter GUID {guid}')
        param_guids.add(guid)
        bindings = param.get('bindings', [])
        if not isinstance(bindings, list):
            raise HandoffError(f'parameter {guid} bindings malformed')
        for index, bind in enumerate(bindings):
            if not isinstance(bind, dict):
                raise HandoffError(f'parameter {guid} binding malformed')
            if str(bind.get('node', '')) == node_guid:
                yield param, bind, index


def _grid(param: dict, bind: dict, vertex_count: int | None = None) -> dict:
    axes = _axes(param)
    values, is_set = bind.get('values'), bind.get('isSet')
    if not isinstance(values, list) or not isinstance(is_set, list):
        raise HandoffError('binding values/isSet grids missing')
    nx, ny = len(axes[0]), len(axes[1])
    if len(values) != nx or len(is_set) != nx:
        raise HandoffError('binding X grid does not match parameter axis')
    for x in range(nx):
        if not isinstance(values[x], list) or len(values[x]) != ny or not isinstance(is_set[x], list) or len(is_set[x]) != ny:
            raise HandoffError('binding Y grid does not match parameter axis')
        for y in range(ny):
            if type(is_set[x][y]) is not bool:
                raise HandoffError('isSet grid must contain booleans')
            if bind.get('param_name') == 'deform':
                v = values[x][y]
                if not isinstance(v, list) or vertex_count is None or len(v) != vertex_count:
                    raise HandoffError(f'deformation vector count differs from neutral mesh [{x},{y}]')
                if any(not isinstance(row, list) or len(row) != 2 or any(not _finite_number(z) for z in row) for row in v):
                    raise HandoffError(f'invalid deform offsets [{x},{y}]')
            elif is_set[x][y]:
                # Unknown properties intentionally remain opaque; never claim their
                # arrays represent vertex offsets.
                if values[x][y] is None:
                    raise HandoffError('authored scalar binding key is null')
    return {'nx': nx, 'ny': ny, 'authored_key_count': sum(sum(row) for row in is_set),
            'authored_key_indices': [[x, y] for x in range(nx) for y in range(ny) if is_set[x][y]],
            'axis_points': axes}


def manual_handoff(document: dict, model_raw: bytes, node_guid: str, *, anchors: dict | None = None) -> dict:
    """Full exact identity/provenance and all rig dependency references for one node.

    Unknown serialized fields are advertised as such; numerical pivot location
    does not purport to include active param bindings or physics evaluation.
    """
    if not isinstance(node_guid, str) or not node_guid:
        raise HandoffError('node_guid is required')
    path, node, parent = locate(document, node_guid)
    children = node.get('children', [])
    if not isinstance(children, list):
        raise HandoffError('invalid child node list')
    mesh_data = validate_mesh(node, path)
    mesh = node.get('mesh') if mesh_data else None
    bindings = []
    for param, bind, bind_index in _bindings_for(document, node_guid):
        prop = bind.get('param_name')
        entry = {
            'parameter_guid': _uid(param), 'parameter_name': param.get('name'),
            'binding_index': bind_index, 'property': prop,
            'interpolation': bind.get('interpolate_mode'),
            'binding_raw_fields': sorted(bind),
        }
        info = _grid(param, bind, len(mesh_data['neutral']) if mesh_data else None)
        entry.update(info)
        entry['vertex_offsets_available'] = prop == 'deform' and mesh_data is not None
        bindings.append(entry)
    raw_fields = {
        'textures': node.get('textures'), 'masked_by': node.get('masked_by'),
        'mask_mode': node.get('mask_mode'), 'mask_threshold': node.get('mask_threshold'),
        'blend_mode': node.get('blend_mode'), 'opacity': node.get('opacity'),
        'tint': node.get('tint'), 'screenTint': node.get('screenTint'),
        'emissionStrength': node.get('emissionStrength'),
        'origin': mesh.get('origin') if mesh else None,
    }
    snapshot = {
        'format': 'inochi-ai-rigging.manual-handoff.v1',
        'source_sha256': hashlib.sha256(model_raw).hexdigest(),
        'format_version': document.get('meta', {}).get('version'),
        'identity': {'node_guid': node_guid, 'node_path': path, 'type': node.get('type'),
                     'parent_guid': _uid(parent) if parent else None,
                     'children': [_uid(child) for child in children]},
        'node_transform_raw': node.get('transform'),
        'lockToRoot': node.get('lockToRoot', False),
        'zsort_raw': node.get('zsort'),
        'ancestor_chain': lineage(document, node_guid),
        'mesh': None if mesh is None else {
            'sha256': mesh_fingerprint(mesh),
            'vertex_count': len(mesh_data['neutral']),
            'triangle_count': len(mesh_data['triangles']),
            'uv_count': len(mesh['uvs']),
            'bounds_mesh_local': [
                min(v[0] for v in mesh_data['neutral']), min(v[1] for v in mesh_data['neutral']),
                max(v[0] for v in mesh_data['neutral']), max(v[1] for v in mesh_data['neutral'])],
            'raw_mesh_fields': sorted(mesh),
            'full_geometry': 'Use rig_binding_vertex_slice for bound vertex offsets; read source file for neutral verts/UVs/indices.',
        },
        'raw_part_fields': raw_fields,
        'bindings': bindings,
        'parameters_binding_count': len(bindings),
        'explicit_anchor_contract': 'provided_and_validated' if anchors is not None else 'NOT_PROVIDED',
        'missing_live_evidence': [
            'actual_creator_evaluated_world_transform', 'parameter_deformer_composition',
            'active_physics_state', 'texture_canvas_pixel_mapping',
            'rendered_occlusion_and_mask_effects', 'Creator_edit_history',
        ],
        'guarantees': {'source_modified': False, 'node_pivot_moved': False,
                       'world_pivot_claimed_without_Creator': False,
                       'mask_properties_are_raw_not_render_verified': True},
    }
    if anchors is not None:
        a = validate_manifest(document, model_raw, anchors)
        selected = [item for item in a['anchors'] if item['node_guid'] == node_guid]
        if not selected:
            raise HandoffError('manifest contains no anchor for requested node')
        # World transform here is a PLANAR ESTIMATE that may be unsupported; do
        # not replace the entire report with misleading coordinates on failure.
        located = []
        for item in selected:
            try:
                located.append(pivot_handoff(document, item))
            except ContractError as exc:
                located.append({'node_guid': node_guid, 'label': item['label'],
                                'kind': item['kind'], 'landmark_mesh_local': item['local'],
                                'landmark_world': None, 'world_estimate_status': 'UNSUPPORTED',
                                'reason': str(exc), 'apply_policy': 'PLAN_ONLY'})
        snapshot['anchors'] = located
    return snapshot


def binding_vertex_slice(document: dict, model_raw: bytes, node_guid: str,
                         parameter_guid: str, binding_index: int, key_index: list[int],
                         start_vertex: int = 0, limit: int = 256) -> dict:
    """Read exact stored per-vertex offsets from one *authored* or empty keyform.

    Requires stable GUID and binding-index; never look up by parameter display
    name or silently collapse 2D keys to x only. Bounded for agent context.
    """
    if type(binding_index) is not int or binding_index < 0:
        raise HandoffError('binding_index must be nonnegative integer')
    if not isinstance(key_index, list) or len(key_index) != 2 or any(type(i) is not int for i in key_index):
        raise HandoffError('key_index must be [x,y] integer pair')
    if type(start_vertex) is not int or start_vertex < 0 or type(limit) is not int or not 1 <= limit <= 4096:
        raise HandoffError('start_vertex >=0 and 1<=limit<=4096 required')
    path, node, _ = locate(document, node_guid)
    mesh = validate_mesh(node, path)
    if mesh is None:
        raise HandoffError('requested node has no mesh')
    found = [(p, b) for p,b,i in _bindings_for(document,node_guid)
             if _uid(p) == parameter_guid and i == binding_index]
    if len(found) != 1:
        raise HandoffError('parameter GUID / binding index not found or ambiguous')
    param, bind = found[0]
    if bind.get('param_name') != 'deform':
        raise HandoffError('binding is not a vertex deform binding')
    info = _grid(param, bind, len(mesh['neutral']))
    x, y = key_index
    if x >= info['nx'] or y >= info['ny']:
        raise HandoffError('key_index outside parameter axis range')
    if start_vertex > len(mesh['neutral']):
        raise HandoffError('start_vertex beyond vertex count')
    stop = min(start_vertex + limit, len(mesh['neutral']))
    rows = bind['values'][x][y][start_vertex:stop]
    return {
        'format': 'inochi-ai-rigging.vertex-slice.v1',
        'source_sha256': hashlib.sha256(model_raw).hexdigest(),
        'node_guid': node_guid, 'mesh_sha256': mesh_fingerprint(node['mesh']),
        'parameter_guid': parameter_guid, 'parameter_name': param.get('name'),
        'binding_index': binding_index, 'key_index': key_index,
        'key_coordinates': [info['axis_points'][0][x], info['axis_points'][1][y]],
        'is_authored': bind['isSet'][x][y],
        'start_vertex': start_vertex, 'next_vertex': stop if stop < len(mesh['neutral']) else None,
        'total_vertices': len(mesh['neutral']),
        'vertices': [{'index': index, 'neutral': mesh['neutral'][index],
                      'uv': node['mesh']['uvs'][index], 'offset': rows[index - start_vertex]}
                     for index in range(start_vertex, stop)],
        'model_modified': False,
    }
