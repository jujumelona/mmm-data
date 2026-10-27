"""Explicit, auditable landmark/pivot contracts for existing INP1 meshes.

A point is never accepted without both a coordinate-space identifier and
source model + node mesh fingerprints. Image pixels and model units are not
silently assumed to be identical. These contracts are *intent records*;
writing a pivot transform to the Inochi scene graph is NOT implemented here.
"""
from __future__ import annotations
import hashlib
import json
import math
from dataclasses import dataclass
from typing import Any

FORMAT = "inochi-ai-rigging.anchors.v1"

class ContractError(ValueError):
    pass


def finite_pair(value: Any, label: str) -> tuple[float, float]:
    if not isinstance(value, (tuple, list)) or len(value) != 2 or any(
        type(x) not in (float, int) or not math.isfinite(x) for x in value
    ):
        raise ContractError(f"{label} must be exactly 2 finite numbers")
    return float(value[0]), float(value[1])


def mesh_fingerprint(mesh: dict) -> str:
    # Source-coordinate fingerprint; order is meaningful and cannot be sorted.
    if not isinstance(mesh, dict):
        raise ContractError("mesh must be an object")
    payload = {k: mesh.get(k) for k in ("verts", "uvs", "indices")}
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(',', ':'),
                                     allow_nan=False).encode()).hexdigest()


def locate(document: dict, guid: str):
    from native.inp08 import walk_nodes
    matches = [(path, node, parent) for path, node, parent in _walk_parent(document['nodes'])
               if str(node.get('guid', node.get('uuid', ''))) == guid]
    if len(matches) != 1:
        raise ContractError(f"node GUID missing or ambiguous: {guid}")
    return matches[0]


def _walk_parent(root):
    stack = [(root, 'Root', None)]
    while stack:
        node, path, parent = stack.pop()
        if not isinstance(node, dict):
            raise ContractError("invalid node in hierarchy")
        here = f"{path}/{node.get('name','unnamed')}"
        yield here, node, parent
        for child in reversed(node.get('children', []) or []):
            stack.append((child, here, node))


def _guid(n):
    return str(n.get('guid', n.get('uuid', ''))) if n else None


def lineage(document: dict, guid: str) -> list[dict]:
    _, node, parent = locate(document, guid)
    target = node
    chain = []
    # GUIDs are never interchangeable with human-readable node names.
    def recurse(n, parents):
        if n is target:
            for part in parents + [n]:
                chain.append({"guid": _guid(part), "name": part.get("name"),
                              "transform": part.get("transform"),
                              "lockToRoot": part.get("lockToRoot", False),
                              "zsort": part.get("zsort")})
            return True
        for c in n.get('children', []) or []:
            if recurse(c, parents + [n]):
                return True
        return False
    if not recurse(document['nodes'], []):
        raise ContractError("unreachable target")
    return chain


def lineage_fingerprint(document: dict, guid: str) -> str:
    return hashlib.sha256(json.dumps(lineage(document, guid), sort_keys=True,
                                     allow_nan=False, separators=(',', ':')).encode()).hexdigest()


def image_to_local(point_px, coordinates: dict) -> list[float]:
    """Translate a raw image pixel coordinate to mesh/node local model units.

    The editor/model's image placement must be measured by the caller; never
    infer unit scale, axis directions or canvas origin from a PNG filename.
    """
    px, py = finite_pair(point_px, 'point_px')
    if coordinates.get('from') != 'image_pixel_top_left_y_down' or coordinates.get('to') != 'mesh_local':
        raise ContractError("explicit image_pixel_top_left_y_down -> mesh_local contract required")
    ox, oy = finite_pair(coordinates.get('image_origin_px'), 'image_origin_px')
    mx, my = finite_pair(coordinates.get('local_origin'), 'local_origin')
    factor = coordinates.get('model_units_per_pixel')
    if type(factor) not in (float, int) or not math.isfinite(factor) or factor <= 0:
        raise ContractError('model_units_per_pixel must be positive and finite')
    axes = coordinates.get('axes')
    if axes not in ('x_right_y_up', 'x_right_y_down'):
        raise ContractError('axes must be declared, no inferred Y flip')
    sign = -1 if axes == 'x_right_y_up' else 1
    return [mx + (px-ox)*factor, my + (py-oy)*factor*sign]


def local_to_image(point_local, coordinates: dict) -> list[float]:
    lx, ly = finite_pair(point_local, 'point_local')
    # Re-validate in the exact same manner as the forward direction.
    image_to_local(coordinates.get('image_origin_px'), coordinates)
    ox, oy = coordinates['image_origin_px']
    mx, my = coordinates['local_origin']
    f = coordinates['model_units_per_pixel']
    sign = -1 if coordinates['axes'] == 'x_right_y_up' else 1
    return [ox+(lx-mx)/f, oy+sign*(ly-my)/f]


def validate_manifest(doc: dict, model_bytes: bytes, manifest: dict) -> dict:
    if manifest.get('format') != FORMAT:
        raise ContractError('unsupported manifest format')
    digest = hashlib.sha256(model_bytes).hexdigest()
    if manifest.get('source_sha256') != digest:
        raise ContractError('model SHA-256 mismatch; re-inspect and regenerate anchors')
    anchors = manifest.get('anchors')
    if not isinstance(anchors, list) or not anchors:
        raise ContractError('nonempty anchors required')
    accepted = []
    by_node = {}
    for a in anchors:
        if not isinstance(a, dict) or not isinstance(a.get('label'), str) or not a['label']:
            raise ContractError('every anchor needs a nonempty label')
        guid = a.get('node_guid')
        if not isinstance(guid, str) or not guid:
            raise ContractError('anchor node_guid must be a stable string')
        path, node, parent = locate(doc, guid)
        mesh = node.get('mesh')
        if not isinstance(mesh, dict):
            raise ContractError(f'{path} is not a drawable mesh')
        current_mesh = mesh_fingerprint(mesh)
        current_lineage = lineage_fingerprint(doc, guid)
        if a.get('mesh_sha256') != current_mesh or a.get('lineage_sha256') != current_lineage:
            raise ContractError(f'{path}: stale mesh, parent, or transform fingerprint')
        coord = a.get('coordinates')
        if not isinstance(coord, dict):
            raise ContractError('coordinate transform contract missing')
        local = image_to_local(a.get('point_px'), coord)
        expected = a.get('point_local')
        if expected is None or any(abs(x-y)>1e-5 for x,y in zip(local,finite_pair(expected, 'point_local'))):
            raise ContractError(f"{a['label']}: transferred pivot/landmark does not match pixel coordinate")
        # Never treat image-level origin as a rotational pivot by default.
        kind = a.get('kind')
        if kind not in ('landmark','rotation_center','joint_center','seam','occlusion_anchor','attachment'):
            raise ContractError('anchor kind must be explicit')
        accepted.append({'label':a['label'],'kind':kind,'node_guid':guid,'local':local,'path':path,
                         'parent_guid':_guid(parent)})
        key=(guid,a['label'])
        if key in by_node: raise ContractError(f'duplicate node+anchor label {key}')
        by_node[key]=True
    return {'valid': True, 'source_sha256':digest, 'anchors':accepted,
            'count':len(accepted), 'warning':'Landmarks/pivots validated as intent; no scene graph pivot transform was changed.'}


def make_anchor(doc: dict, model_bytes: bytes, node_guid: str, label: str, kind: str,
                point_px, coordinates: dict):
    _, node, _ = locate(doc, node_guid)
    if not isinstance(node.get('mesh'), dict):
        raise ContractError('target node is not a mesh')
    return {'label':label,'kind':kind,'node_guid':node_guid,'point_px':list(point_px),
            'point_local':image_to_local(point_px, coordinates),'coordinates':coordinates,
            'mesh_sha256':mesh_fingerprint(node['mesh']),
            'lineage_sha256':lineage_fingerprint(doc, node_guid)}
