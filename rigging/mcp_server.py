"""Optional MCP interface. Identical implementation as CLI; no duplicated rig logic.

Install with `pip install -e '.[mcp]'`. stdout reserved for MCP JSON-RPC.
"""
from __future__ import annotations
import hashlib
import json
from pathlib import Path

try:
    from mcp.server.fastmcp import FastMCP
except ImportError as exc:
    raise SystemExit("MCP extra not installed. pip install -e '.[mcp]'") from exc

from native.inp08 import parse, inspect, extract_samples, encode, apply_keyform, atomic_write
from rigging.contracts import validate_manifest, lineage, make_anchor, mesh_fingerprint
from rigging.deform import propose_keyform
from rigging.creator_bridge import call_creator, set_node_transform_verified

mcp=FastMCP('Inochi2D-AI-Rigging')


def load_model(path):
    raw=Path(path).read_bytes()
    doc,rawjson,tail=parse(raw)
    return raw,doc,tail

@mcp.tool()
def rig_status()->dict:
    """Clearly report available and unsupported capabilities."""
    return {'version':'0.4.0','inp08_read_write':'implemented',
            'inspect_anchors_and_pivots':'implemented',
            'tps_existing_keyform_proposal':'implemented',
            'creator_live_node_parameter_bridge':'requires patched Creator 0.8',
            'creator_live_mesh_and_binding_edit':'NOT implemented',
            'auto_pivot_reparent_preserve_world':'NOT implemented',
            'psd_to_full_rig':'NOT implemented',
            'ai_visual_quality_or_render_loop':'NOT implemented',
            'inp2_0_9_support':'NOT implemented'}

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
    raw,doc,tail=load_model(src)
    plan=json.loads(Path(plan_path).read_text(encoding='utf8'))
    if plan.get('format')!='inochi-authoring.keyform-plan.v1' or plan.get('source_sha256')!=hashlib.sha256(raw).hexdigest():
        raise ValueError('wrong or stale plan')
    import copy
    clone=copy.deepcopy(doc)
    patches=plan.get('patches')
    if not isinstance(patches,list) or not patches:raise ValueError('no patches')
    for p in patches:apply_keyform(clone,p)
    updated=encode(clone,tail)
    doc2,_,tail2=parse(updated)
    if doc2!=clone or tail!=tail2:raise ValueError('roundtrip failed')
    atomic_write(out,updated)
    return {'output':str(out),'applied':len(patches),'textures_preserved':True,
            'creator_render_tested':False,'requires_manual_creator_render':True}

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

if __name__=='__main__':mcp.run()
