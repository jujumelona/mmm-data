"""Behavioral tests for source-backed, read-only AI/manual rigging handoffs."""
from __future__ import annotations
import copy
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from test_rigging import specimen
from rigging.handoff import manual_handoff, binding_vertex_slice, HandoffError
from rigging.contracts import ContractError, make_anchor
from native.inp08 import encode, parse
import hashlib


class ManualHandoffTests(unittest.TestCase):
    def test_binds_exact_identity_mesh_and_parents(self):
        doc, raw, _ = specimen()
        before = copy.deepcopy(doc)
        result = manual_handoff(doc, raw, 'face-001')
        self.assertEqual(doc, before)
        self.assertEqual(result['identity']['parent_guid'], 'root')
        self.assertEqual(result['identity']['children'], [])
        self.assertEqual(result['mesh']['vertex_count'], 5)
        self.assertEqual(result['mesh']['triangle_count'], 4)
        self.assertEqual(result['explicit_anchor_contract'], 'NOT_PROVIDED')
        self.assertEqual(result['raw_part_fields']['textures'], None)
        self.assertFalse(result['guarantees']['node_pivot_moved'])
        self.assertIn('actual_creator_evaluated_world_transform', result['missing_live_evidence'])

    def test_reports_param_axes_is_set_cells_and_binding_identity(self):
        doc, raw, _ = specimen()
        summary = manual_handoff(doc, raw, 'face-001')['bindings']
        self.assertEqual(len(summary), 1)
        self.assertEqual(summary[0]['parameter_guid'], 'param-01')
        self.assertEqual(summary[0]['axis_points'], [[-30, 0, 30], [-30, 0, 30]])
        self.assertEqual(summary[0]['authored_key_indices'], [[1, 1]])
        self.assertEqual(summary[0]['authored_key_count'], 1)
        self.assertTrue(summary[0]['vertex_offsets_available'])

    def test_exact_anchor_positions_retain_distinction_from_pivot(self):
        doc, raw, anchors = specimen()
        result = manual_handoff(doc, raw, 'face-001', anchors=anchors)
        self.assertEqual(len(result['anchors']), 4)
        b = next(a for a in result['anchors'] if a['label'] == 'b')
        self.assertEqual(b['landmark_mesh_local'], [10.0, 0.0])
        self.assertEqual(b['current_node_pivot_world'], [3.0, 4.0])
        self.assertEqual(b['landmark_world'], [13.0, 4.0])
        self.assertFalse(b['pivot_is_at_landmark'])

    def test_unsupported_world_transform_does_not_invent_pivot(self):
        doc, raw, anchors = specimen()
        doc['nodes']['children'][0]['lockToRoot'] = True
        raw = encode(doc,parse(raw)[2])
        anchors['source_sha256'] = hashlib.sha256(raw).hexdigest()
        anchors['anchors'] = [make_anchor(doc,raw,'face-001',a['label'],a['kind'],a['point_px'],a['coordinates'])
                              for a in anchors['anchors']]
        result = manual_handoff(doc, raw, 'face-001', anchors=anchors)
        self.assertEqual(len(result['anchors']), 4)
        self.assertTrue(all(a['world_estimate_status'] == 'UNSUPPORTED' for a in result['anchors']))
        self.assertTrue(all(a['landmark_world'] is None for a in result['anchors']))

    def test_model_sha_mismatch_rejected(self):
        doc, raw, anchors = specimen()
        anchors['source_sha256'] = '0'*64
        with self.assertRaisesRegex(ContractError, 'SHA-256'):
            manual_handoff(doc, raw, 'face-001', anchors=anchors)

    def test_anchor_for_wrong_node_rejected(self):
        doc, raw, anchors = specimen()
        doc['nodes']['children'].append({'guid':'other', 'name':'other','type':'Node','children':[]})
        with self.assertRaisesRegex(HandoffError,'no anchor'):
            manual_handoff(doc, raw, 'other', anchors=anchors)

    def test_exact_stored_offsets_and_uv_returned_in_bounded_slice(self):
        doc, raw, _ = specimen()
        doc['param'][0]['bindings'][0]['values'][1][1][3] = [3.5, -2.0]
        s = binding_vertex_slice(doc, raw, 'face-001', 'param-01', 0, [1,1],2,2)
        self.assertEqual(s['key_coordinates'], [0,0])
        self.assertTrue(s['is_authored'])
        self.assertEqual([x['index'] for x in s['vertices']], [2,3])
        self.assertEqual(s['vertices'][1]['offset'], [3.5,-2.0])
        self.assertEqual(s['vertices'][1]['neutral'], [10,10])
        self.assertEqual(s['vertices'][1]['uv'], [1,1])
        self.assertEqual(s['next_vertex'], 4)
        e = binding_vertex_slice(doc, raw, 'face-001', 'param-01',0,[2,2],4,256)
        self.assertEqual(e['next_vertex'],None)
        self.assertFalse(e['is_authored'])
        self.assertEqual(len(e['vertices']),1)

    def test_reject_unknown_or_misidentified_binding(self):
        doc, raw, _ = specimen()
        for args in [('not-a-param',0,[1,1]),('param-01',1,[1,1]),('param-01',0,[3,1])]:
            with self.assertRaises(HandoffError):
                binding_vertex_slice(doc,raw,'face-001',args[0],args[1],args[2])

    def test_strict_slice_pagination(self):
        doc, raw, _ = specimen()
        for start,limit in ((-1,20),(0,0),(0,4097),(6,10),(False,1)):
            with self.assertRaises(HandoffError):
                binding_vertex_slice(doc,raw,'face-001','param-01',0,[1,1],start,limit)

    def test_reject_corrupt_binding_vertex_grid(self):
        doc, raw, _ = specimen()
        doc['param'][0]['bindings'][0]['values'][0][1].pop()
        with self.assertRaisesRegex(HandoffError,'vector count'):
            manual_handoff(doc,raw,'face-001')

    def test_reject_nonfinite_and_non_boolean(self):
        doc, raw, _ = specimen()
        doc['param'][0]['bindings'][0]['isSet'][0][0] = 0
        with self.assertRaisesRegex(HandoffError,'booleans'):
            manual_handoff(doc,raw,'face-001')
        doc,raw,_=specimen()
        doc['param'][0]['bindings'][0]['values'][0][0][0] = [float('nan'),0]
        with self.assertRaisesRegex(HandoffError,'invalid deform'):
            manual_handoff(doc,raw,'face-001')

    def test_reject_duplicate_param_guids(self):
        doc,raw,_=specimen()
        doc['param'].append(copy.deepcopy(doc['param'][0]))
        with self.assertRaisesRegex(HandoffError,'duplicate parameter'):
            manual_handoff(doc,raw,'face-001')

    def test_reject_unordered_axis_points(self):
        doc,raw,_=specimen()
        doc['param'][0]['axis_points'][0] = [0,-30,30]
        with self.assertRaisesRegex(HandoffError,'non-increasing'):
            manual_handoff(doc,raw,'face-001')

    def test_cli_manual_handoff_matches_core(self):
        doc,raw,anchors=specimen()
        with tempfile.TemporaryDirectory() as td:
            model=Path(td)/'input.inx'; model.write_bytes(raw)
            p = subprocess.run([sys.executable,'-m','rigging.cli','manual-handoff',str(model),'face-001'],
                               capture_output=True,text=True,check=True)
            report=json.loads(p.stdout)
            self.assertEqual(report,manual_handoff(doc,raw,'face-001'))
            q=subprocess.run([sys.executable,'-m','rigging.cli','binding-slice',str(model),
                                'face-001','param-01','0','1','1','--start','3','--limit','2'],
                                capture_output=True,text=True,check=True)
            self.assertEqual(json.loads(q.stdout)['start_vertex'],3)
            self.assertEqual(model.read_bytes(),raw)

    def test_mcp_read_methods_reuse_same_core(self):
        from test_mcp_contract import FakeMCP
        import types,importlib
        mcp=types.ModuleType('mcp');server=types.ModuleType('mcp.server');fast=types.ModuleType('mcp.server.fastmcp')
        fast.FastMCP=FakeMCP
        v2=types.ModuleType('mcp.server.mcpserver');v2.MCPServer=FakeMCP
        with patch.dict(sys.modules,{'mcp':mcp,'mcp.server':server,'mcp.server.fastmcp':fast,'mcp.server.mcpserver':v2}):
            sys.modules.pop('rigging.mcp_server',None)
            mod=importlib.import_module('rigging.mcp_server')
            self.assertIn('rig_manual_handoff',mod.mcp.registered)
            self.assertIn('rig_binding_vertex_slice',mod.mcp.registered)
            doc,raw,anchors=specimen()
            with tempfile.TemporaryDirectory() as td:
                model=Path(td)/'input.inx';model.write_bytes(raw)
                a=mod.rig_manual_handoff(str(model),'face-001')
                self.assertEqual(a['mesh']['vertex_count'],5)
                b=mod.rig_binding_vertex_slice(str(model),'face-001','param-01',0,[1,1],0,2)
                self.assertEqual(len(b['vertices']),2)
            sys.modules.pop('rigging.mcp_server',None)

if __name__ == '__main__': unittest.main()
