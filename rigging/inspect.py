"""Read-only parser for Inochi2D 0.8 TRNSRTS containers.

Does not reinterpret model coordinates or modify original textures.
"""
from __future__ import annotations

from collections import Counter
import hashlib
import json
from pathlib import Path
import struct
from typing import Any

MAGIC = b"TRNSRTS\x00"
TEX = b"TEX_SECT"
EXT = b"EXT_SECT"


class InochiFormatError(ValueError):
    pass


def inspect_bytes(data: bytes) -> dict[str, Any]:
    if len(data) < 24 or data[:8] != MAGIC:
        raise InochiFormatError("Not a supported Inochi2D 0.8 TRNSRTS container")
    length = struct.unpack_from(">I", data, 8)[0]
    end = 12 + length
    if length < 2 or end + 12 > len(data):
        raise InochiFormatError("Invalid/truncated JSON payload")
    try:
        payload = json.loads(data[12:end].decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise InochiFormatError("Malformed model JSON") from exc
    if not isinstance(payload, dict):
        raise InochiFormatError("Model payload is not a JSON object")
    if data[end:end + 8] != TEX:
        raise InochiFormatError("Missing TEX_SECT")
    position = end + 8
    textures = struct.unpack_from(">I", data, position)[0]
    position += 4
    if textures > len(data) // 5:
        raise InochiFormatError("Implausible texture count")
    tex_encoding = Counter()
    for _ in range(textures):
        if position + 5 > len(data):
            raise InochiFormatError("Truncated texture header")
        n = struct.unpack_from(">I", data, position)[0]
        encoding = data[position + 4]
        position += 5
        if n > len(data) - position:
            raise InochiFormatError("Truncated texture data")
        tex_encoding[encoding] += 1
        position += n

    extension_count = 0
    if data[position:position + 8] == EXT:
        position += 8
        if position + 4 > len(data):
            raise InochiFormatError("Truncated extension header")
        extension_count = struct.unpack_from(">I", data, position)[0]
        position += 4
        if extension_count > len(data) // 8:
            raise InochiFormatError("Implausible extension count")
        for _ in range(extension_count):
            if position + 4 > len(data):
                raise InochiFormatError("Truncated extension name length")
            name_len = struct.unpack_from(">I", data, position)[0]
            position += 4
            if name_len > len(data) - position:
                raise InochiFormatError("Truncated extension name")
            position += name_len
            if position + 4 > len(data):
                raise InochiFormatError("Truncated extension body length")
            body_len = struct.unpack_from(">I", data, position)[0]
            position += 4
            if body_len > len(data) - position:
                raise InochiFormatError("Truncated extension body")
            position += body_len
    if position != len(data):
        raise InochiFormatError("Unexpected trailing bytes")
    nodes = Counter()
    vertices = 0
    triangles = 0
    def walk(node: Any) -> None:
        nonlocal vertices, triangles
        if not isinstance(node, dict):
            return
        nodes[str(node.get("type", "Node"))] += 1
        mesh = node.get("mesh")
        if isinstance(mesh, dict):
            vv = mesh.get("verts")
            ii = mesh.get("indices")
            if isinstance(vv, list):
                vertices += len(vv)
            if isinstance(ii, list):
                triangles += len(ii) // 3
        for child in node.get("children", []):
            walk(child)
    walk(payload.get("nodes"))
    params = payload.get("param", [])
    if not isinstance(params, list):
        params = []
    return {
        "format": "inochi2d-0.8", "sha256": hashlib.sha256(data).hexdigest(),
        "nodes": sum(nodes.values()), "node_types": dict(nodes),
        "vertices": vertices, "triangles": triangles,
        "parameters": len(params), "texture_count": textures,
        "texture_encodings": dict(tex_encoding), "extension_count": extension_count,
        "read_only": True
    }


def inspect_file(path: str | Path) -> dict[str, Any]:
    return inspect_bytes(Path(path).read_bytes())
