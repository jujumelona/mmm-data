"""AI edit conformance: real synthetic INP serialization and revision gates."""
import hashlib
import tempfile
import unittest
from pathlib import Path
from native.inp08 import parse
from rigging.agent_editor import digest,model_map,read_target
from rigging.transactions import execute_transaction,FORMAT
from test_rigging import specimen

class AIAuthoringTests(unittest.TestCase):
    def test_agent_edits_preserve_original_and_protect_stale_revisions(self):
        doc,raw,_=specimen()
        m=model_map(doc,hashlib.sha256(raw).hexdigest())
        self.assertEqual(m["nodes"][1]["guid"],"face-001")
        view=read_target(doc,"node","face-001","name")
        edit={"op":"set_node_property","guid":"face-001","field":"name",
              "expected_value_sha256":view["value_sha256"],"value":"AI Refined"}
        batch={"format":FORMAT,"request_id":"agent-v06-1",
               "source_sha256":hashlib.sha256(raw).hexdigest(),"edits":[edit]}
        with tempfile.TemporaryDirectory() as d:
            src=Path(d)/"input.inx";dst=Path(d)/"out.inx";src.write_bytes(raw)
            preview=execute_transaction(src,batch,commit=False,strict_pairs=True)
            self.assertFalse(preview["committed"])
            receipt=execute_transaction(src,batch,destination=dst,commit=True)
            self.assertTrue(receipt["committed"])
            self.assertEqual(src.read_bytes(),raw)
            self.assertEqual(parse(dst.read_bytes())[0]["nodes"]["children"][0]["name"],"AI Refined")
            with self.assertRaises(ValueError):
                execute_transaction(src,batch,destination=dst,commit=True)
            edit["expected_value_sha256"]="0"*64
            with self.assertRaises(ValueError):
                execute_transaction(src,batch,commit=False)

    def test_agent_changes_authored_deformation_with_exact_key_sha(self):
        doc,raw,_=specimen()
        old=doc["param"][0]["bindings"][0]["values"][1][1]
        edit={"op":"replace_deform_keyform","parameter_guid":"param-01",
              "node_guid":"face-001","binding_index":0,"key_index":[1,1],
              "expected_is_set":True,"expected_offsets_sha256":digest(old),
              "offsets":[[0,0]]*5,"space":"mesh_local_displacement"}
        batch={"format":FORMAT,"request_id":"agent-v06-2",
               "source_sha256":hashlib.sha256(raw).hexdigest(),"edits":[edit]}
        with tempfile.TemporaryDirectory() as d:
            src=Path(d)/"a.inx";dst=Path(d)/"b.inx";src.write_bytes(raw)
            r=execute_transaction(src,batch,destination=dst,commit=True)
            self.assertTrue(r["committed"])
            self.assertTrue(parse(dst.read_bytes())[0]["param"][0]["bindings"][0]["isSet"][1][1])
            edit["expected_offsets_sha256"]="0"*64
            with self.assertRaises(ValueError):
                execute_transaction(src,batch,commit=False)

if __name__=="__main__":unittest.main()
