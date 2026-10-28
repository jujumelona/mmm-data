# Inochi2D AI Rigging — manual editing & MCP audit (Korean)

## MCP connected vs Creator connected

- MCP stdio process registration is **not** proof of Inochi Creator connectivity.
- Call `creator_probe_connection`: `creator_connected=true` requires the separately patched and running Creator v0_8 RPC bridge on localhost port 17320.
- The official Creator executable does not provide this RPC automatically. Optional `INOCHI_MCP_PORT` and `INOCHI_MCP_TOKEN` must match between bridge and server.
- The external bridge can read live node transforms and parameters. **It cannot inspect or edit raw mesh vertices, deform binding grids, actual pivot geometry, physics anchor maps or mask links.**
- `creator_manual_edit_snapshot` returns a GUID-stable parent-chain and a list of unavailable fields. Do not confuse a semantic landmark with Creator's actual node origin.

## Mandatory manual-adjustment handoff fields

1. **File identity:** exact .inx/.inp SHA-256, 0.8 vs 0.9/INP2 version, immutable backup.
2. **Part identity:** node GUID / live Creator UUID mapping, node type, full ancestor chain (including parent GUID), transform, zsort, enabled, draw order. Names are never unique IDs.
3. **Artwork provenance:** full canvas resolution, transparent PNG layer bounding box, crop offset in original canvas, image hash, atlas UV, original texture width/height, material and emissive/normal-map alignment.
4. **Coordinate contract:** image pixel top-left Y-down, mesh-local, parent-local and model-world must be tagged independently. Existing converter assumes explicit axis-aligned uniform scale; do not guess Y flip, crop, scaling or rotate. Use official Creator matrices for root locks, X/Y rotations, shear and unusual artwork transforms.
5. **Distinct anchor kinds:** rotation_center, joint_center, attachment, seam, occlusion_anchor and landmark. Do not silently translate or reparent the true node pivot.
6. **Pivot rebase:** to move an actual rotation origin, compensate the full neutral mesh, existing keyed vertex offsets, all children, any parent deformers, physics/colliders, masks and tracking drivers. This feature is NOT supported by the upstream RPC, so the live auto-pivot move is blocked.
7. **Parameters & bindings:** parameter GUID, axes/axis_points, key coordinate and isSet flag, interpolation, target node GUID, binding param_name, mesh vertex count, and current authored keys. Reject stale versions and protect previously-authored keys.
8. **Geometry QA:** winding, inverted/collapsed triangles, UV integrity, visible contour, non-rigid blending, joint closure. Retopology requires remapping every existing keyframe.
9. **Occlusion/paint QA:** front/back hair and earrings, actual hidden geometry, clipping and composite masks, z ordering, opacity, emissive and normal maps, attachment seam continuity.
10. **Motion QA:** neutral, +/− angle extremes, midpoints, combinations, open/closed eyes, vowels and closing lips, arm/hand joints, soft-body physics across time, and actual Creator rendering. Geometry tests alone are not evidence of aesthetic quality.

## Current capabilities / outstanding blockers

- Implemented: file reader/writer, conservative non-rigid keyform candidates, model+mesh+ancestry hashes, MCP/CLI wrappers.
- Added audit guards: MCP keyform patch cannot set unsafe or overwrite flags; live translation cannot bypass pivot guard; entire ancestor chain is snapshot-checked before rotation or scale edits; output publication uses atomic no-overwrite hard link.
- Not implemented: real patched Creator bridge in this environment, Creator transaction compare-and-set, pivot rebasing, mesh+binding authoring RPC, actual image/UV calibration extraction, visual QA loop, PSD→full rig. Rotation/scale still uses non-atomic live RPC; another simultaneous editor can cause a race.
- For actual completeness, extend Creator D bridge to expose mesh/UV, parameter bindings, physics, masks, SDK world matrices, transactional edits and render_pose; validate the bridge against actual live models before calling it production-ready.

References: https://github.com/ozekimasaki/inochi-creator-mcp ; https://github.com/yanjingzhaisun/inochi2d-toolkit ; https://github.com/Inochi2D/inochi-creator
