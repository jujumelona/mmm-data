"""Contract tests for MCP tool wrappers, without requiring network install of mcp."""
from __future__ import annotations
import hashlib
import importlib
import json
import sys
import tempfile
import types
import unittest
from pathlib import Path

from test_rigging import specimen

class FakeMCP:
    def __init__(self, name): self.name=name;self.registered={}
    def tool(self):
        def deco(func):self.registered[func.__name__]=func;return func
        return deco

class TestMCP(unittest.TestCase):
    def setUp(self):
        mcp=types.ModuleType('mcp');server=types.ModuleType('mcp.server');fast=types.ModuleType('mcp.server.fastmcp');fast.FastMCP=FakeMCP
        # Patch only the MCP module entries: restoring all sys.modules would
        # discard NumPy modules imported during this test and cause a C-extension
        # reimport failure later in the same Python process.
        fakes={'mcp':mcp,'mcp.server':server,'mcp.server.fastmcp':fast}
        self._missing=object()
        self._saved={key:sys.modules.get(key,self._missing) for key in fakes}
        sys.modules.update(fakes)
        sys.modules.pop('rigging.mcp_server',None)
        self.server=importlib.import_module('rigging.mcp_server')
    def tearDown(self):
        sys.modules.pop('rigging.mcp_server',None)
        for key,value in self._saved.items():
            if value is self._missing:
                sys.modules.pop(key,None)
            else:
                sys.modules[key]=value

    def test_tools_registered_and_not_promising_full_autorig(self):
        reg=self.server.mcp.registered
        for key in ['rig_status','rig_inspect','rig_anchor_contract','rig_validate_anchors',
                    'rig_propose_keyform','rig_apply_approved_plan','creator_get_node','creator_list_nodes']:
            self.assertIn(key,reg)
        self.assertEqual(reg['rig_status']()['psd_to_full_rig'],'NOT implemented')

    def test_inspect_validate_propose_apply_pipeline(self):
        doc,raw,manifest=specimen()
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);model=root/'original.inx';model.write_bytes(raw)
            mf=root/'anchors.json';mf.write_text(json.dumps(manifest))
            info=self.server.rig_inspect(str(model))
            self.assertEqual(info['source_sha256'],hashlib.sha256(raw).hexdigest())
            self.assertEqual(self.server.rig_validate_anchors(str(model),str(mf))['count'],4)
            config=root/'config.json';config.write_text(json.dumps({'node_guid':'face-001','parameter':'Head:: Angle',
                'key_index':[2,2],'targets_local':{'a':[0,0],'b':[10,0],'c':[0,10],'d':[10,11]}}))
            output=root/'candidate.json'
            p=self.server.rig_propose_keyform(str(model),str(mf),str(config),str(output))
            self.assertEqual(p['status'],'CANDIDATE_ONLY')
            with self.assertRaises(ValueError):
                self.server.rig_apply_approved_plan(str(model),str(output),str(root/'candidate.inx'))
            new=root/'candidate.inx'
            result=self.server.rig_apply_approved_plan(str(model),str(output),str(new),True)
            self.assertEqual(result['applied'],1)
            self.assertEqual(model.read_bytes(),raw)
            self.assertEqual(self.server.rig_inspect(str(new))['mesh_nodes'][0]['vertices'],5)
            self.assertFalse(result['creator_render_tested'])
            with self.assertRaisesRegex(ValueError,'refusing output overwrite'):
                self.server.rig_apply_approved_plan(str(model),str(output),str(new),True)

if __name__=='__main__':unittest.main()
