"""Optional MCP interface. Identical implementation as CLI; no duplicated rig logic.

Install with `pip install -e '.[mcp]'`. stdout reserved for MCP JSON-RPC.
"""
from __future__ import annotations
import hashlib
import json
from pathlib import Path

try:
    # MCP Python SDK 2.x renamed FastMCP to MCPServer. Prefer the current API.
    from mcp.server.mcpserver import MCPServer as FastMCP
except ImportError:
    try:
        from mcp.server.fastmcp import FastMCP  # MCP Python SDK 1.x
    except ImportError as exc:
        raise SystemExit(
            "Compatible MCP runtime missing: install with pip install -e '.[mcp]'"
        ) from exc

from native.inp08 import parse, inspect, extract_samples, encode, apply_keyform, atomic_write
from rigging.contracts import validate_manifest, lineage, make_anchor, mesh_fingerprint
from rigging.deform import propose_keyform
from rigging.handoff import manual_handoff, binding_vertex_slice
from rigging.creator_bridge import call_creator, set_node_transform_verified, creator_probe, creator_manual_edit_context

mcp=FastMCP('Inochi2D-AI-Rigging')


def load_model(path):
    raw=Path(path).read_bytes()
    doc,rawjson,tail=parse(raw)
    return raw,doc,tail

@mcp.tool()
def rig_status()->dict:
    """Clearly report available and unsupported capabilities."""
    return {'version':'0.6.0','inp08_read_write':'implemented',
            'inspect_anchors_and_pivots':'implemented',
            'manual_handoff_and_paged_vertex_bindings':'implemented_file_state_only',
            'tps_existing_keyform_proposal':'implemented',
            'creator_live_node_parameter_bridge':'requires patched Creator 0.8',
            'creator_live_mesh_and_binding_edit':'file-roundtrip export/import only; native in-memory API NOT implemented',
            'auto_pivot_reparent_preserve_world':'NOT implemented',
            'psd_to_full_rig':'NOT implemented',
            'ai_visual_quality_or_render_loop':'NOT implemented',
            'inp2_0_9_support':'NOT implemented',
            'transactional_inp08_batch_edit':'implemented_new_output_only',
            'barycentric_mesh_subdivision':'implemented_rebases_all_vertex_deform_keyforms',
            'single_and_pairwise_proxy_geometry_audit':'implemented_NOT_renderer'}

@mcp.tool()
def rig_inspect(path:str)->dict:
    """Inspect existing Inochi 0.8 project without changing it."""
    raw,doc,tail=load_model(path)
    return {'source_sha256':hashlib.sha256(raw).hexdigest(),**inspect(doc)}

@mcp.tool()
def rig_anchor_contract(path:str, node_guid:str, label:str, kind:str, point_px:list[float], coordinates_json:str)->dict:
    """Create a bound image-pixel to mesh-local anchor with parent/mesh fingerprints."""
    raw,doc,_=load_model(path)
    return {'format':'inochi-ai-rigging.anchors.v1','source_sha256':hashlib.sha256(raw).hexdigest(),
            'anchors':[make_anchor(doc,raw,node_guid,label,kind,point_px,json.loads(coordinates_json))],
            'lineage':lineage(doc,node_guid)}

@mcp.tool()
def rig_validate_anchors(path:str, manifest_path:str)->dict:
    """Verify every landmark, pivot and parent node is still on the same model version."""
    raw,doc,_=load_model(path)
    return validate_manifest(doc,raw,json.loads(Path(manifest_path).read_text(encoding='utf8')))

@mcp.tool()
def rig_propose_keyform(path:str, manifest_path:str, config_path:str, out_path:str)->dict:
    """Propose a TPS non-rigid *existing binding* keyform; does not apply changes."""
    raw,doc,_=load_model(path)
    manifest=json.loads(Path(manifest_path).read_text(encoding='utf8'))
    config=json.loads(Path(config_path).read_text(encoding='utf8'))
    plan=propose_keyform(doc,raw,manifest,config)
    out=Path(out_path)
    if out.exists():raise ValueError('refusing to overwrite plan output')
    atomic_write(out,json.dumps(plan,ensure_ascii=False,indent=2).encode())
    return {'path':str(out),'status':plan['status'],'anchor_count':plan['source_anchor_count'],
            'model_unmodified':True}

@mcp.tool()
def rig_apply_approved_plan(path:str, plan_path:str, out_path:str, visual_review_ack:bool=False)->dict:
    """Opt-in apply, existing un-authored keyform only, new output file only.

    Visual review acknowledgement does NOT mean the server performed a render.
    """
    if not visual_review_ack:raise ValueError('explicit visual_review_ack required')
    src=Path(path).resolve();out=Path(out_path).resolve()
    if src==out or out.exists():raise ValueError('refusing output overwrite')
    if out.suffix.lower() not in ('.inp','.inx'):
        raise ValueError('approved model must use .inp or .inx extension')
    raw,doc,tail=load_model(src)
    plan=json.loads(Path(plan_path).read_text(encoding='utf8'))
    if plan.get('format')!='inochi-authoring.keyform-plan.v1' or plan.get('source_sha256')!=hashlib.sha256(raw).hexdigest():
        raise ValueError('wrong or stale plan')
    if plan.get('status')!='CANDIDATE_ONLY' or plan.get('algorithm')!='TPS-v1-explicit-anchored':
        raise ValueError('unsupported or unverified proposal type')
    if type(plan.get('source_anchor_count')) is not int or plan['source_anchor_count']<3:
        raise ValueError('proposal lacks required source landmarks')
    import copy
    clone=copy.deepcopy(doc)
    patches=plan.get('patches')
    if not isinstance(patches,list) or not patches:raise ValueError('no patches')
    for p in patches:
        if not isinstance(p,dict):raise ValueError('invalid patch object')
        # MCP cannot request the explicit unsafe/overwrite flags exposed by the
        # low-level offline library. A forged plan must not bypass geometry QA.
        if p.get('allow_replace') or p.get('allow_unsafe'):
            raise ValueError('MCP refuses authored keyform replacement or unsafe geometry overrides')
        if set(p)-{'parameter','node_guid','key_index','vertex_offsets'}:
            raise ValueError('unknown or privileged keyform patch field')
        apply_keyform(clone,p)
    # The alternate plan writer must not bypass the batch editor's composite
    # geometry gate: two individually safe keys can invert a triangle together.
    from rigging.quality import inspect_geometry
    quality=inspect_geometry(clone,include_pairs=True)
    if not quality['individual_geometry_pass'] or not quality['additive_proxy_pair_pass']:
        raise ValueError('approved plan fails composite geometry validation')
    updated=encode(clone,tail)
    doc2,_,tail2=parse(updated)
    if doc2!=clone or tail!=tail2:raise ValueError('roundtrip failed')
    atomic_write(out,updated)
    return {'output':str(out),'applied':len(patches),'textures_preserved':True,
            'creator_render_tested':False,'requires_manual_creator_render':True}

@mcp.tool()
def rig_manual_handoff(path:str,node_guid:str,anchors_manifest_path:str="")->dict:
    """Read exact node/parent/binding/texture references and typed anchors before a manual edit."""
    raw,doc,_=load_model(path)
    anchors=json.loads(Path(anchors_manifest_path).read_text(encoding='utf8')) if anchors_manifest_path else None
    return manual_handoff(doc,raw,node_guid,anchors=anchors)

@mcp.tool()
def rig_binding_vertex_slice(path:str,node_guid:str,parameter_guid:str,binding_index:int,
                             key_index:list[int],start_vertex:int=0,limit:int=256)->dict:
    """Read a bounded slice of existing keyform vertex offsets, UVs and neutral positions."""
    raw,doc,_=load_model(path)
    return binding_vertex_slice(doc,raw,node_guid,parameter_guid,binding_index,key_index,start_vertex,limit)

@mcp.tool()
def creator_probe_connection()->dict:
    """Perform a real localhost Creator bridge handshake; no mock success."""
    return creator_probe()

@mcp.tool()
def creator_manual_edit_snapshot(uuid:str)->dict:
    """Get live parent/pivot-related context and explicitly list unavailable rig details."""
    return creator_manual_edit_context(uuid)

@mcp.tool()
def creator_get_node(uuid:str)->dict:
    """Query current live node local transform from separately patched Inochi Creator."""
    return call_creator('get_node',{'uuid':uuid})

@mcp.tool()
def creator_list_nodes()->dict:
    """Query Creator node hierarchy; does not mutate editor."""
    return call_creator('list_nodes',{'detail':True})

@mcp.tool()
def creator_set_transform_guarded(uuid:str, expected_json:str, new_translation:list[float]|None=None,
                                  new_rotation:list[float]|None=None,new_scale:list[float]|None=None)->dict:
    """Guarded live transform edit; translation/pivot relocation intentionally refused without compensation."""
    return set_node_transform_verified(uuid,expected=json.loads(expected_json),translation=new_translation,
                                       rotation=new_rotation,scale=new_scale)


from rigging.live_qa import capture_pose_sweep

@mcp.tool()
def creator_capture_pose_sweep(parameter_uuid: str, poses: list[list[float]],
                               acknowledge_live_mutations: bool=False)->dict:
    """Capture real patched Creator viewport evidence with original parameter restoration; no images emitted."""
    if not acknowledge_live_mutations:raise ValueError('explicit acknowledge_live_mutations required')
    return capture_pose_sweep(parameter_uuid,poses)

# ---- Atomic offline editing and geometry verification (same core as CLI). ----
from rigging.transactions import execute_transaction
from rigging.quality import inspect_geometry

@mcp.tool()
def rig_geometry_audit(path: str, include_pairs: bool=True)->dict:
    """Check authored single and pairwise additive-proxy deformation geometry; never claim a render pass."""
    _,doc,_=load_model(path)
    return inspect_geometry(doc,include_pairs=include_pairs)

@mcp.tool()
def rig_preview_transaction(path: str, batch_path: str, strict_pairs: bool=False)->dict:
    """Apply batch in memory, reject stale source or unsafe geometry; never write model."""
    batch=json.loads(Path(batch_path).read_text(encoding='utf8'))
    return execute_transaction(path,batch,commit=False,strict_pairs=strict_pairs)

@mcp.tool()
def rig_commit_transaction(path: str, batch_path: str, out_path: str,
                           human_approved: bool=False)->dict:
    """Requires explicit approval, checks revision/geometry, writes ONE new INP/INX file atomically."""
    if not human_approved:raise ValueError('human_approved is required for model output')
    batch=json.loads(Path(batch_path).read_text(encoding='utf8'))
    return execute_transaction(path,batch,destination=out_path,commit=True,strict_pairs=True)




from rigging.agent_editor import model_map as _agent_map,read_target as _agent_read

@mcp.tool()
def rig_agent_capabilities() -> dict:
    """Discover actual AI editing support and missing Creator runtime capabilities."""
    return {'format':'inochi-ai-rigging.agent-capabilities.v1',
            'offline_edits':['set_node_property','set_parameter_property','edit_mesh_vertices',
                             'edit_mesh_uvs','replace_deform_keyform','replace_binding_value_keyform',
                             'set_new_keyform','subdivide_mesh'],
            'workflow':['rig_agent_model_map','rig_agent_read_target','rig_agent_preview_batch',
                        'rig_agent_save_batch','rig_geometry_audit','creator_capture_pose_sweep'],
            'source_overwrite':False,'creator_live_mesh_edit':False,
            'ai_visual_aesthetic_score':False,'native_creator_atomic_transaction':False}

@mcp.tool()
def rig_agent_model_map(path: str) -> dict:
    """Read real GUIDs, parameter binding indexes and mesh revisions."""
    raw,doc,_=load_model(path)
    return _agent_map(doc,hashlib.sha256(raw).hexdigest())

@mcp.tool()
def rig_agent_read_target(path: str, kind: str, guid: str, field: str="",
                          parameter_guid: str="",node_guid: str="",binding_index: int=0,
                          start: int=0,limit: int=256) -> dict:
    """Read exact stored field, revision hash and optional paged arrays."""
    raw,doc,_=load_model(path)
    result=_agent_read(doc,kind,guid,field,parameter_guid,node_guid,binding_index,start,limit)
    result['source_sha256']=hashlib.sha256(raw).hexdigest()
    return result

@mcp.tool()
def rig_agent_preview_batch(path: str,batch_json: str) -> dict:
    """Apply edits to a disposable model copy and report quality without writes."""
    return execute_transaction(path,json.loads(batch_json),commit=False,strict_pairs=True)

@mcp.tool()
def rig_agent_save_batch(path: str,batch_json: str,output_path: str,
                         allow_agent_new_output: bool=False) -> dict:
    """Allow AI to publish verified edits to a NEW INP/INX file, never source."""
    if not allow_agent_new_output:
        raise ValueError('allow_agent_new_output is required')
    return execute_transaction(path,json.loads(batch_json),destination=output_path,
                               commit=True,strict_pairs=True)


from rigging.creator_bridge import creator_simple_edit_guarded
from rigging.live_model_bridge import prepare_session as live_prepare, preview_batch as live_preview, apply_batch as live_apply

@mcp.tool()
def creator_get_live_status() -> dict:
    """Read the running patched Creator project path and current edit mode."""
    return call_creator('get_status')

@mcp.tool()
def creator_get_live_parameters() -> dict:
    """Read current Creator parameter GUIDs, values, ranges and groups."""
    return call_creator('list_parameters')

@mcp.tool()
def creator_create_or_edit_basic(method: str, params_json: str, expected_project_path: str,
                                  expected_node_json: str="") -> dict:
    """Use safe existing Creator node/parameter commands; INOCHI_CREATOR_MUTATIONS=1 required."""
    expected=json.loads(expected_node_json) if expected_node_json else None
    return creator_simple_edit_guarded(method,json.loads(params_json),
                                       expected_project_path=expected_project_path,
                                       expected_node=expected)

@mcp.tool()
def creator_prepare_rig_session(workspace:str, expected_project_path:str)->dict:
    """Export currently opened Creator puppet with immutable recovery snapshot."""
    return live_prepare(workspace,expected_project_path=expected_project_path)

@mcp.tool()
def creator_preview_rig_session(session_path:str,batch_json:str)->dict:
    """Validate edits to the live Creator export without replacing the current project."""
    return live_preview(session_path,json.loads(batch_json))

@mcp.tool()
def creator_apply_rig_session(session_path:str,batch_json:str,
                              expected_project_path:str,
                              acknowledge_project_replacement:bool=False)->dict:
    """Import AI-edited model with baseline backup and strict readback. Loses Creator Undo history."""
    return live_apply(session_path,json.loads(batch_json),
                      expected_project_path=expected_project_path,
                      acknowledge_project_replacement=acknowledge_project_replacement)

if __name__=='__main__':
    mcp.run()
