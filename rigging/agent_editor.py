"""GUID/revision-guarded AI authoring for Inochi2D 0.8 puppet files.
The exact same functions run under MCP and CLI. This is NOT Creator's renderer.
"""
import copy
import hashlib
import json
import math
from native.inp08 import validate_mesh, walk_nodes
from native.local_geometry import geometry_errors
from .contracts import locate, mesh_fingerprint

class AgentEditError(ValueError): pass

def digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,ensure_ascii=False,
                                      allow_nan=False,separators=(",",":")).encode()).hexdigest()

def guid(item):
    return str(item.get("guid",item.get("uuid","")))

def node(doc,key):
    if not isinstance(key,str) or not key: raise AgentEditError("node GUID required")
    return locate(doc,key)[1]

def parameter(doc,key):
    matches=[p for p in doc.get("param",[]) if isinstance(p,dict) and guid(p)==str(key)]
    if len(matches)!=1: raise AgentEditError("missing or duplicate parameter GUID")
    return matches[0]

def binding(doc,param_guid,node_guid,index):
    p=parameter(doc,param_guid);bs=p.get("bindings",[])
    if type(index) is not int or index<0 or index>=len(bs):
        raise AgentEditError("invalid binding index")
    b=bs[index]
    if str(b.get("node"))!=str(node_guid): raise AgentEditError("binding node GUID mismatch")
    return p,b

def check_fields(op, allowed):
    extra=set(op)-allowed
    if extra:raise AgentEditError("unexpected or privileged fields: "+str(sorted(extra)))

def check_revision(item,field,sha):
    if field not in item or digest(item[field])!=sha:
        raise AgentEditError("stale or missing field revision")

def finite(x):
    if type(x) in (float,int):return math.isfinite(x)
    if isinstance(x,list):return all(finite(v) for v in x)
    return False

def key_cell(param,b,index):
    if not isinstance(index,list) or len(index)!=2 or any(type(v) is not int for v in index):
        raise AgentEditError("key_index must be [x,y]")
    axes=param.get("axis_points");vals=b.get("values");flags=b.get("isSet")
    if not isinstance(axes,list) or len(axes)!=2 or not all(isinstance(a,list) for a in axes):
        raise AgentEditError("invalid parameter axes")
    nx,ny=len(axes[0]),len(axes[1])
    if not isinstance(vals,list) or not isinstance(flags,list) or len(vals)!=nx or len(flags)!=nx:
        raise AgentEditError("invalid binding grid")
    if any(not isinstance(v,list) or len(v)!=ny for v in vals):
        raise AgentEditError("invalid binding values")
    if any(not isinstance(v,list) or len(v)!=ny or any(type(f) is not bool for f in v) for v in flags):
        raise AgentEditError("invalid binding flags")
    x,y=index
    if not 0<=x<nx or not 0<=y<ny:raise AgentEditError("keyform out of range")
    return x,y

def model_map(doc,source_sha):
    nodes=[]
    for path,item in walk_nodes(doc["nodes"]):
        mesh=item.get("mesh")
        nodes.append({"guid":guid(item),"name":item.get("name"),"path":path,
                      "type":item.get("type"),"mesh_sha256":mesh_fingerprint(mesh) if isinstance(mesh,dict) else None,
                      "vertex_count":len(mesh.get("verts",[])) if isinstance(mesh,dict) else None})
    pars=[]
    for p in doc.get("param",[]):
        if not isinstance(p,dict):raise AgentEditError("malformed parameter")
        pars.append({"guid":guid(p),"name":p.get("name"),"axis_points":p.get("axis_points"),
                     "bindings":[{"index":i,"node_guid":b.get("node"),"property":b.get("param_name")}
                                 for i,b in enumerate(p.get("bindings",[]))]})
    return {"format":"inochi-ai-rigging.agent-map.v1","source_sha256":source_sha,
            "nodes":nodes,"parameters":pars,"creator_rendered":False}

def read_target(doc,kind,key,field="",parameter_guid="",node_guid="",binding_index=0,start=0,limit=256):
    if kind=="node": obj=node(doc,key)
    elif kind=="parameter": obj=parameter(doc,key)
    elif kind=="binding":obj=binding(doc,parameter_guid,node_guid,binding_index)[1]
    else:raise AgentEditError("kind must be node, parameter or binding")
    if field:
        if field not in obj:raise AgentEditError("field absent")
        obj=obj[field]
    if type(start) is not int or type(limit) is not int or start<0 or not 1<=limit<=4096:
        raise AgentEditError("invalid page")
    total=len(obj) if isinstance(obj,list) else None
    data=obj[start:start+limit] if isinstance(obj,list) else obj
    if not field and kind=="node":
        data={k:({"kind":"nested-object","fields":sorted(v)} if k=="mesh" and isinstance(v,dict) else
                  [{"guid":guid(c),"name":c.get("name")} for c in v] if k=="children" and isinstance(v,list) else v)
              for k,v in obj.items()}
    if not field and kind=="binding" and isinstance(data,dict):
        data={k:({"kind":"paged-array","count":len(v)} if k in ("values","isSet") and isinstance(v,list) else v)
              for k,v in data.items()}
    return {"format":"inochi-ai-rigging.agent-target.v1","kind":kind,"guid":key,
            "field":field or None,"value":data,"value_sha256":digest(obj),
            "next_start":start+limit if total is not None and start+limit<total else None,
            "total_items":total}

def apply_agent_edit(doc,op):
    if not isinstance(op,dict):raise AgentEditError("edit must be object")
    typ=op.get("op")
    if typ in ("set_node_property","set_parameter_property"):
        check_fields(op,{"op","guid","field","value","expected_value_sha256"})
        obj=node(doc,op["guid"]) if typ=="set_node_property" else parameter(doc,op["guid"])
        field=op.get("field");val=op.get("value")
        if typ=="set_parameter_property" and field!="name":
            raise AgentEditError("parameter axes cannot be modified without rebasing all bindings")
        allowed={"name","enabled","zsort","opacity","mask_threshold","emissionStrength","tint","screenTint"}
        if typ=="set_node_property" and field not in allowed:
            raise AgentEditError("pivot/transform/structure mutations require their own compensation contract")
        if field=="name":
            if not isinstance(val,str) or not val.strip() or len(val)>256:raise AgentEditError("bad name")
        elif field=="enabled":
            if type(val) is not bool:raise AgentEditError("enabled must be bool")
        elif field in ("opacity","mask_threshold","zsort","emissionStrength"):
            if type(val) not in (float,int) or not math.isfinite(val):raise AgentEditError("bad scalar")
            if field in ("opacity","mask_threshold") and not 0<=val<=1:raise AgentEditError("range error")
        else:
            if not isinstance(val,list) or len(val) not in (3,4) or not finite(val):
                raise AgentEditError("invalid color")
        check_revision(obj,field,op.get("expected_value_sha256"))
        obj[field]=copy.deepcopy(val)
        return {"op":typ,"guid":op["guid"],"field":field,"after_sha256":digest(val)}
    if typ in ("edit_mesh_vertices","edit_mesh_uvs"):
        check_fields(op,{"op","node_guid","expected_mesh_sha256","updates","space"})
        target=node(doc,op["node_guid"]);mesh=target.get("mesh")
        if not isinstance(mesh,dict) or mesh_fingerprint(mesh)!=op.get("expected_mesh_sha256"):
            raise AgentEditError("stale mesh SHA")
        expect="mesh_local" if typ=="edit_mesh_vertices" else "texture_uv"
        if op.get("space")!=expect:raise AgentEditError("coordinate space must be "+expect)
        validate_mesh(target,target.get("name","mesh"))
        field=mesh["verts" if typ=="edit_mesh_vertices" else "uvs"]
        updates=op.get("updates")
        if not isinstance(updates,list) or not updates:raise AgentEditError("nonempty updates required")
        seen=set()
        for u in updates:
            if not isinstance(u,dict) or set(u)!={"index","expected","value"}:
                raise AgentEditError("index, expected and value required")
            i=u["index"]
            if type(i) is not int or not 0<=i<len(field) or i in seen:
                raise AgentEditError("bad or duplicate vertex index")
            if field[i]!=u["expected"] or not isinstance(u["value"],list) or len(u["value"])!=2 or not finite(u["value"]):
                raise AgentEditError("stale or invalid vertex/UV value")
            seen.add(i)
        for u in updates:field[u["index"]]=copy.deepcopy(u["value"])
        validate_mesh(target,target.get("name","mesh"))
        return {"op":typ,"node_guid":op["node_guid"],"changed_count":len(seen),
                "mesh_sha256_after":mesh_fingerprint(mesh)}
    if typ in ("replace_deform_keyform","replace_binding_value_keyform"):
        allowed={"op","parameter_guid","node_guid","binding_index","key_index","expected_is_set",
                 "expected_offsets_sha256","offsets","space"} if typ=="replace_deform_keyform" else {
                 "op","parameter_guid","node_guid","binding_index","key_index","expected_is_set",
                 "expected_value_sha256","value"}
        check_fields(op,allowed)
        p,b=binding(doc,op["parameter_guid"],op["node_guid"],op["binding_index"])
        deform=b.get("param_name")=="deform"
        if deform!=(typ=="replace_deform_keyform"):raise AgentEditError("wrong binding type")
        x,y=key_cell(p,b,op["key_index"])
        if type(op.get("expected_is_set")) is not bool or b["isSet"][x][y]!=op["expected_is_set"]:
            raise AgentEditError("key authored-state changed")
        old=b["values"][x][y]
        new=op.get("offsets" if deform else "value")
        expected=op.get("expected_offsets_sha256" if deform else "expected_value_sha256")
        if digest(old)!=expected:raise AgentEditError("stale keyform SHA")
        if deform:
            if op.get("space")!="mesh_local_displacement":
                raise AgentEditError("explicit displacement coordinates required")
            mesh=validate_mesh(node(doc,op["node_guid"]),op["node_guid"])
            if mesh is None:raise AgentEditError("binding has no mesh")
            if not isinstance(new,list) or len(new)!=len(mesh["neutral"]) or any(
                    not isinstance(v,list) or len(v)!=2 or not finite(v) for v in new):
                raise AgentEditError("vertex count/shape mismatch")
            if geometry_errors(mesh["neutral"],new,mesh["triangles"]):
                raise AgentEditError("unsafe inverted/collapsed deformation")
        else:
            if type(old) in (int,float):
                if type(new) not in (int,float) or not finite(new):
                    raise AgentEditError("scalar type mismatch")
            elif isinstance(old,list):
                if not isinstance(new,list) or len(new)!=len(old) or not finite(new):
                    raise AgentEditError("vector type mismatch")
            else:raise AgentEditError("unsupported binding data type")
        b["values"][x][y]=copy.deepcopy(new)
        b["isSet"][x][y]=True
        return {"op":typ,"node_guid":op["node_guid"],"parameter_guid":op["parameter_guid"],
                "key_index":[x,y],"replaced_existing":op["expected_is_set"]}
    raise AgentEditError("unsupported AI edit: "+str(typ))
