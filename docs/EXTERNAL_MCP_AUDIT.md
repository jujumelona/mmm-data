# Existing MCP projects — actual implementation audit (2026-10-28)

## `ozekimasaki/inochi-creator-mcp`

Checked `README.md`, `src/creator-client.ts`, `src/tools/nodes.ts`, `src/tools/parameters.ts`, `src/tools/import.ts`, `src/tools/viewport.ts`, and `creator-bridge/mcp/handlers.d`.

- Architecture: **stdio MCP** (Node + TypeScript) → HTTP `POST` to `127.0.0.1:17320/rpc` → specially patched and rebuilt **Inochi Creator v0_8** D implementation, polled on Creator UI thread. Stock itch/Steam Creator does not have this bridge.
- Read: `get_status`, `list_nodes`, `get_node`, `list_parameters`, animations, capture viewport.
- Write: set node local translation/rotation/scale/z-sort, select/rename/reparent/create/delete node, arm/set/add/remove parameters, animation keyframes, import PSD/images and save/export.
- Rotation on `creator_set_node_transform` uses **radians**, node local translation is relative to its parent; a node is not the same as a semantic part joint center.
- **Missing for professional rigging:** mesh vertex/triangle editing, deform binding keyform creation/repair, compensated pivot relocation and provenance of image↔mesh coordinates. Reparent action is not assumed to preserve world space; capture viewport is not an automatic reference-based QA system.
- Security: loopback only with optional `INOCHI_MCP_TOKEN`. Our client allowlists a subset of RPC methods, requires `INOCHI_CREATOR_MUTATIONS=1` for mutation, and rejects unchecked pivot movement.
- Integration status: **compatible HTTP client implementation, NOT tested against a running patched Creator**.

## `yanjingzhaisun/inochi2d-toolkit`

Checked `README.md`, `docs/architecture.md`, `src/inochi2d_toolkit/inp.py`, `src/inochi2d_toolkit/mcp_server.py`.

- Thin Python MCP server for structural inspect/verify, texture extraction and minimal 0.8 file creation.
- INP1 uses `TRNSRTS\0`, big-endian JSON length, JSON payload, `TEX_SECT`, optional `EXT_SECT`.
- Auto-rig, alpha-adaptive mesh generation, native Creator rendering are **proposed**, not already working in this project.
- Our code independently uses file parsing + conservative keyform patching, adds anchored coordinate contract and TPS candidates, but **does not outperform official Creator yet**.

## Inochi Creator v0_8 / SDK: coordinate and scene-graph constraints

Official `source/inochi2d/core/nodes/package.d` and `source/inochi2d/core/param/binding.d` define:

- Each node has a parent-linked transform, local position, rotation and scale. Parent transforms are inherited; `lockToRoot` is special and must not be approximated as a normal parent link.
- Mesh `verts`, `uvs`, `indices` are ordered; deform bindings contain per-keyform **vertex offset arrays** keyed to target node GUID and parameter. Retopology without rebuilding bindings breaks correspondence.
- Values can be bound to `transform.t.x`, `transform.t.y`, `transform.r.z`, etc. Pivot edits must consider these bindings and attached children.
- Only sampled local geometry is currently verified automatically; true deformation composition, mask ordering, physics, graphics rendering and keyframe interpolation need Creator/SDK evaluation.
- SDK 0.9 INP2 is a **different format**. No speculative migration.

## Quality gate for future 'fully integrated' label

A feature must have a real input model and documented official baseline, automatically generated output accepted and editable in Creator, actual rendered pose coverage, mask/occlusion/joint seam review, performance measurements, and a fail-safe rollback. Merely passing unit tests or cloning repositories is insufficient.
