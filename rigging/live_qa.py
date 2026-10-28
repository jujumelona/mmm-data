"""Real patched-Creator viewport evidence capture with guarded parameter restore.

This is an integration hook, NOT an AI aesthetic score or a headless SDK render.
It requires a running patched Inochi Creator 0.8 on localhost; returns only
checksums and metadata, never sends screenshots into the chat or an MCP response.
"""
from __future__ import annotations
import base64
import hashlib
import math
import struct
from .creator_bridge import call_creator, CreatorBridgeError

class LiveQAError(ValueError):pass


def _lookup(values, uuid):
    if not isinstance(values,dict) or not isinstance(values.get('parameters'),list):
        raise LiveQAError('Creator list_parameters returned malformed data')
    selected=[]
    def walk(items):
        for item in items:
            if not isinstance(item,dict):raise LiveQAError('malformed parameter tree')
            if item.get('is_group'):
                walk(item.get('children') or [])
            elif str(item.get('uuid'))==str(uuid):
                selected.append(item)
    walk(values['parameters'])
    if len(selected)!=1:raise LiveQAError('parameter UUID missing or ambiguous')
    param=selected[0]
    for field in ('value','min','max'):
        if not isinstance(param.get(field),list) or len(param[field])!=2 or any(type(n) not in (int,float) or not math.isfinite(n) for n in param[field]):
            raise LiveQAError('incomplete Creator parameter range/value')
    return param


def _snapshot():
    status=call_creator('get_status')
    if not isinstance(status,dict) or not status.get('project_path'):
        raise LiveQAError('Creator project path missing; open and save a project')
    if status.get('armed_parameter'):
        raise LiveQAError('disarm active Creator editing parameter before pose sweep')
    return status


def _capture():
    data=call_creator('capture_viewport',{'full':True})
    if not isinstance(data,dict) or not isinstance(data.get('png_base64'),str):
        raise LiveQAError('Creator did not return viewport PNG')
    try:png=base64.b64decode(data['png_base64'],validate=True)
    except Exception as exc:raise LiveQAError('invalid Creator PNG base64') from exc
    if len(png)<24 or png[:8]!=b'\x89PNG\r\n\x1a\n' or png[12:16]!=b'IHDR':
        raise LiveQAError('Creator capture was not a PNG')
    w,h=struct.unpack_from('>II',png,16)
    if w<1 or h<1 or data.get('width')!=w or data.get('height')!=h:
        raise LiveQAError('viewport dimensions inconsistent')
    return {'width':w,'height':h,'png_sha256':hashlib.sha256(png).hexdigest(),'byte_length':len(png)}


def capture_pose_sweep(parameter_uuid:str, poses:list[list[float]])->dict:
    """Capture actual Creator before/after evidence, restoring original values.

    Mutations are separately gated by INOCHI_CREATOR_MUTATIONS=1. This API is
    intentionally serialized; callers must not concurrently edit the Creator.
    """
    if not isinstance(poses,list) or not poses:raise LiveQAError('nonempty poses required')
    status=_snapshot();project=status['project_path']
    param=_lookup(call_creator('list_parameters'),parameter_uuid)
    original=list(param['value']); minv=param['min'];maxv=param['max']
    checked=[]
    for pose in poses:
        if not isinstance(pose,list) or len(pose)!=2 or any(type(x) not in (int,float) or not math.isfinite(x) for x in pose):
            raise LiveQAError('every pose must be finite [x,y]')
        if not (minv[0]<=pose[0]<=maxv[0] and minv[1]<=pose[1]<=maxv[1]):
            raise LiveQAError('pose outside Creator parameter range')
        if not param.get('is_vec2',False) and pose[1]!=original[1]:
            raise LiveQAError('1D parameter Y must remain unchanged')
        checked.append(list(pose))
    evidence=[];changed=False
    try:
        for pose in checked:
            if _snapshot().get('project_path')!=project:
                raise LiveQAError('Creator project changed during sweep')
            changed=True
            call_creator('set_parameter',{'uuid':parameter_uuid,'x':pose[0],'y':pose[1]})
            current=_lookup(call_creator('list_parameters'),parameter_uuid)
            if any(abs(a-b)>1e-5 for a,b in zip(current['value'],pose)):
                raise LiveQAError('Creator did not apply requested pose')
            evidence.append({'pose':pose,**_capture()})
    finally:
        if changed:
            # Restore even on capture error; expose failures rather than silently
            # claiming success. Does not alter authored keyforms.
            call_creator('set_parameter',{'uuid':parameter_uuid,'x':original[0],'y':original[1]})
            restored=_lookup(call_creator('list_parameters'),parameter_uuid)
            if any(abs(a-b)>1e-5 for a,b in zip(restored['value'],original)):
                raise LiveQAError('CRITICAL: Creator parameter restore failed')
    return {'source':'patched Creator 0.8 live viewport','project_path':project,
            'parameter_uuid':str(parameter_uuid),'restored_parameter':True,'poses':evidence,
            'actual_viewports_captured':len(evidence),
            'aesthetic_score':None,'pixel_reference_compared':False,
            'limitation':'Viewport includes Creator UI/scene state. Image hashes prove capture, not rig quality. No video/user-facing images produced.'}
