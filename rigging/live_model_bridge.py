"""Creator 0.8 <-> INP rigging engine: guarded live file-roundtrip.

Requires patched Creator RPC. Import replaces the current project and undo
history. This is NOT native in-memory Creator vertex manipulation.
"""
from __future__ import annotations
import hashlib
import json
import os
import tempfile
import uuid
from pathlib import Path
from native.inp08 import parse
from .creator_bridge import call_creator
from .transactions import execute_transaction

class CreatorSessionError(RuntimeError):
    pass

def _hash(b):
    return hashlib.sha256(b).hexdigest()

def _read(path):
    if not path.is_file() or path.is_symlink():
        raise CreatorSessionError("expected regular INP file missing")
    data=path.read_bytes()
    doc,_,_=parse(data)
    return data,doc

def _export(path):
    if path.exists() or path.is_symlink():
        raise CreatorSessionError("refusing to overwrite Creator export")
    result=call_creator("export_inp",{"path":str(path)})
    if not isinstance(result,dict) or Path(result.get("path","")).resolve()!=path.resolve():
        raise CreatorSessionError("Creator returned unexpected export path")
    return _read(path)[0]

def _status():
    s=call_creator("get_status")
    if not isinstance(s,dict) or not s.get("project_path"):
        raise CreatorSessionError("open and save a named Creator project first")
    if s.get("armed_parameter"):
        raise CreatorSessionError("disarm active Creator parameter before proceeding")
    return {"project_path":s["project_path"],"edit_mode":s.get("edit_mode")}

def _load_session(folder):
    base=Path(folder).resolve(strict=True)
    path=base/"manifest.json"
    if not base.is_dir() or not path.is_file() or path.is_symlink():
        raise CreatorSessionError("missing or invalid Creator session")
    m=json.loads(path.read_text(encoding="utf8"))
    if m.get("format")!="inochi-ai-rigging.creator-session.v1":
        raise CreatorSessionError("invalid Creator session format")
    if _hash(_read(base/"source.inp")[0])!=m.get("source_sha256"):
        raise CreatorSessionError("session source was changed")
    return base,m

def _mark(base,manifest,state,**fields):
    result={**manifest,"state":state,**fields}
    temp=base/("manifest."+uuid.uuid4().hex+".tmp")
    temp.write_text(json.dumps(result,indent=2),encoding="utf8")
    os.replace(temp,base/"manifest.json")

def prepare_session(workspace:str,*,expected_project_path:str)->dict:
    before=_status()
    if not expected_project_path or before["project_path"]!=expected_project_path:
        raise CreatorSessionError("Creator project path does not match")
    folder=Path(workspace).resolve(strict=True)
    if not folder.is_dir():
        raise CreatorSessionError("workspace directory required")
    base=Path(tempfile.mkdtemp(prefix="inochi-live-",dir=folder))
    raw=_export(base/"source.inp")
    if _status()!=before:
        raise CreatorSessionError("Creator changed while exporting baseline")
    m={"format":"inochi-ai-rigging.creator-session.v1",
       "session_id":uuid.uuid4().hex,"source_sha256":_hash(raw),
       "expected_project_path":expected_project_path,"status":before,"state":"prepared"}
    (base/"manifest.json").write_text(json.dumps(m,indent=2),encoding="utf8")
    return {"session_path":str(base),"source_path":str(base/"source.inp"),
            "source_sha256":_hash(raw),"creator_project_replacement_required":True}

def preview_batch(folder:str,batch:dict)->dict:
    base,m=_load_session(folder)
    if m["state"]!="prepared":
        raise CreatorSessionError("Creator session is already used")
    return execute_transaction(base/"source.inp",batch,commit=False,strict_pairs=True)

def apply_batch(folder:str,batch:dict,*,expected_project_path:str,
                acknowledge_project_replacement:bool=False)->dict:
    if not acknowledge_project_replacement:
        raise CreatorSessionError("acknowledge_project_replacement required")
    if os.environ.get("INOCHI_CREATOR_MUTATIONS")!="1":
        raise CreatorSessionError("INOCHI_CREATOR_MUTATIONS=1 required")
    base,m=_load_session(folder)
    if m["state"]!="prepared" or m["expected_project_path"]!=expected_project_path:
        raise CreatorSessionError("wrong project or already used Creator session")
    lock=base/".apply.lock"
    try: lock.mkdir()
    except FileExistsError as exc: raise CreatorSessionError("session locked or needs recovery") from exc
    imported=False
    try:
        if _status()!=m["status"]:
            raise CreatorSessionError("Creator project changed after baseline")
        if _hash(_export(base/"recheck.inp"))!=m["source_sha256"]:
            raise CreatorSessionError("Creator model changed since baseline")
        preview_batch(str(base),batch)
        candidate=base/"candidate.inp"
        receipt=execute_transaction(base/"source.inp",batch,
                                    destination=candidate,commit=True,strict_pairs=True)
        if _status()!=m["status"]:
            raise CreatorSessionError("Creator state changed before import")
        _mark(base,m,"importing",candidate_sha256=receipt["candidate_sha256"])
        imported=True
        call_creator("import_inp",{"path":str(candidate)})
        verified=_export(base/"readback.inp")
        actual,_,_=parse(verified)
        expected_doc=_read(candidate)[1]
        if actual!=expected_doc:
            raise CreatorSessionError("Creator import/readback model mismatch")
        _mark(base,m,"verified",readback_sha256=_hash(verified))
        return {"creator_import_verified":True,"source_preserved":True,
                "editor_undo_history_preserved":False,"editor_project_saved":False,
                "session_path":str(base),"receipt":receipt,
                "next_step":"Save imported model under a NEW project name in Creator."}
    except BaseException as exc:
        if imported:
            try:
                call_creator("import_inp",{"path":str(base/"source.inp")})
                restored=_export(base/"rollback_readback.inp")
                if parse(restored)[0]!=_read(base/"source.inp")[1]:
                    raise CreatorSessionError("rollback model mismatch")
            except BaseException as err:
                _mark(base,m,"RECOVERY_REQUIRED",reason=str(exc),rollback_error=str(err))
                raise CreatorSessionError(
                    "CRITICAL: Creator rollback unverified. Restore source.inp manually."
                ) from err
            _mark(base,m,"rolled_back",reason=str(exc))
        raise
    finally:
        lock.rmdir()
