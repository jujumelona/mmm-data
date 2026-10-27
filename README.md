# Inochi2D-AI-Rigging

Open-source **Inochi2D rig-authoring and validation toolkit**. This repository has been repurposed from its former MMM data-store role. **It is not an MMM trajectory store.**

## Current public bootstrap

- A standalone, dependency-free Inochi2D 0.8 INP/INX **read-only inspector**.
- Structural checks for model payloads, texture sections, node/triangle counts, and malformed files.
- CLI and unit tests.
- Detailed roadmap and compatibility boundaries for eventual **full AI-assisted editing, rigging, pivot preservation, keyforms, rendering, Creator bridge and MCP**.

**Status:** Early public bootstrap. Do **not** mistake this source for a finished AI autorigger or for the complete v0.4 development archive. Real-model render/quality verification remains outstanding.

## Quick start

```bash
python -m pip install -e .
inochi-rig inspect /path/to/model.inx
python -m unittest discover -s tests -v
```

## Project architecture and source migration

The full v0.4 development package with experimental rigging, safe anchor contracts, constrained keyform proposals, Python/JS tests and optional MCP adapter exists separately; these features **have not yet all been migrated into this public repository**.

The ultimate design is independent of AIRI:
```text
Inochi2D-AI-Rigging
├── file / scene authoring core
├── accurate coordinate / landmark / pivot handoff
├── adaptive mesh / facial and articulated-body autorig
├── saved parameter + keyform editing
├── rendering + visual QA + rollback
└── CLI / API / optional MCP
```

No RE:ARCHIVE character assets, private AIRI code or previous MMM memory are published here.

Inochi2D and Inochi Creator are separately maintained projects. This repository is not affiliated with the Inochi2D Project. See [docs/EXTERNAL_MCP_AUDIT.md](docs/EXTERNAL_MCP_AUDIT.md) and [README_KO.md](README_KO.md).

License: MIT (original code only).