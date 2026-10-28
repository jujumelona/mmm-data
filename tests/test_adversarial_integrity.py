"""Regression tests for exact source model integrity, not render quality."""
import copy
import hashlib
import json
import struct
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from native.inp08 import encode, parse, validate_mesh, FormatError, MAGIC
from rigging.agent_editor import digest
from rigging.contracts import mesh_fingerprint
from rigging.live_model_bridge import prepare_session, apply_batch, CreatorSessionError
from rigging.transactions import execute_transaction, FORMAT
from test_rigging import specimen

class IntegrityRegressions(unittest.TestCase):
    def test_neutral_winding_flip_refused(self):
        doc,raw,_=specimen();mesh=doc["nodes"]["children"][0]["mesh"]
        edit={"op":"edit_mesh_vertices","node_guid":"face-001",
              "expected_mesh_sha256":mesh_fingerprint(mesh),"space":"mesh_local",
              "updates":[{"index":1,"expected":[10,0],"value":[-10,0]}]}
        batch={"format":FORMAT,"request_id":"flip","source_sha256":hashlib.sha256(raw).hexdigest(),"edits":[edit]}
        with tempfile.TemporaryDirectory() as td:
            src=Path(td)/"source.inx";src.write_bytes(raw)
            with self.assertRaisesRegex(ValueError,"triangle"):
                execute_transaction(src,batch)
            self.assertEqual(src.read_bytes(),raw)

    def test_opacity_binding_range_refused(self):
        doc,raw,_=specimen()
        b=copy.deepcopy(doc["param"][0]["bindings"][0])
        b["param_name"]="opacity";b["values"]=[[1.0]*3 for _ in range(3)]
        doc["param"][0]["bindings"].append(b)
        raw=encode(doc,parse(raw)[2])
        edit={"op":"replace_binding_value_keyform","parameter_guid":"param-01",
              "node_guid":"face-001","binding_index":1,"key_index":[1,1],
              "expected_is_set":True,"expected_value_sha256":digest(1.0),"value":999.0}
        batch={"format":FORMAT,"request_id":"opacity","source_sha256":hashlib.sha256(raw).hexdigest(),"edits":[edit]}
        with tempfile.TemporaryDirectory() as td:
            src=Path(td)/"source.inx";src.write_bytes(raw)
            with self.assertRaisesRegex(ValueError,"opacity"):
                execute_transaction(src,batch)

    def test_texture_corruption_rolls_back(self):
        doc,_,_=specimen()
        tail=b"TEX_SECT"+struct.pack(">I",1)+struct.pack(">I",4)+b"\x00DATA"
        raw=encode(doc,tail)
        state={"raw":raw,"project":"/models/source.inx","imports":0}
        def rpc(method,params=None):
            if method=="get_status":
                return {"project_path":state["project"],"edit_mode":"model","armed_parameter":None}
            if method=="export_inp":
                Path(params["path"]).write_bytes(state["raw"])
                return {"path":params["path"]}
            if method=="import_inp":
                state["imports"]+=1
                state["raw"]=Path(params["path"]).read_bytes()
                if state["imports"]==1:
                    d,_,t=parse(state["raw"])
                    state["raw"]=encode(d,t[:-1]+b"X")
                state["project"]=""
                return True
            raise AssertionError(method)
        mesh=doc["nodes"]["children"][0]["mesh"]
        batch={"format":FORMAT,"request_id":"corrupt-texture",
               "source_sha256":hashlib.sha256(raw).hexdigest(),
               "edits":[{"op":"subdivide_mesh","node_guid":"face-001",
                         "expected_mesh_sha256":mesh_fingerprint(mesh)}]}
        with tempfile.TemporaryDirectory() as td,patch("rigging.live_model_bridge.call_creator",side_effect=rpc),patch.dict("os.environ",{"INOCHI_CREATOR_MUTATIONS":"1"}):
            session=prepare_session(td,expected_project_path="/models/source.inx")
            with self.assertRaisesRegex(CreatorSessionError,"texture"):
                apply_batch(session["session_path"],batch,expected_project_path="/models/source.inx",acknowledge_project_replacement=True)
            self.assertEqual(state["imports"],2)
            self.assertEqual(state["raw"],raw)
            self.assertEqual(json.loads((Path(session["session_path"])/"manifest.json").read_text())["state"],"rolled_back")

    def test_duplicate_json_object_field_refused(self):
        doc,raw,_=specimen();_,_,tail=parse(raw)
        payload=b'{"nodes":'+json.dumps(doc["nodes"]).encode()+b',"meta":{"name":"a","name":"b"},"param":[]}'
        with self.assertRaisesRegex(FormatError,"duplicate"):
            parse(MAGIC+struct.pack(">I",len(payload))+payload+tail)

    def test_duplicate_triangle_refused(self):
        doc,_,_=specimen();part=doc["nodes"]["children"][0]
        part["mesh"]["indices"].extend([0,1,4])
        with self.assertRaisesRegex(FormatError,"duplicate triangle"):
            validate_mesh(part,"face")

    def test_inconsistent_adjacent_winding_refused(self):
        doc,_,_=specimen();part=doc["nodes"]["children"][0]
        part["mesh"]["indices"][3:6]=[1,4,3]
        with self.assertRaisesRegex(FormatError,"winding"):
            validate_mesh(part,"face")
