# Existing MCP and SDK research

1. https://github.com/ozekimasaki/inochi-creator-mcp: Node.js MCP ↔ localhost Creator bridge. Requires modified Inochi Creator v0_8 build. Supports project, node, parameter, basic animation, viewport capture. Does **not** directly edit mesh vertices/parameter binding details.
2. https://github.com/yanjingzhaisun/inochi2d-toolkit: Python 0.8 model file parser, inspect/verify/extract, minimal build and MCP surface. Full autorig and renderer bridge described as plans, not completed tools.
3. https://github.com/Inochi2D/inochi2d: official SDK, version-specific data structures. 0.8 `TRNSRTS` is **not** the later 0.9 `INP2`.

## Rigging correctness contracts for future modules
- Record pixel-to-mesh conversion with image dimensions, axis direction and measured calibration; never assume pixel space equals model space.
- Record node GUID, chain of parents, pivot at local origin, joint landmark distinct from pivot, transforms, mesh indices/UV/bindings.
- Relocating a pivot requires coordinated updates to mesh positions, descendants, existing keyforms/physics; merely changing node translation breaks continuity.
- Reject stale source SHA, changed topology/texture calibration, triangle winding flips, unsupported shear and root lock cases.
- Keep original art private, modify copies, compare actual Creator renders rather than trusting synthetic geometry tests.

This document is a comparative engineering note, not a claim that upstream code is included or that finished AI automatic rigging is implemented.
