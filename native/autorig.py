"""0.8 Inochi2D *existing-parameter* first-pass authoring.

Creates 3x3 translation/stretch deform-binding candidate patches from user-measured
face landmarks. It never segments art, creates node hierarchies, or claims
professional-level motion. Explicit review and approval gate before writing.
"""
from __future__ import annotations
import argparse
import copy
import hashlib
import json
import math
from pathlib import Path
import sys

from inp08 import parse, encode, inspect, walk_nodes, validate_mesh, apply_keyform, FormatError, atomic_write

ROLES={"face","leftEye","rightEye","nose","mouth","chin","frontHair","backHair","leftBrow","rightBrow"}


def vector(v,name):
    if not isinstance(v,list) or len(v)!=2 or any(type(n) not in (int,float) or not math.isfinite(n) for n in v):
        raise FormatError(f"invalid landmark: {name}")
    return v


def compile_plan(document, source_bytes, config):
    landmarks=config.get("landmarks",{})
    for name in ("face","leftEye","rightEye","nose","mouth","chin"):
        vector(landmarks.get(name), name)
    node_roles=config.get("node_roles",{})
    if not isinstance(node_roles,dict) or not node_roles:
        raise FormatError("node_roles must map roles to existing node GUIDs")
    if set(node_roles)-ROLES:
        raise FormatError("unknown node roles: "+", ".join(sorted(set(node_roles)-ROLES)))
    if len(set(node_roles.values()))!=len(node_roles):
        raise FormatError("node GUIDs must map to distinct roles")
    param_name=config.get("parameter", "Head:: Angle")
    found=[p for p in document.get("param",[]) if p.get("name")==param_name]
    if len(found)!=1:
        raise FormatError("existing 2D angle parameter not found; create rig parameter in Creator first")
    axes=found[0].get("axis_points",[])
    if len(axes)!=2 or len(axes[0])!=3 or len(axes[1])!=3:
        raise FormatError("parameter must already have a 3x3 lattice")
    if not all(len(axis)==3 and axis[0]<axis[1]<axis[2] and abs(axis[1])<1e-8 for axis in axes):
        raise FormatError("angle axes must be ordered [-angle, 0, +angle]")
    nodes={str(node.get("uuid",node.get("guid",""))):(path,node) for path,node in walk_nodes(document["nodes"])}
    hh=abs(landmarks["chin"][1] - (landmarks["leftEye"][1]+landmarks["rightEye"][1])/2)
    if hh<5:raise FormatError("head landmarks too small or inconsistent")
    scale=config.get("strength",0.7)
    if not isinstance(scale,(int,float)) or not 0<scale<=1:raise FormatError("strength must be in (0,1]")
    patches=[];skipped=[]
    for role, guid in node_roles.items():
        if guid not in nodes:raise FormatError(f"no such mesh node GUID for {role}: {guid}")
        path,node=nodes[guid];mesh=validate_mesh(node,path)
        if mesh is None:raise FormatError(f"node {guid} has no mesh")
        binds=[b for b in found[0].get("bindings",[]) if b.get("node")==guid and b.get("param_name")=="deform"]
        if len(binds)!=1:raise FormatError(f"existing deform binding required for {role}/{guid}")
        b=binds[0]
        if len(b.get("isSet",[]))!=3 or any(len(row)!=3 for row in b["isSet"]):
            raise FormatError(f"{role} has invalid isSet array")
        origin=landmarks.get(role,landmarks["face"])
        if role in ("leftBrow","rightBrow"):
            origin=landmarks["leftEye" if role=="leftBrow" else "rightEye"]
        for ix,x in enumerate(axes[0]):
            for iy,y in enumerate(axes[1]):
                if ix==1 and iy==1:continue
                if b["isSet"][ix][iy]:
                    skipped.append({"role":role,"key_index":[ix,iy],"reason":"already user-authored"})
                    continue
                xnorm=x/(axes[0][-1] if x>=0 else abs(axes[0][0]))
                ynorm=y/(axes[1][-1] if y>=0 else abs(axes[1][0]))
                # T is low-frequency face translation. Eye/nose/ear depth adds parallax.
                surface_x=xnorm*0.12*hh*scale
                surface_y=-ynorm*0.10*hh*scale
                follow={"face":1,"leftEye":1.55,"rightEye":1.55,"nose":2.0,"mouth":1.5,"chin":1.3,
                        "frontHair":1.25,"backHair":-0.15,"leftBrow":1.5,"rightBrow":1.5}[role]
                dx=surface_x*follow
                dy=surface_y*(1.0 if role=="face" else 1.18)
                width_scale=1.0
                if role in ("leftEye","rightEye") and abs(xnorm)>.001:
                    far=(role=="leftEye" and xnorm>0) or (role=="rightEye" and xnorm<0)
                    width_scale=1 - abs(xnorm)*0.13 if far else 1 + abs(xnorm)*0.06
                offsets=[[round((v[0]-origin[0])*(width_scale-1)+dx,5),round(dy,5)] for v in mesh["neutral"]]
                p={"parameter":param_name,"node_guid":guid,"key_index":[ix,iy],"vertex_offsets":offsets}
                # Geometry checked again in apply_keyform, which verifies vertex and triangle topology.
                temp=copy.deepcopy(document)
                try:apply_keyform(temp,p)
                except FormatError as e:
                    skipped.append({"role":role,"key_index":[ix,iy],"reason":str(e)})
                    continue
                patches.append(p)
    return {"format":"inochi-authoring.keyform-plan.v1","source_sha256":hashlib.sha256(source_bytes).hexdigest(),
            "parameter":param_name,"model":document.get("meta",{}).get("name"),"patches":patches,"skipped":skipped,
            "status":"CANDIDATE_ONLY","warning":"Rough 2.5D first-pass. Not a substitute for artwork, occlusion recovery, artist-selected keyforms, physics, or Creator/WASM render verification."}


def main():
    p=argparse.ArgumentParser(description="Propose 3x3 first-pass keyforms for EXISTING Inochi2D 0.8 rig")
    p.add_argument("command",choices=["plan","apply"])
    p.add_argument("model",type=Path)
    p.add_argument("--config",type=Path,help="landmarks and explicit mapping of existing rig nodes")
    p.add_argument("--plan",type=Path)
    p.add_argument("--output",type=Path)
    p.add_argument("--acknowledge-visual-review-required",action="store_true")
    args=p.parse_args()
    try:
        source=args.model.read_bytes();doc,raw,tail=parse(source)
        if args.command=="plan":
            if not args.config:raise FormatError("--config required")
            config=json.loads(args.config.read_text(encoding="utf8"))
            result=compile_plan(doc,source,config)
            out=json.dumps(result,ensure_ascii=False,indent=2).encode("utf8")
            if args.output:atomic_write(args.output,out)
            else:sys.stdout.buffer.write(out+b"\n")
        else:
            if not args.plan or not args.output:raise FormatError("--plan and --output required")
            if not args.acknowledge_visual_review_required:
                raise FormatError("must explicitly acknowledge visual review; no implicit auto-commit")
            plan=json.loads(args.plan.read_text(encoding="utf8"))
            if plan.get("format")!="inochi-authoring.keyform-plan.v1" or plan.get("source_sha256")!=hashlib.sha256(source).hexdigest():
                raise FormatError("wrong format or stale plan")
            if plan.get("status")!="CANDIDATE_ONLY":
                raise FormatError("only candidate plans may be applied")
            if not isinstance(plan.get("patches"),list) or not plan["patches"]:
                raise FormatError("no safe proposed changes")
            if args.output.suffix.lower() not in (".inp",".inx"):
                raise FormatError("model output must be .inp or .inx")
            clone=copy.deepcopy(doc);results=[]
            seen=set()
            for patch in plan["patches"]:
                if not isinstance(patch,dict) or set(patch)-{"parameter","parameter_guid","node_guid","key_index","vertex_offsets"}:
                    raise FormatError("unsupported or privileged keyform patch fields")
                key=(patch.get("parameter_guid",patch.get("parameter")),patch.get("node_guid"),str(patch.get("key_index")))
                if key in seen:raise FormatError("duplicate keyform patch target")
                seen.add(key)
                results.append(apply_keyform(clone,patch))
            # Legacy direct CLI cannot bypass full geometry quality checks.
            # Enable core imports when this script is executed outside repo CWD.
            sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
            from rigging.quality import inspect_geometry
            quality=inspect_geometry(clone,include_pairs=True)
            if not quality['individual_geometry_pass'] or not quality['additive_proxy_pair_pass']:
                raise FormatError("unsafe authored keyforms or composite-pose geometry")
            updated=encode(clone,tail);reloaded,_,t=parse(updated)
            if reloaded!=clone or t!=tail:raise FormatError("roundtrip validation failed")
            atomic_write(args.output,updated)
            print(json.dumps({"applied":len(results),"output":str(args.output),"texture_tail_unchanged":True,"requires_real_creator_render_review":True}))
    except (OSError,ValueError,KeyError,TypeError) as e:
        print("ERROR:",e,file=sys.stderr);sys.exit(2)

if __name__=="__main__":main()
