# Contract for preserving pivots, anchors and coordinate provenance

## Identity and version

Every control point carries:

- `source_sha256`: the exact input `.inx/.inp` bytes used for calculation.
- `node_guid`: stable node identifier, not a name or index.
- `mesh_sha256`: hash of ordered `verts`, `uvs`, `indices`.
- `lineage_sha256`: hash of the node's full parent chain, transforms, lock-to-root and sort values.
- `label` and `kind`: e.g. `left_elbow` / `joint_center` or `outer_eye_corner` / `landmark`.

**Any mismatch aborts.** A point measured on one rig may not be applied to another by visual name similarity.

## Coordinate spaces

1. `image_pixel_top_left_y_down`: `(0,0)` at source image top-left.
2. `mesh_local`: 2D coordinates stored in `mesh.verts`.
3. `parent_local`: node translation/orientation is relative to its parent node.
4. `inochi_model_world_xy`: mesh point after composing all parent transforms.

You must explicitly provide source `image_origin_px`, `local_origin`, positive `model_units_per_pixel`, and whether mesh-local Y increases up or down. **No automatic scale, origin, or Y-flip guessing.** Conversion is reversible and unit tested.

## Distinguish five physical concepts

- `rotation_center`: proposed semantic rotational axis of a part.
- `joint_center`: point where bones or flexible mesh segments should bend.
- `seam`: paired vertex/edge alignment constraint between neighboring parts.
- `attachment`: child part should track the parent at this point.
- `occlusion_anchor`: landmark for sorting, clipping, and hidden geometry.

They may coincide but must not be silently conflated. For example, an earring's stud position is an attachment and pivot candidate; the dangling tip should swing around that stud, not around the earring image center. `pivot_handoff` reports `current_node_pivot_world` separately from `landmark_world`.

## World transform and reparent constraints

Our `rigging.spaces` only supports well-formed 2D transformations (explicit translation, rotation-Z in radians, scale). It refuses `lockToRoot`, X/Y rotations, zero scale and reparent plans involving shear. `reparent_plan_2d` computes a candidate transform without mutating the model. **Do not call Creator reparent and assume the result is world-position preserving** without a render/coordinate check.

Relocating the actual pivot on an existing rig is more complex: preserve neutral mesh position *and* every keyed transform, children, physics/collider anchors, mask targets, and tracking correspondence. Automated relocation is not offered until those invariants are tested on actual Creator models.

## Example input

```json
{
  "format": "inochi-ai-rigging.anchors.v1",
  "source_sha256": "SHA256-OF-ORIGINAL-MODEL",
  "anchors": [
    {
      "node_guid": "EXACT-NODE-GUID",
      "label": "left_eye_outer_corner",
      "kind": "landmark",
      "point_px": [360, 412],
      "point_local": [10, 8],
      "coordinates": {
        "from": "image_pixel_top_left_y_down",
        "to": "mesh_local",
        "image_origin_px": [350, 420],
        "local_origin": [0, 0],
        "model_units_per_pixel": 1,
        "axes": "x_right_y_up"
      },
      "mesh_sha256": "SHA256-OF-ORDERED-MESH",
      "lineage_sha256": "SHA256-OF-EXACT-NODE-PARENTS-AND-TRANSFORMS"
    }
  ]
}
```

This is only the schema example; placeholder hashes MUST be replaced by `rigging.contracts.make_anchor` output before use. Runtime models remain private and are not bundled.
