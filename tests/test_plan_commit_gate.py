"""An alternate MCP plan writer must not bypass batch composition quality gates."""
from __future__ import annotations
import copy,hashlib,json,tempfile,unittest
from pathlib import Path
from native.inp08 import encode,parse
from test_rigging import specimen
from rigging.mcp_server import rig_apply_approved_plan

class ApprovedPlanGate(unittest.TestCase):
    def run_plan(self,raw):
        plan={'format':'inochi-authoring.keyform-plan.v1','source_sha256':hashlib.sha256(raw).hexdigest(),
              'status':'CANDIDATE_ONLY','algorithm':'TPS-v1-explicit-anchored','source_anchor_count':4,
              'patches':[{'parameter':'Head:: Angle','node_guid':'face-001','key_index':[0,0],
                          'vertex_offsets':[[0,0] for _ in range(5)]}]}
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);src=root/'source.inx';src.write_bytes(raw)
            p=root/'plan.json';p.write_text(json.dumps(plan));out=root/'new.inx'
            try:
                r=rig_apply_approved_plan(str(src),str(p),str(out),True)
            except ValueError:
                self.assertFalse(out.exists())
                self.assertEqual(src.read_bytes(),raw)
                raise
            self.assertTrue(out.is_file())
            return r
    def test_valid_plan_passes(self):
        _,raw,_=specimen();result=self.run_plan(raw)
        self.assertFalse(result['creator_render_tested'])
    def test_individually_safe_pairwise_inversion_is_rejected(self):
        doc,raw,_=specimen()
        a=doc['param'][0];b=copy.deepcopy(a);a['guid']='left';b['guid']='right';b['name']='Other'
        doc['param'].append(b)
        for param in (a,b):
            bind=param['bindings'][0]
            bind['values'][2][2][2]=[0,-6];bind['isSet'][2][2]=True
        raw=encode(doc,parse(raw)[2])
        with self.assertRaisesRegex(ValueError,'composite geometry'):
            self.run_plan(raw)
