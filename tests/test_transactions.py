"""No fake Creator tests: prove real INP bytes, mesh/topology/UV, atomic file safety."""
from __future__ import annotations
import copy
import hashlib
import json
import struct
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from native.inp08 import encode,parse
from rigging.contracts import mesh_fingerprint
from rigging.topology import subdivide_once,TopologyError
from rigging.transactions import execute_transaction, TransactionError,FORMAT
from rigging.quality import inspect_geometry
from test_rigging import specimen

class TransactionTests(unittest.TestCase):
    def setUp(self):
        self.doc,self.raw,self.manifest=specimen()
        self.mesh=self.doc['nodes']['children'][0]['mesh']
        self.sha=mesh_fingerprint(self.mesh)

    def batch(self, *edits):
        return {'format':FORMAT,'source_sha256':hashlib.sha256(self.raw).hexdigest(),
                'request_id':'manual-rig-001','edits':list(edits)}

    def sub(self):return {'op':'subdivide_mesh','node_guid':'face-001','expected_mesh_sha256':self.sha}

    def key(self, idx=[2,2]):
        return {'op':'set_new_keyform','parameter':'Head:: Angle','node_guid':'face-001',
                'key_index':idx,'vertex_offsets':[[0,0]]*5}

    def test_topology_preserves_original_vertices_uvs_and_all_existing_keyforms(self):
        document=copy.deepcopy(self.doc)
        binding=document['param'][0]['bindings'][0]
        binding['values'][0][0][1]=[2,4]
        prior=copy.deepcopy(binding)
        result=subdivide_once(document,'face-001',expected_mesh_sha256=self.sha)
        mesh=document['nodes']['children'][0]['mesh'];b=document['param'][0]['bindings'][0]
        self.assertEqual((result['vertices_before'],result['vertices_after']), (5,13))
        self.assertEqual(result['triangles_after'],16)
        self.assertEqual(mesh['verts'][:5],self.mesh['verts'])
        self.assertEqual(mesh['uvs'][:5],self.mesh['uvs'])
        self.assertEqual(mesh['indices'][:3],[0,5,7]) # first triangle 0,1,4
        self.assertEqual(b['isSet'],prior['isSet'])
        for x in range(3):
            for y in range(3):
                self.assertEqual(b['values'][x][y][:5],prior['values'][x][y])
                self.assertEqual(len(b['values'][x][y]),13)
        self.assertEqual(b['values'][0][0][5],[1,2])
        self.assertTrue(inspect_geometry(document)['individual_geometry_pass'])
        self.assertEqual(self.doc['nodes']['children'][0]['mesh'],self.mesh)

    def test_source_revision_conflict_and_bad_mesh_digest(self):
        with tempfile.TemporaryDirectory() as d:
            m=Path(d)/'source.inx';m.write_bytes(self.raw)
            stale=self.batch(self.sub());stale['source_sha256']='e'*64
            with self.assertRaisesRegex(TransactionError,'stale'):execute_transaction(m,stale)
            wrong=self.sub();wrong['expected_mesh_sha256']='e'*64
            with self.assertRaisesRegex(TopologyError,'stale'):execute_transaction(m,self.batch(wrong))

    def test_atomic_all_or_nothing_failure(self):
        with tempfile.TemporaryDirectory() as d:
            m=Path(d)/'source.inx';m.write_bytes(self.raw)
            out=Path(d)/'output.inx'
            failure=self.key([1,1]) # originally authored
            with self.assertRaisesRegex(ValueError,'existing authored'):
                execute_transaction(m,self.batch(self.sub(),failure),destination=out,commit=True)
            self.assertFalse(out.exists())
            self.assertEqual(m.read_bytes(),self.raw)

    def test_topology_then_stale_keyform_rejected_no_partial(self):
        with tempfile.TemporaryDirectory() as d:
            m=Path(d)/'source.inx';m.write_bytes(self.raw)
            with self.assertRaisesRegex(ValueError,'same count'):
                execute_transaction(m,self.batch(self.sub(),self.key()),destination=Path(d)/'out.inx',commit=True)
            self.assertEqual(list(Path(d).glob('*.inx')),[m])

    def test_roundtrip_binary_vendor_extension_untouched(self):
        extra=b'EXT_SECT'+struct.pack('>I',1)+struct.pack('>I',4)+b'unit'+struct.pack('>I',3)+b'raw'
        tex=b'TEX_SECT'+struct.pack('>I',1)+struct.pack('>I',5)+b'\x00HELLO'+extra
        raw=encode(self.doc,tex)
        with tempfile.TemporaryDirectory() as d:
            model=Path(d)/'in.inx';model.write_bytes(raw)
            b=self.batch(self.sub());b['source_sha256']=hashlib.sha256(raw).hexdigest()
            out=Path(d)/'out.inx'
            receipt=execute_transaction(model,b,destination=out,commit=True)
            self.assertTrue(receipt['committed'])
            self.assertEqual(model.read_bytes(),raw)
            self.assertEqual(parse(out.read_bytes())[2],tex)
            self.assertEqual(receipt['candidate_sha256'],hashlib.sha256(out.read_bytes()).hexdigest())
            with self.assertRaisesRegex(TransactionError,'existing output'):
                execute_transaction(model,b,destination=out,commit=True)

    def test_preview_never_writes(self):
        with tempfile.TemporaryDirectory() as d:
            model=Path(d)/'input.inx';model.write_bytes(self.raw)
            result=execute_transaction(model,self.batch(self.sub()),destination=Path(d)/'candidate.inx',commit=False)
            self.assertFalse(result['committed'])
            self.assertFalse((Path(d)/'candidate.inx').exists())
            self.assertFalse(result['creator_render_tested'])

    def test_no_bypass_fields_or_duplicate_operations(self):
        with tempfile.TemporaryDirectory() as d:
            model=Path(d)/'input.inx';model.write_bytes(self.raw)
            f=self.key();f['allow_unsafe']=True
            for batch in [self.batch(f),self.batch(self.sub(),self.sub()),self.batch({'op':'delete_part'}),
                          {**self.batch(self.key()),'safety_override':True}]:
                with self.assertRaises(ValueError):execute_transaction(model,batch)

    def test_cli_transaction_preview_and_commit(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d); model=root/'model.inx';model.write_bytes(self.raw)
            batch=root/'batch.json';batch.write_text(json.dumps(self.batch(self.sub())))
            output=root/'fine.inx'
            cmd=[sys.executable,'-m','rigging.cli','transaction',str(model),str(batch)]
            preview=subprocess.run(cmd,capture_output=True,text=True,check=True)
            self.assertFalse(json.loads(preview.stdout)['committed'])
            run=subprocess.run(cmd+['--commit','--out',str(output),'--strict-pairs'],capture_output=True,text=True,check=True)
            self.assertTrue(json.loads(run.stdout)['committed'])
            self.assertEqual(len(parse(output.read_bytes())[0]['nodes']['children'][0]['mesh']['verts']),13)
            self.assertEqual(model.read_bytes(),self.raw)

    def test_geometry_detects_pairwise_composition_failure(self):
        p=copy.deepcopy(self.doc['param'][0]);q=copy.deepcopy(p)
        p['guid']='left';q['guid']='right';q['name']='Other param'
        self.doc['param']=[p,q]
        # Each individual 2D warp is safe (one independent axis compression),
        # but together they invert some triangles.
        for binding in [p['bindings'][0],q['bindings'][0]]:
            binding['values'][2][2][2]=[0,-6]
            binding['isSet'][2][2]=True
        report=inspect_geometry(self.doc)
        self.assertTrue(report['individual_geometry_pass'])
        self.assertFalse(report['additive_proxy_pair_pass'])
        self.assertGreater(len(report['additive_proxy_pair_failures']),0)

    def test_foreign_vertex_property_rejected(self):
        d=copy.deepcopy(self.doc)
        d['nodes']['children'][0]['mesh']['weights']=[1]*5
        with self.assertRaisesRegex(TopologyError,'unknown mesh'):
            subdivide_once(d,'face-001',expected_mesh_sha256=mesh_fingerprint(d['nodes']['children'][0]['mesh']))

if __name__=='__main__':unittest.main()

class AdditionalGuards(unittest.TestCase):
    def test_guid_is_preferred_to_duplicate_parameter_names(self):
        doc,raw,_=specimen()
        dup=copy.deepcopy(doc['param'][0]);dup['guid']='second';doc['param'].append(dup)
        from native.inp08 import apply_keyform
        patch={'parameter_guid':'param-01','node_guid':'face-001', 'key_index':[0,0],
               'vertex_offsets':[[0,0]]*5}
        apply_keyform(doc,patch)
        self.assertTrue(doc['param'][0]['bindings'][0]['isSet'][0][0])
        self.assertFalse(doc['param'][1]['bindings'][0]['isSet'][0][0])

    def test_commit_disallows_skipping_pair_geometry_gate(self):
        doc,raw,_=specimen()
        p=doc['param'][0];p['guid']='a';q=copy.deepcopy(p);q['guid']='b';q['name']='Other'
        doc['param'].append(q)
        for binding in [p['bindings'][0],q['bindings'][0]]:
            binding['values'][2][2][2]=[0,-6];binding['isSet'][2][2]=True
        raw=encode(doc,parse(raw)[2])
        with tempfile.TemporaryDirectory() as td:
            model=Path(td)/'model.inx';model.write_bytes(raw)
            mesh=doc['nodes']['children'][0]['mesh']
            b={'format':FORMAT,'source_sha256':hashlib.sha256(raw).hexdigest(),'request_id':'verify',
               'edits':[{'op':'subdivide_mesh','node_guid':'face-001', 'expected_mesh_sha256':mesh_fingerprint(mesh)}]}
            # Even explicitly providing strict_pairs=False cannot bypass a commit safety gate.
            with self.assertRaisesRegex(TransactionError,'unsafe additive-proxy pairs'):
                execute_transaction(model,b,destination=Path(td)/'bad.inx',commit=True,strict_pairs=False)
            self.assertFalse((Path(td)/'bad.inx').exists())
