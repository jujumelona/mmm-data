# Inochi2D-AI-Rigging

Independent, open-source **Inochi2D 0.8 rig-authoring and quality-gate research toolkit** with a CLI, a separately installable MCP endpoint, and a guarded interface to a patched Inochi Creator. It is **not** a finished professional auto-rigger or a Creator replacement.

## Status: working versus missing

| Feature | Status |
| --- | --- |
| INP1 `.inp`/`.inx` read, inspect, strictly gated keyform output | **Implemented** — Inochi2D 0.8 only |
| Preserve existing model's texture/extension bytes during approved edits | **Implemented, synthetic tests** |
| Mesh geometry, parameter samples and motion diagnostics | **Implemented on supplied geometry/samples** |
| Explicit image-pixel ↔ mesh-local landmark conversion | **Implemented** — requires measured calibration |
| Parent-chain fingerprints, model SHA, joint/rotation anchor provenance | **Implemented** |
| World/local transform and 2D reparent plan | **Implemented on supported planar frames** — refuses root-locked and shear cases |
| Nonuniform **TPS** landmark-driven deform-keyform proposal | **Implemented** — existing mesh, parameter and binding only |
| Node-level manual handoff + paged keyform vertex/UV/offset inspection | **Implemented** — raw file state, not evaluated Creator state |
| Thin optional MCP server wrapping the same core as CLI | **Implemented, needs `mcp` package to start** |
| Optional HTTP adapter to `ozekimasaki/inochi-creator-mcp` live Creator bridge | **Implemented on the documented RPC contract; no live Creator E2E verified** |
| PSD → full high-quality rig, alpha-adaptive AutoMesh replacement | **Not implemented** |
| Automatic world-preserving pivot relocation inside Creator | **Not implemented** — intentionally safety-blocked |
| Rig quality greater than professional Inochi2D Creator authoring | **Not demonstrated** |
| Real Creator renderer + visual AI optimization and output acceptance | **Not implemented** |
| INP2/0.9 models | **Not implemented / refused** |

No character art, private models, original vendor code or model weights are bundled.

## Quick start

```bash
python -m pip install -e .
python -m unittest discover -s native -p 'test_*.py' -v
python -m unittest discover -s tests -p 'test_*.py' -v
npm test
python -m rigging.cli --help
python -m rigging.cli inspect PATH_TO_EXISTING_0_8_MODEL.inx
```

For an MCP client:

```bash
python -m pip install -e '.[mcp]'
python -m rigging.mcp_server
```

Example client configuration for a local stdio MCP client:

```json
{
  "mcpServers": {
    "inochi-ai-rigging": {
      "command": "python",
      "args": ["-m", "rigging.mcp_server"]
    }
  }
}
```

A **separate patched Creator 0.8 build** is needed for `creator_*` methods. This project does *not* silently patch or launch Creator. Read `docs/EXTERNAL_MCP_AUDIT.md`.

## Rigging workflow

1. Import prepared artwork with official Creator/AutoMesh. Save an editable `.inx` 0.8 project.
2. Use `rig_inspect` / `inochi-rig inspect` to list actual nodes, mesh sizes, parameter GUIDs, and animation names.
3. For every landmark/pivot, create a manifest with exact `source_sha256`, `node_guid`, `mesh_sha256`, `lineage_sha256`, image→mesh coordinate calibration, and both image and local coordinates. **Do not infer Y direction, pivot, or scale.**
4. Use `rig_validate_anchors` and `rig_propose_keyform` to produce safe nonrigid candidates only for an **existing** mesh and un-authored parameter binding keyform.
5. Use `rig_apply_approved_plan` with explicit acknowledgement to write a **different file**. The writer refuses overwrite, stale original, triangle flips, and keys already authored.
6. **Open in the actual Creator**, inspect the 9 directions, edge seams, occlusion, eyebrow/mouth identity, and animations. This project currently does not execute the Creator renderer or establish artistic improvement.
7. Keep the official Creator result when the candidate does not *demonstrably* improve the appearance.

### Landmark-to-pivot handoff rule

A joint landmark in mesh-local coordinates is **not** automatically the node's pivot. The latter is the local origin `[0,0]`, inherited through transforms. `rigging.spaces.pivot_handoff` reports them separately, including parent GUID, measured model-world coordinates, and whether they coincide. An actual pivot relocation must also update mesh positions, children, bound keyforms and tracking/physics effects as needed, and is deliberately **not automatically applied** here.

## Extensions & acknowledgements

Existing MCP systems were inspected for their *protocols and boundaries*. This repository does **not** vendor their code:
- [inochi-creator-mcp](https://github.com/ozekimasaki/inochi-creator-mcp) — patched Creator RPC, GUI/nodes/parameters/viewport; no mesh vertex/binding modification.
- [inochi2d-toolkit](https://github.com/yanjingzhaisun/inochi2d-toolkit) — INP read/verify/texture extraction; no finished auto-rigger.

Inochi2D and Creator are separate projects, generally BSD-2-Clause. See `docs/EXTERNAL_MCP_AUDIT.md` for precise compatibility. Other registered GitHub projects are discovery references, **not integrated engines**. Follow their original licenses before copying code.

This project is not affiliated with the Inochi2D Project or either MCP author.

## Current source-backed handoff commands

```bash
python -m rigging.cli manual-handoff model.inx NODE_GUID --anchors anchors.json
python -m rigging.cli binding-slice model.inx NODE_GUID PARAM_GUID 0 2 2 --start 0 --limit 256
```

These functions also exist as MCP tools `rig_manual_handoff` and `rig_binding_vertex_slice`. They reveal exactly which data remains unavailable from a live Creator. See `docs/MCP_ENGINE_INTEGRATION_ROADMAP_KO.md` for external MCP comparisons and production-level gaps. Current GitHub publication is `jujumelona/mmm-data` until the repository is renamed.
