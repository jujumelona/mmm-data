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
    if translation is not None and expected.get('pivot_compensation_required',True):
        raise CreatorBridgeError('node translation changes pivot/children; no mesh/child compensation supported')
    return call_creator('set_node_transform',payload)
