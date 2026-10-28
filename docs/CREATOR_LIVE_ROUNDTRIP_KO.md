# Inochi Creator v0.8 file roundtrip connection

The project now connects the AI rigging editor to the running Creator using
the existing patched Creator MCP bridge export_inp / import_inp RPC methods.

Setup:
1. Clone Inochi2D/inochi-creator at v0_8; apply the D bridge patch from
   ozekimasaki/inochi-creator-mcp and compile it. The stock binary has no RPC.
2. Save the Creator project, disarm editing parameters, start patched Creator.
3. Install with pip install -e '.[mcp]' and run python -m rigging.mcp_server on the SAME PC.
4. Match INOCHI_MCP_PORT (default 17320) and optional INOCHI_MCP_TOKEN.
5. Set INOCHI_CREATOR_MUTATIONS=1 for explicitly authorized project replacement.

MCP sequence:
- creator_probe_connection
- creator_get_live_status
- creator_prepare_rig_session(workspace,expected_project_path)
- rig_agent_model_map(source_path) and rig_manual_handoff for GUID/keyform planning
- creator_preview_rig_session(session_path,batch_json)
- creator_apply_rig_session(session_path,batch_json,expected_project_path,
                            acknowledge_project_replacement=true)

IMPORTANT: import_inp REPLACES the currently opened Creator puppet and resets
its Undo history. The original source.inp is kept for recovery; no auto-save
occurs. Save the newly imported model under a new project name.

The bridge fails closed on stale source hashes, modified Creator status,
invalid geometry, or mismatched re-exported model data. If import fails, it
attempts to restore the original snapshot and marks recovery status. If
rollback cannot be verified, the state becomes RECOVERY_REQUIRED.

This does NOT implement native Creator in-memory vertex/binding editing, an
autonomous LLM driver, or visual aesthetic scoring. Real Windows Creator 0.8
integration must be tested with the patched binary.