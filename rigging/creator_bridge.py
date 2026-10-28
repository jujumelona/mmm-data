"""Optional localhost adapter for ozekimasaki/inochi-creator-mcp's D bridge.

This is a compatible RPC client, NOT a replacement for the patched creator.
We do not send any project data off-machine. No upstream source copied.
"""
from __future__ import annotations
import json
import os
from urllib.request import Request, urlopen
from urllib.error import URLError

class CreatorBridgeError(RuntimeError): pass

READ_METHODS={'ping','get_status','list_nodes','get_node','list_parameters','list_animations'}
WRITE_METHODS={'set_node_transform','set_parameter','save_project','arm_parameter','disarm_parameter'}


def call_creator(method: str, params: dict | None = None, *, timeout=15):
    if method not in READ_METHODS|WRITE_METHODS:
        raise CreatorBridgeError('RPC method not allowlisted; unsupported/unsafe method')
    if method in WRITE_METHODS and os.environ.get('INOCHI_CREATOR_MUTATIONS')!='1':
        raise CreatorBridgeError('Set INOCHI_CREATOR_MUTATIONS=1 explicitly to allow editor changes')
    port=int(os.environ.get('INOCHI_MCP_PORT','17320'))
    if not 1<=port<=65535:raise CreatorBridgeError('invalid Creator bridge port')
    token=os.environ.get('INOCHI_MCP_TOKEN')
    headers={'Content-Type':'application/json'}
    if token:
        headers['Authorization']='Bearer '+token
        headers['X-Inochi-Token']=token
    body=json.dumps({'method':method,'params':params or {}},allow_nan=False).encode()
    req=Request(f'http://127.0.0.1:{port}/rpc',data=body,headers=headers,method='POST')
    try:
        with urlopen(req,timeout=timeout) as reply:
            response=json.load(reply)
    except (OSError,ValueError,URLError) as exc:raise CreatorBridgeError(f'local Creator RPC unavailable: {exc}') from exc
    if not isinstance(response,dict) or response.get('ok') is not True:
        raise CreatorBridgeError('Creator error: '+str(response.get('error') if isinstance(response,dict) else response))
    return response.get('result')


def set_node_transform_verified(guid, *, translation=None, rotation=None, scale=None, expected=None):
    """Compare the live Creator transform before mutation. No silent overwrite.

    The existing bridge API accepts local translation, Euler angles in radians,
    and scale. It cannot perform a compensated *pivot relocation* safely.
    """
    if not expected or not isinstance(expected,dict):
        raise CreatorBridgeError('expected current transform snapshot is mandatory')
    got=call_creator('get_node',{'uuid':guid})
    if not isinstance(got,dict) or str(got.get('uuid'))!=str(guid):
        raise CreatorBridgeError('Creator returned unexpected node')
    for key in ('translation','rotation','scale','parent_uuid'):
        if key not in expected:
            raise CreatorBridgeError(f'expected snapshot missing {key}')
        if got.get(key)!=expected.get(key):
            raise CreatorBridgeError(f'Creator {key} changed; refresh snapshot before edit')
    payload={'uuid':guid}
    for key,value,dim in (('translation',translation,3),('rotation',rotation,3),('scale',scale,2)):
        if value is not None:
            if not isinstance(value,(list,tuple)) or len(value)!=dim:
                raise CreatorBridgeError(f'bad {key} shape')
            import math
            if any(type(v) not in (int,float) or not math.isfinite(v) for v in value):
                raise CreatorBridgeError(f'bad {key} finite values')
            payload[key]=list(value)
    if len(payload)==1:raise CreatorBridgeError('no transform change provided')
    if translation is not None:
        raise CreatorBridgeError('node translation changes pivot/children; no mesh/child compensation supported')
    if not isinstance(expected.get('ancestor_chain'), list):
        raise CreatorBridgeError('expected ancestor_chain required; call creator_manual_edit_context first')
    context=creator_manual_edit_context(guid)
    if context['ancestor_chain']!=expected['ancestor_chain']:
        raise CreatorBridgeError('Creator ancestor_chain changed; regenerate snapshot')
    if context['node_snapshot'] != {k:got.get(k) for k in context['node_snapshot']}:
        raise CreatorBridgeError('Creator node changed during snapshot; retry')
    return call_creator('set_node_transform',payload)


def creator_probe() -> dict:
    """Perform actual localhost RPC probes; MCP registration alone is not connectivity."""
    try:
        ping=call_creator('ping')
        status=call_creator('get_status')
        return {'creator_connected':True,'rpc_ping':ping,'creator_status':status,
                'mesh_edit':False,'parameter_binding_edit':False,
                'warning':'Live mesh and binding editing is unavailable in the upstream bridge.'}
    except (CreatorBridgeError,OSError,ValueError) as exc:
        return {'creator_connected':False,'error':f'{type(exc).__name__}: {exc}',
                'mesh_edit':False,'parameter_binding_edit':False}


def creator_manual_edit_context(guid: str) -> dict:
    """Read the complete live parent-chain snapshot; do not invent unavailable pivots."""
    node=call_creator('get_node',{'uuid':guid})
    tree=call_creator('list_nodes',{'detail':True})
    params=call_creator('list_parameters')
    if not isinstance(node,dict) or str(node.get('uuid'))!=str(guid):
        raise CreatorBridgeError('Creator returned wrong live node UUID')
    if not isinstance(tree,dict) or not isinstance(tree.get('root'),dict):
        raise CreatorBridgeError('Creator returned incomplete hierarchy')
    found=[]
    def walk(item,ancestors):
        if not isinstance(item,dict):raise CreatorBridgeError('malformed node hierarchy')
        entry={key:item.get(key) for key in ('uuid','parent_uuid','translation','rotation','scale','zsort','enabled','type')}
        if str(item.get('uuid'))==str(guid):found.append(ancestors+[entry])
        for child in item.get('children',[]) or []:
            walk(child,ancestors+[entry])
    walk(tree['root'],[])
    if len(found)!=1:raise CreatorBridgeError('missing or duplicate node in live hierarchy')
    chain=found[0]
    if len(chain)>1 and str(chain[-2]['uuid'])!=str(node.get('parent_uuid')):
        raise CreatorBridgeError('live node parent differs from hierarchy')
    if any(key not in node for key in ('translation','rotation','scale','parent_uuid')):
        raise CreatorBridgeError('Creator snapshot missing transform; cannot edit safely')
    snapshot={key:node.get(key) for key in ('uuid','translation','rotation','scale','parent_uuid','zsort','enabled')}
    return {'uuid':str(guid),'node_snapshot':snapshot,'ancestor_chain':chain,
            'parameters':params,
            'authoring_context_missing':['mesh_vertices','mesh_uv','actual_pivot','parameter_bindings',
                                         'physics_anchors','mask_relationships','parameter_drivers',
                                         'texture_pixel_calibration'],
            'safe_for_automatic_pivot_relocation':False,
            'note':'Read-only snapshot. No atomic compare-and-set in upstream Creator RPC; recheck before manual edits.'}
