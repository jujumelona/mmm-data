"""Conservative Inochi2D INP1 (.inp/.inx) JSON payload inspector and patcher.

Implements only documented 0.8.x TRNSRTS\\0 format. It preserves texture and
extended vendor sections byte-for-byte and does not synthesize unknown data.
INP2 is intentionally refused. No third-party libraries.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import math
import os
from pathlib import Path
import struct
import sys
import tempfile

MAGIC = b"TRNSRTS\0"
MAX_MODEL_JSON = 128 * 1024 * 1024
MAX_TEXTURES = 16384


class FormatError(ValueError):
    pass


def _u32(data: bytes, offset: int) -> tuple[int, int]:
    if offset + 4 > len(data):
        raise FormatError(f"truncated uint32 at byte {offset}")
    return struct.unpack_from(">I", data, offset)[0], offset + 4


def parse(blob: bytes) -> tuple[dict, bytes, bytes]:
    if blob.startswith(b"TRNSRTS2"):
        raise FormatError("INP2 (0.9+) is not compatible with INP1. Use matching official SDK.")
    if not blob.startswith(MAGIC):
        raise FormatError("unsupported file; expected Inochi2D INP1 TRNSRTS\\0")
    length, p = _u32(blob, 8)
    if length <= 0 or length > MAX_MODEL_JSON:
        raise FormatError("invalid or oversized puppet JSON payload")
    end = p + length
    if end + 12 > len(blob):
        raise FormatError("truncated JSON or texture section")
    original_json = blob[p:end]
    if blob[end:end + 8] != b"TEX_SECT":
        raise FormatError("texture section header missing")
    p = end + 8
    count, p = _u32(blob, p)
    if count > MAX_TEXTURES:
        raise FormatError("implausible texture slot count")
    for _ in range(count):
        n, p = _u32(blob, p)
        if p + n + 1 > len(blob):
            raise FormatError("truncated texture payload")
        texture_type = blob[p]
        if texture_type not in (0, 1, 2, 0xFF):
            raise FormatError(f"unknown texture type {texture_type}; aborting")
        p += 1 + n
    if p < len(blob):
        if blob[p:p + 8] != b"EXT_SECT":
            raise FormatError(f"unknown data after textures at {p}; aborting rather than discarding")
        p += 8
        ext_count, p = _u32(blob, p)
        if ext_count > MAX_TEXTURES:
            raise FormatError("implausible extension count")
        for _ in range(ext_count):
            n, p = _u32(blob, p)
            if p + n > len(blob):
                raise FormatError("truncated extension vendor name")
            p += n
            n, p = _u32(blob, p)
            if p + n > len(blob):
                raise FormatError("truncated extension payload")
            p += n
        if p != len(blob):
            raise FormatError("extra unknown bytes after extension data")
    try:
        data = json.loads(original_json.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError) as e:
        raise FormatError(f"malformed puppet JSON: {e}") from e
    if not isinstance(data, dict) or not isinstance(data.get("nodes"), dict):
        raise FormatError("puppet JSON missing node hierarchy")
    return data, original_json, blob[end:]


def encode(document: dict, tail: bytes) -> bytes:
    payload = json.dumps(document, ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode("utf-8")
    if len(payload) > MAX_MODEL_JSON:
        raise FormatError("updated payload oversized")
    return MAGIC + struct.pack(">I", len(payload)) + payload + tail


def walk_nodes(root: dict):
    stack = [(root, "Root")]
    while stack:
        node, path = stack.pop()
        if not isinstance(node, dict):
            continue
        name = node.get("name", "(unnamed)")
        current = f"{path}/{name}"
        yield current, node
        for child in reversed(node.get("children", [])):
            if isinstance(child, dict):
                stack.append((child, current))


def _coords(pts):
    return (isinstance(pts, list) and all(
        isinstance(v, list) and len(v) == 2 and all(type(x) in (int,float) and math.isfinite(x) for x in v)
        for v in pts))


def _triplets(indices):
    return [indices[i:i + 3] for i in range(0, len(indices), 3)]


def validate_mesh(node, name):
    mesh = node.get("mesh")
    if not isinstance(mesh, dict):
        return None
    verts, indices, uvs = mesh.get("verts"), mesh.get("indices"), mesh.get("uvs")
    if not _coords(verts) or not verts:
        raise FormatError(f"{name}: invalid mesh verts")
    if not _coords(uvs) or len(uvs) != len(verts):
        raise FormatError(f"{name}: mismatched mesh UVs")
    if not isinstance(indices, list) or len(indices) % 3 or not indices:
        raise FormatError(f"{name}: invalid triangle indices")
    if any(type(x) is not int or x < 0 or x >= len(verts) for x in indices):
        raise FormatError(f"{name}: bad triangle index")
    return {"neutral": verts, "triangles": _triplets(indices)}


def inspect(document):
    nodes = []
    node_by_guid = {}
    for path, node in walk_nodes(document["nodes"]):
        guid = str(node.get("uuid", node.get("guid", "")))
        if guid:
            if guid in node_by_guid:
                raise FormatError(f"duplicate node GUID: {guid}")
            node_by_guid[guid] = (path, node)
        mesh = validate_mesh(node, path)
        if mesh:
            nodes.append({"path":path,"name":node.get("name"),"guid":guid,"vertices":len(mesh["neutral"]),"triangles":len(mesh["triangles"])})
    params = []
    for item in document.get("param", []):
        if not isinstance(item, dict):
            raise FormatError("invalid parameter entry")
        bindings = item.get("bindings", [])
        info = {"name":item.get("name"),"guid":item.get("guid"),"axis_points":item.get("axis_points"),"bindings":[]}
        for binding in bindings:
            ref = str(binding.get("node", ""))
            info["bindings"].append({"node":ref,"node_path":node_by_guid.get(ref, (None,))[0],"param_name":binding.get("param_name")})
        params.append(info)
    return {"model_name":document.get("meta",{}).get("name"),"mesh_nodes":nodes,"parameters":params,"animations":list(document.get("animations",{}))}


def extract_samples(document):
    by_guid = {}
    samples = []
    for path, node in walk_nodes(document["nodes"]):
        guid = str(node.get("uuid", node.get("guid", "")))
        mesh = validate_mesh(node, path)
        if not mesh:
            continue
        by_guid[guid] = (path, mesh)
        samples.append({"part":path,"pose":"neutral","neutral":mesh["neutral"],"posed":mesh["neutral"],"triangles":mesh["triangles"]})
    errors = []
    for parameter in document.get("param", []):
        pname = parameter.get("name")
        axes = parameter.get("axis_points", [])
        for binding in parameter.get("bindings", []):
            if binding.get("param_name") != "deform":
                continue
            ref = str(binding.get("node", ""))
            if ref not in by_guid:
                errors.append({"parameter":pname,"node":ref,"issue":"deform binding target not found"})
                continue
            path, mesh = by_guid[ref]
            vals = binding.get("values")
            if not isinstance(vals, list) or len(vals) != len(axes[0]):
                errors.append({"parameter":pname,"node":ref,"issue":"invalid x keyform dimensions"})
                continue
            for ix, row in enumerate(vals):
                if not isinstance(row, list) or len(row) != len(axes[1]):
                    errors.append({"parameter":pname,"node":ref,"issue":"invalid y keyform dimensions"})
                    continue
                for iy, offsets in enumerate(row):
                    if not _coords(offsets) or len(offsets) != len(mesh["neutral"]):
                        errors.append({"parameter":pname,"node":ref,"issue":f"invalid deformation offsets [{ix},{iy}]"})
                        continue
                    posed=[[a[0]+b[0],a[1]+b[1]] for a,b in zip(mesh["neutral"],offsets)]
                    samples.append({"part":path,"pose":f"{pname} [{ix},{iy}]", "axis":{"x":axes[0][ix],"y":axes[1][iy]},"neutral":mesh["neutral"],"posed":posed,"triangles":mesh["triangles"]})
    return {"samples":samples,"warnings":errors,"note":"Individual parameter deformation only; does not include hierarchical deformer composition, physics or camera transforms."}


def _binding(document, param_name: str, node_guid: str):
    matches=[]
    for param in document.get("param", []):
        if param.get("name")!=param_name:continue
        for binding in param.get("bindings", []):
            if binding.get("node") == node_guid and binding.get("param_name") == "deform":
                matches.append((param,binding))
    if len(matches)!=1:
        raise FormatError(f"expected exactly one deformation binding for {param_name}/{node_guid}, got {len(matches)}")
    return matches[0]


def apply_keyform(document, patch):
    """Safe patch: set one EXISTING deform binding keyform, never change topology.

    Explicit opt-in can overwrite a pre-existing key only if source checksum
    matches, geometry passes and caller specifies --allow-replace.
    """
    param,binding=_binding(document,patch["parameter"],patch["node_guid"])
    axes=param.get("axis_points",[])
    if len(axes)!=2 or len(axes[0])!=len(binding["values"]) or len(axes[1])<1:
        raise FormatError("unsupported binding axes")
    ix,iy=patch["key_index"]
    if not (type(ix) is type(iy) is int and 0<=ix<len(axes[0]) and 0<=iy<len(axes[1])):
        raise FormatError("key_index is out of range")
    if not isinstance(binding.get("isSet"),list) or len(binding["isSet"])!=len(axes[0]):
        raise FormatError("binding isSet shape does not match axes")
    for row in binding["isSet"]:
        if not isinstance(row,list) or len(row)!=len(axes[1]):
            raise FormatError("binding isSet dimensions inconsistent")
    if binding["isSet"][ix][iy] and not patch.get("allow_replace",False):
        raise FormatError("existing authored keyform; refusal unless allow_replace is true")
    vertex_offsets=patch["vertex_offsets"]
    refs=[(n,node) for n,node in walk_nodes(document["nodes"]) if str(node.get("uuid",node.get("guid","")))==patch["node_guid"]]
    if len(refs)!=1:
        raise FormatError("target node missing or ambiguous")
    mesh=validate_mesh(refs[0][1],refs[0][0])
    if mesh is None or not _coords(vertex_offsets) or len(vertex_offsets)!=len(mesh["neutral"]):
        raise FormatError("vertex_offsets must be finite vec2 array with same count as mesh")
    if not patch.get("allow_unsafe",False):
        try:
            from .local_geometry import geometry_errors
        except ImportError:  # direct CLI invocation
            from local_geometry import geometry_errors
        bad=geometry_errors(mesh["neutral"], vertex_offsets, mesh["triangles"])
        if bad:
            raise FormatError(f"keyform rejected for {bad} unsafe triangles")
    # refuse even zero-offset replacement without explicit request
    binding["values"][ix][iy]=vertex_offsets
    binding["isSet"][ix][iy]=True
    return {"parameter":param["name"],"node":patch["node_guid"],"key_index":[ix,iy],"changed_vertices":len(vertex_offsets)}


def read_model(path: Path):
    return parse(path.read_bytes())


def atomic_write(path: Path, payload: bytes):
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        raise FormatError(f"refusing to overwrite existing file: {path}")
    with tempfile.NamedTemporaryFile(dir=path.parent,delete=False) as t:
        t.write(payload)
        name=t.name
    try:
        os.replace(name,path)
    finally:
        if os.path.exists(name):os.unlink(name)


def main():
    parser=argparse.ArgumentParser(description="Inochi2D 0.8 INP1 inspector and strictly gated keyform writer")
    parser.add_argument("command",choices=["inspect","extract","roundtrip","patch-keyform"])
    parser.add_argument("model",type=Path)
    parser.add_argument("--output",type=Path)
    parser.add_argument("--patch",type=Path)
    args=parser.parse_args()
    try:
        doc,raw,tail=read_model(args.model)
        if args.command=="inspect":
            out=inspect(doc)
            out["source_sha256"]=hashlib.sha256(args.model.read_bytes()).hexdigest()
            print(json.dumps(out,ensure_ascii=False,indent=2))
        elif args.command=="extract":
            out=extract_samples(doc)
            if args.output:atomic_write(args.output,json.dumps(out,ensure_ascii=False,indent=2).encode())
            else:print(json.dumps(out,ensure_ascii=False,indent=2))
        elif args.command=="roundtrip":
            if not args.output:raise FormatError("--output required")
            atomic_write(args.output,MAGIC+struct.pack(">I",len(raw))+raw+tail)
            if args.model.read_bytes()!=args.output.read_bytes():raise FormatError("roundtrip byte check failed")
            print(json.dumps({"byte_identical":True,"output":str(args.output)}))
        else:
            if not args.output or not args.patch:raise FormatError("--patch and --output required")
            patch=json.loads(args.patch.read_text(encoding="utf-8"))
            if patch.get("source_sha256")!=hashlib.sha256(args.model.read_bytes()).hexdigest():
                raise FormatError("source_sha256 mismatched: refusing stale patch")
            clone=copy.deepcopy(doc)
            change=apply_keyform(clone,patch)
            data=encode(clone,tail)
            validated,_,validated_tail=parse(data)
            if validated_tail!=tail or validated!=clone:raise FormatError("serialized verification failed")
            atomic_write(args.output,data)
            print(json.dumps({"changed":change,"output":str(args.output),"texture_tail_unchanged":True}))
    except (FormatError,KeyError,TypeError,ValueError,OSError) as exc:
        print(f"ERROR: {exc}",file=sys.stderr)
        sys.exit(2)


if __name__=="__main__":main()
